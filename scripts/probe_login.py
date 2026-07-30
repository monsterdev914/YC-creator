"""Debug login step-by-step (headed)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CREDS = ROOT / "credentials.csv"
LOGIN_URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fedit_sign_up"
)


def load_first_cred():
    with CREDS.open(encoding="utf-8-sig", newline="") as fh:
        return next(csv.DictReader(fh))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    context = browser.new_context()
    page = context.new_page()
    page.goto(LOGIN_URL, wait_until="networkidle")
    page.wait_for_timeout(2000)

    cred = load_first_cred()
    page.locator("#ycid-input").fill(cred["username"])
    page.get_by_role("button", name=re.compile(r"Continue", re.I)).click()
    page.wait_for_timeout(2500)
    print("STEP2 BODY:\n", page.locator("body").inner_text()[:1000])
    print("IFRAMES:", page.locator("iframe").evaluate_all("els => els.map(e => e.src)"))

    # Dump any captcha / challenge nodes
    html = page.content()
    for needle in ("captcha", "hcaptcha", "recaptcha", "cf-turnstile", "turnstile", "Validation"):
        print(needle, "->", needle.lower() in html.lower())

    page.locator("#password-input").fill(cred["password"])
    page.get_by_role("button", name=re.compile(r"Log.?In", re.I)).click()
    page.wait_for_timeout(8000)
    print("FINAL URL:", page.url)
    print("FINAL BODY:\n", page.locator("body").inner_text()[:1500])
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    page.screenshot(path=str(out / "login_debug.png"), full_page=True)
    (out / "login_debug.html").write_text(page.content(), encoding="utf-8")
    browser.close()
