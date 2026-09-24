from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .config import (
    DEFAULT_EMAILS_PATH,
    ROOT,
    SIGNUP_URL,
    AccountTarget,
    browser_settings,
    load_email_targets,
    random_username,
    update_email_statuses,
)
from .credentials_io import (
    DEFAULT_CREDENTIALS_PATH,
    find_credential,
    upsert_credentials,
)
from .proxy import context_options, get_proxy_pool

CREDENTIALS_PATH = DEFAULT_CREDENTIALS_PATH


class EmailAlreadyRegisteredError(Exception):
    """Continue led to login instead of the signup form."""


@dataclass
class SignupResult:
    email: str
    username: str
    password: str
    first_name: str
    last_name: str
    linkedin_url: str
    status: str
    message: str
    finished_at: str


def field_for_label(page: Page, label: str):
    """
    Resolve an input for a label.

    YC's form only wires `for=` on Username/Password; other fields are
    sibling inputs under `.input-group`, so get_by_label is not enough.
    """
    by_label = page.get_by_label(label, exact=False)
    if by_label.count() > 0:
        return by_label.first

    group = page.locator(".input-group").filter(
        has=page.locator("label", has_text=label)
    )
    return group.locator("input").first


def fill_by_label(page: Page, label: str, value: str) -> None:
    field = field_for_label(page, label)
    field.wait_for(state="visible", timeout=15000)
    field.click()
    field.fill("")
    field.fill(value)


def open_signup_form(page: Page, email: str) -> None:
    page.goto(SIGNUP_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(500)

    # YC now uses email-first: enter email → Continue → signup form for new users.
    email_field = page.locator("#ycid-input").first
    email_field.wait_for(state="visible", timeout=20000)
    email_field.fill(email)
    page.get_by_role("button", name=re.compile(r"Continue", re.I)).click()

    first_name = field_for_label(page, "First Name")
    signup_btn = page.get_by_role("button", name=re.compile(r"Sign\s*[Uu]p", re.I))
    password_field = page.locator("#password-input")

    try:
        first_name.wait_for(state="visible", timeout=15000)
        signup_btn.wait_for(state="visible", timeout=5000)
        return
    except PlaywrightTimeoutError:
        pass

    if password_field.is_visible() and first_name.count() == 0:
        raise EmailAlreadyRegisteredError(
            f"{email} already has an account; run profile flow instead of signup"
        )

    raise PlaywrightTimeoutError(
        "Expected signup form after Continue; got an unknown page state"
    )


def _result(
    target: AccountTarget,
    username: str,
    password: str,
    status: str,
    message: str,
    finished_at: str,
) -> SignupResult:
    return SignupResult(
        email=target.email,
        username=username,
        password=password,
        first_name=target.first_name,
        last_name=target.last_name,
        linkedin_url=target.linkedin_url,
        status=status,
        message=message,
        finished_at=finished_at,
    )


def signup_one(page: Page, target: AccountTarget) -> SignupResult:
    username = target.username or random_username()
    if not target.password:
        raise ValueError(f"No password set for {target.email}; set PASSWORD in .env")
    password = target.password
    finished_at = datetime.now(timezone.utc).isoformat()

    try:
        open_signup_form(page, target.email)
    except EmailAlreadyRegisteredError as exc:
        existing = find_credential(target.email)
        if existing:
            if existing.get("username"):
                username = existing["username"]
            prior_status = (existing.get("status") or "").strip().lower()
            if prior_status in {
                "submitted",
                "profile_complete",
                "cofounder_started",
                "cofounder_agreed",
                "cofounder_profile_complete",
            }:
                return _result(
                    target,
                    username,
                    password,
                    prior_status,
                    f"{target.email} already signed up",
                    finished_at,
                )
        return _result(
            target, username, password, "already_registered", str(exc), finished_at
        )

    try:
        fill_by_label(page, "First Name", target.first_name)
        fill_by_label(page, "Last Name", target.last_name)
        fill_by_label(page, "Email", target.email)
        fill_by_label(page, "Username", username)
        fill_by_label(page, "Password", password)

        fill_by_label(page, "Your LinkedIn Profile URL", target.linkedin_url)

        signup_btn = page.get_by_role("button", name=re.compile(r"Sign\s*[Uu]p", re.I))
        signup_btn.click()

        # Success heuristics: leave signup form, or show a clear confirmation.
        try:
            signup_btn.wait_for(state="hidden", timeout=20000)
        except PlaywrightTimeoutError:
            # Still on form — capture any visible validation/error text.
            body = page.locator("body").inner_text(timeout=3000)
            lowered = body.lower()
            for needle in (
                "already taken",
                "already exists",
                "invalid",
                "required",
                "error",
                "try again",
            ):
                if needle in lowered:
                    return _result(
                        target,
                        username,
                        password,
                        "failed",
                        f"Signup rejected (matched: {needle})",
                        finished_at,
                    )
            return _result(
                target,
                username,
                password,
                "uncertain",
                "Sign up still visible; check browser for CAPTCHA/verification",
                finished_at,
            )

        return _result(
            target,
            username,
            password,
            "submitted",
            "Signup form submitted",
            finished_at,
        )
    except Exception as exc:  # noqa: BLE001 - surface per-account failures
        return _result(
            target, username, password, "error", str(exc), finished_at
        )


def write_credentials(results: list[SignupResult], path: Path = CREDENTIALS_PATH) -> Path:
    """Upsert account credentials into credentials.csv (one row per email)."""
    return upsert_credentials(
        [
            {
                "email": row.email,
                "username": row.username,
                "password": row.password,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "linkedin_url": row.linkedin_url,
                "status": row.status,
                "created_at": row.finished_at,
            }
            for row in results
        ],
        path,
    )


def write_results(results: list[SignupResult], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"signup_results_{stamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(results[0]).keys()) if results else [])
        if results:
            writer.writeheader()
            for row in results:
                writer.writerow(asdict(row))
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate YC Account / Startup School signup"
    )
    parser.add_argument(
        "--emails",
        type=Path,
        default=DEFAULT_EMAILS_PATH,
        help="Path to emails.csv (one email per line, or an email column)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N emails (0 = all)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between accounts",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = load_email_targets(args.emails)
    if args.limit > 0:
        targets = targets[: args.limit]

    settings = browser_settings()
    proxy_pool = get_proxy_pool()
    results: list[SignupResult] = []

    print(f"Loaded {len(targets)} account target(s)")
    print(f"Signup URL: {SIGNUP_URL}")
    if proxy_pool:
        print(f"Proxy enabled: {len(proxy_pool)} endpoint(s) from pool")
    else:
        print("Proxy disabled")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=settings["headless"],
            slow_mo=settings["slow_mo"],
        )

        def open_context():
            proxy = proxy_pool.next() if proxy_pool else None
            if proxy:
                print(f"  Using proxy {proxy.label()}")
            ctx = browser.new_context(**context_options(proxy))
            return ctx, ctx.new_page()

        context, page = open_context()

        for index, target in enumerate(targets, start=1):
            print(f"[{index}/{len(targets)}] Signing up {target.email} ...")
            result = signup_one(page, target)
            results.append(result)
            print(f"  -> {result.status}: {result.message}")

            # Fresh context reduces session bleed between accounts.
            context.close()
            if index < len(targets):
                time.sleep(args.delay)
                context, page = open_context()

        context.close()
        browser.close()

    creds_path = write_credentials(results)
    out_path = write_results(results, ROOT / "output")
    email_path = update_email_statuses(
        {row.email: row.status for row in results}, args.emails
    )
    print(f"\nCredentials written to {creds_path}")
    print(f"Email statuses written to {email_path}")
    print(f"Run log written to {out_path}")
    for row in results:
        print(f"  {row.email} | {row.username} | {row.password} | {row.status}")
    failed = sum(1 for r in results if r.status in {"failed", "error"})
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
