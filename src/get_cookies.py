"""Log into YC accounts from credentials.csv and export SSO cookies for profile-web-scraper."""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

from .auth import login
from .config import ROOT, browser_settings
from .credentials_io import load_credentials
from .proxy import context_options, get_proxy_pool

SSO_COOKIE = "_sso.key"
SESSION_COOKIE = "_bf_session_key"
CONTINUE_URL = "https://www.startupschool.org/cofounder-matching/dashboard"
DEFAULT_OUT = ROOT / "cookies_export.csv"

COOKIE_CSV_FIELDS = ["label", "ssoKey", "susSession", "email", "status", "error"]


@dataclass
class CookieRow:
    label: str
    sso_key: str
    sus_session: str
    email: str
    status: str
    error: str = ""


def _cookie_map(context, urls: list[str] | None = None) -> dict[str, str]:
    cookies = context.cookies(urls) if urls else context.cookies()
    return {c["name"]: c["value"] for c in cookies if c.get("name") and c.get("value")}


def extract_sso_cookies(context) -> tuple[str, str]:
    """Return (_sso.key, _sus_session) from the browser context."""
    # Prefer Startup School + account domains; fall back to all cookies.
    by_name = _cookie_map(
        context,
        [
            "https://www.startupschool.org",
            "https://startupschool.org",
            "https://account.ycombinator.com",
            "https://www.ycombinator.com",
        ],
    )
    if SSO_COOKIE not in by_name or SESSION_COOKIE not in by_name:
        by_name = {**by_name, **_cookie_map(context)}

    sso = (by_name.get(SSO_COOKIE) or "").strip()
    session = (by_name.get(SESSION_COOKIE) or "").strip()
    if not sso or not session:
        missing = [
            name
            for name, val in ((SSO_COOKIE, sso), (SESSION_COOKIE, session))
            if not val
        ]
        raise RuntimeError(f"Missing cookie(s): {', '.join(missing)}")
    return sso, session


def harvest_one(
    browser,
    *,
    username: str,
    password: str,
    email: str,
    proxy=None,
) -> CookieRow:
    label = email.strip()
    ctx = browser.new_context(**context_options(proxy))
    page = ctx.new_page()
    try:
        login(page, username, password, continue_url=CONTINUE_URL)
        # Ensure Startup School cookies are set after redirects settle.
        page.wait_for_timeout(1500)
        if "startupschool.org" not in (page.url or ""):
            page.goto(CONTINUE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

        sso_key, sus_session = extract_sso_cookies(ctx)
        return CookieRow(
            label=label,
            sso_key=sso_key,
            sus_session=sus_session,
            email=label,
            status="ok",
        )
    except Exception as exc:  # noqa: BLE001 — per-account isolation
        return CookieRow(
            label=label,
            sso_key="",
            sus_session="",
            email=label,
            status="failed",
            error=str(exc),
        )
    finally:
        ctx.close()


def write_cookies_csv(path: Path, rows: list[CookieRow], *, ok_only: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out_rows = [r for r in rows if r.status == "ok"] if ok_only else rows
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COOKIE_CSV_FIELDS)
        writer.writeheader()
        for row in out_rows:
            writer.writerow(
                {
                    "label": row.label,
                    "ssoKey": row.sso_key,
                    "susSession": row.sus_session,
                    "email": row.email,
                    "status": row.status,
                    "error": row.error,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Log into accounts from credentials.csv and export "
            "_sso.key / _sus_session for profile-web-scraper cookie import."
        )
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=ROOT / "credentials.csv",
        help="Path to credentials.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output CSV path (default: cookies_export.csv)",
    )
    parser.add_argument("--limit", type=int, default=0, help="First N accounts (0=all)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between accounts")
    parser.add_argument(
        "--status",
        default="cofounder_profile_complete",
        help="Comma-separated statuses to process (empty = all)",
    )
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Include failed rows in the output CSV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    headless = settings["headless"]
    if headless:
        print("Note: forcing headed browser (YC login blocks headless).")
        headless = False

    print(f"Loaded {len(creds)} credential(s)")
    print(f"Credentials: {args.credentials}")
    print(f"Output: {args.out}")
    if proxy_pool:
        print(f"Proxy enabled: {len(proxy_pool)} endpoint(s)")
    else:
        print("Proxy disabled")

    results: list[CookieRow] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=settings["slow_mo"])
        try:
            for i, cred in enumerate(creds, start=1):
                print(f"[{i}/{len(creds)}] {cred.email} …", flush=True)
                proxy = proxy_pool.next() if proxy_pool else None
                if proxy:
                    print(f"  Using proxy {proxy.label()}")
                row = harvest_one(
                    browser,
                    username=cred.username,
                    password=cred.password,
                    email=cred.email,
                    proxy=proxy,
                )
                results.append(row)
                if row.status == "ok":
                    print(f"  OK — cookies captured (label={row.label})")
                else:
                    print(f"  FAILED — {row.error}")
                if i < len(creds) and args.delay > 0:
                    time.sleep(args.delay)
        finally:
            browser.close()

    write_cookies_csv(args.out, results, ok_only=not args.include_failed)
    ok = sum(1 for r in results if r.status == "ok")
    failed = len(results) - ok
    print(f"\nDone: {ok} ok, {failed} failed → {args.out}")
    print(
        "Import this CSV on the profile-web-scraper Cookies page "
        "(label = email automatically)."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
