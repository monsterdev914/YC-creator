from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from .auth import login
from .cofounder_profile import fill_cofounder_matching_profile
from .config import ROOT, browser_settings
from .credentials_io import (
    DEFAULT_CREDENTIALS_PATH,
    Credential,
    load_credentials,
    update_credential_status,
)
from .profile_data import DEFAULT_PROFILE_PATH, ProfileData, load_profile
from .proxy import context_options, get_proxy_pool

EDIT_URL = "https://www.startupschool.org/users/edit_sign_up"
COFOUNDER_URL = "https://www.startupschool.org/cofounder-matching"
CF_PROFILE_URL = "https://www.startupschool.org/cofounder-matching/profile"


@dataclass
class ProfileResult:
    email: str
    username: str
    status: str
    message: str
    finished_at: str


def fill_named(page: Page, name: str, value: str) -> None:
    field = page.locator(f'[name="{name}"]').first
    field.wait_for(state="visible", timeout=15000)
    field.click()
    field.fill("")
    field.fill(value)


def set_yes_no_radios(page: Page, profile: ProfileData) -> None:
    """
    Radio order on edit_sign_up:
      0/1 working on startup (active_founder / aspiring_founder)
      2/3 technical (true / false)
      4/5 seeking co-founder (true / false)
    """
    radios = page.locator('input[type="radio"]')
    radios.nth(0 if profile.working_on_startup else 1).check()
    radios.nth(2 if profile.is_technical else 3).check()
    radios.nth(4 if profile.seeking_a_cofounder else 5).check()


def select_dropdown(page: Page, name: str, option_text: str) -> None:
    field = page.locator(f'[name="{name}"]').first
    field.click()
    option = page.get_by_role(
        "option", name=re.compile(rf"^{re.escape(option_text)}$", re.I)
    )
    if option.count() == 0:
        option = page.get_by_text(option_text, exact=True)
    option.first.click()


def save_or_skip_refresh(page: Page) -> str:
    """
    Click Save when enabled. If disabled, skip save and refresh the page.
    Returns: 'saved' | 'skipped_refresh'
    """
    save_btn = page.get_by_role("button", name=re.compile(r"^Save$"))
    page.wait_for_timeout(500)
    body = page.locator("body").inner_text().lower()
    if "please fix" in body or "fix errors" in body:
        raise RuntimeError("Form has validation errors before save")

    if not save_btn.is_enabled():
        print("  Save disabled — skipping save and refreshing")
        page.reload(wait_until="domcontentloaded")
        page.locator('[name="ssoUser.firstName"]').wait_for(
            state="visible", timeout=30000
        )
        return "skipped_refresh"

    save_btn.click()
    page.wait_for_timeout(2500)
    lowered = page.locator("body").inner_text().lower()
    if "please fix" in lowered or "fix errors" in lowered:
        raise RuntimeError("Save rejected: please fix validation errors on the form")
    if "no unsaved changes" not in lowered and "saved" not in lowered:
        page.wait_for_timeout(3000)
        lowered = page.locator("body").inner_text().lower()
    if "please fix" in lowered or "fix errors" in lowered:
        raise RuntimeError("Save rejected: please fix validation errors on the form")
    return "saved"


def fill_profile_form(page: Page, profile: ProfileData, email: str) -> str:
    if "edit_sign_up" not in page.url:
        page.goto(EDIT_URL, wait_until="domcontentloaded")
    page.locator('[name="ssoUser.firstName"]').wait_for(state="visible", timeout=30000)

    fill_named(page, "ssoUser.firstName", profile.first_name)
    fill_named(page, "ssoUser.lastName", profile.last_name)
    email_field = page.locator('[name="ssoUser.email"]').first
    if email_field.input_value().strip() != email:
        fill_named(page, "ssoUser.email", email)

    fill_named(page, "linkedin", profile.linkedin_url)
    fill_named(page, "education", profile.education)
    fill_named(page, "employment", profile.employment)
    fill_named(page, "location", profile.location)
    fill_named(page, "impressiveThing", profile.accomplishment)

    set_yes_no_radios(page, profile)

    if profile.gender:
        try:
            select_dropdown(page, "gender", profile.gender)
        except Exception:
            fill_named(page, "gender", profile.gender)

    birth = page.locator('[name="birthdate"]').first
    birth.fill(profile.birthday)

    if profile.hear_about:
        try:
            label = page.get_by_text(
                "How did you first hear about Startup School?", exact=False
            )
            container = label.locator(
                "xpath=ancestor::div[contains(@class,'') or true][1]"
            )
            trigger = container.locator("input[type='text'], [role='combobox']").first
            if trigger.count():
                trigger.click()
                page.get_by_text(profile.hear_about, exact=False).first.click()
        except Exception:
            pass

    return save_or_skip_refresh(page)


def accept_behavior_agreement(page: Page) -> None:
    """Check all boxes on Co-founder Matching Behavior Agreement, then I agree."""
    page.get_by_text(
        re.compile(r"Co-founder Matching Behavior Agreement", re.I)
    ).first.wait_for(state="visible", timeout=30000)

    checkboxes = page.locator('input[type="checkbox"]')
    if checkboxes.count() == 0:
        checkboxes = page.get_by_role("checkbox")
    count = checkboxes.count()
    if count < 6:
        # Fall back: click every agreement label that starts with "I confirm"
        labels = page.get_by_text(re.compile(r"^I confirm that", re.I))
        for i in range(labels.count()):
            labels.nth(i).click()
    else:
        for i in range(count):
            box = checkboxes.nth(i)
            try:
                if not box.is_checked():
                    box.check()
            except Exception:
                box.click()

    agree_btn = page.get_by_role("button", name=re.compile(r"^I agree$", re.I))
    if agree_btn.count() == 0:
        agree_btn = page.get_by_role("button", name=re.compile(r"^(Save|I agree)$", re.I))
    agree_btn.first.wait_for(state="visible", timeout=15000)
    if not agree_btn.first.is_enabled():
        raise RuntimeError("I agree button is disabled; not all checkboxes accepted")
    agree_btn.first.click()
    page.wait_for_timeout(2000)


def start_cofounder_profile(page: Page) -> None:
    """Open cofounder matching, Create profile, then accept behavior agreement."""
    # Already mid-flow on profile wizard
    page.goto(COFOUNDER_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    if "cofounder-matching/profile" in page.url:
        return

    if page.get_by_text(
        re.compile(r"Co-founder Matching Behavior Agreement", re.I)
    ).count():
        accept_behavior_agreement(page)
        return

    create_btn = page.get_by_role(
        "button", name=re.compile(r"Create profile", re.I)
    )
    if create_btn.count() == 0:
        create_btn = page.get_by_text(re.compile(r"^Create profile$", re.I))
    if create_btn.count() == 0:
        # Profile already started — go straight to wizard
        page.goto(f"{CF_PROFILE_URL}?page=1", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        return

    create_btn.first.wait_for(state="visible", timeout=30000)
    create_btn.first.click()
    page.wait_for_timeout(2000)

    if page.get_by_text(
        re.compile(r"Co-founder Matching Behavior Agreement", re.I)
    ).count():
        accept_behavior_agreement(page)


def complete_one(
    page: Page, cred: Credential, profile: ProfileData
) -> ProfileResult:
    finished_at = datetime.now(timezone.utc).isoformat()
    try:
        login(
            page,
            username=cred.username,
            password=cred.password,
            continue_url=EDIT_URL,
        )
        save_result = fill_profile_form(page, profile, cred.email)
        start_cofounder_profile(page)
        fill_cofounder_matching_profile(page, profile, cred.email)
        return ProfileResult(
            email=cred.email,
            username=cred.username,
            status="cofounder_profile_complete",
            message=f"Profile {save_result}; cofounder wizard filled",
            finished_at=finished_at,
        )
    except Exception as exc:  # noqa: BLE001
        return ProfileResult(
            email=cred.email,
            username=cred.username,
            status="profile_failed",
            message=str(exc),
            finished_at=finished_at,
        )


def write_results(results: list[ProfileResult], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"profile_results_{stamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        if not results:
            return path
        writer = csv.DictWriter(fh, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for row in results:
            writer.writerow(asdict(row))
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log in and complete Startup School profile (edit_sign_up)"
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS_PATH,
        help="Path to credentials.csv",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help="Path to profile.json",
    )
    parser.add_argument("--limit", type=int, default=0, help="First N accounts (0=all)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between accounts")
    parser.add_argument(
        "--status",
        default="submitted,profile_complete,cofounder_started,cofounder_agreed",
        help="Comma-separated statuses to process (empty = all)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = load_profile(args.profile)
    creds = load_credentials(args.credentials)
    if args.status:
        allowed = {s.strip() for s in args.status.split(",") if s.strip()}
        creds = [c for c in creds if c.status in allowed or not c.status]
    if args.limit > 0:
        creds = creds[: args.limit]

    if not creds:
        print("No matching credentials to process.")
        return 1

    settings = browser_settings()
    proxy_pool = get_proxy_pool()
    # YC login shows "Validation required" in headless; force headed.
    headless = settings["headless"]
    if headless:
        print("Note: forcing headed browser (YC login blocks headless).")
        headless = False

    results: list[ProfileResult] = []
    print(f"Loaded {len(creds)} credential(s)")
    print(f"Profile: {args.profile}")
    print(f"Target: {EDIT_URL}")
    if proxy_pool:
        print(f"Proxy enabled: {len(proxy_pool)} endpoint(s) from pool")
    else:
        print("Proxy disabled")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=settings["slow_mo"])

        def open_context():
            proxy = proxy_pool.next() if proxy_pool else None
            if proxy:
                print(f"  Using proxy {proxy.label()}")
            ctx = browser.new_context(**context_options(proxy))
            return ctx, ctx.new_page()

        context, page = open_context()

        for index, cred in enumerate(creds, start=1):
            print(f"[{index}/{len(creds)}] {cred.email} ({cred.username}) ...")
            result = complete_one(page, cred, profile)
            results.append(result)
            update_credential_status(cred.email, result.status, args.credentials)
            print(f"  -> {result.status}: {result.message}")

            context.close()
            if index < len(creds):
                time.sleep(args.delay)
                context, page = open_context()

        context.close()
        browser.close()

    out_path = write_results(results, ROOT / "output")
    print(f"\nResults written to {out_path}")
    print("credentials.csv status column updated")
    failed = sum(1 for r in results if r.status == "profile_failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
