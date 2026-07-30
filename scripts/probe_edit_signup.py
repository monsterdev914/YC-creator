"""Log in and dump the edit_sign_up form structure."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CREDS = ROOT / "credentials.csv"
EDIT_URL = "https://www.startupschool.org/users/edit_sign_up"
LOGIN_URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fsign_in"
)


def load_first_cred():
    with CREDS.open(encoding="utf-8-sig", newline="") as fh:
        row = next(csv.DictReader(fh))
    return row


def main() -> None:
    cred = load_first_cred()
    print("Using", cred["email"], cred["username"])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(LOGIN_URL, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Login form: username/email then continue, then password
        body = page.locator("body").inner_text()
        print("LOGIN BODY SNIP:\n", body[:600])

        # Try username-or-email field
        user_field = page.get_by_label(re.compile(r"Username or email", re.I))
        if user_field.count() == 0:
            user_field = page.locator("input").first
        user_field.fill(cred["username"])

        cont = page.get_by_role("button", name=re.compile(r"Continue", re.I))
        if cont.count():
            cont.first.click()
            page.wait_for_timeout(1500)

        pwd = page.locator("#password-input")
        if pwd.count() == 0:
            pwd = page.get_by_label(re.compile(r"Password", re.I))
        pwd.first.fill(cred["password"])

        # Sign in / Continue / Log in
        for name in (r"Log in", r"Sign in", r"Continue", r"Submit"):
            btn = page.get_by_role("button", name=re.compile(name, re.I))
            if btn.count():
                btn.first.click()
                break

        page.wait_for_timeout(4000)
        print("AFTER LOGIN URL:", page.url)
        print("AFTER LOGIN BODY:\n", page.locator("body").inner_text()[:800])

        page.goto(EDIT_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)
        print("EDIT URL:", page.url)
        print("EDIT TITLE:", page.title())
        text = page.locator("body").inner_text()
        print("EDIT BODY:\n", text[:4000])

        labels = page.locator("label").all_inner_texts()
        print("LABELS:", labels[:80])

        inputs = page.locator("input, textarea, select").evaluate_all(
            """els => els.map(e => ({
                tag: e.tagName,
                type: e.type || '',
                name: e.name,
                id: e.id,
                placeholder: e.placeholder,
                aria: e.getAttribute('aria-label'),
                value: (e.value || '').slice(0, 80)
            }))"""
        )
        print("FIELDS:")
        for item in inputs:
            print(item)

        buttons = page.get_by_role("button").all_inner_texts()
        print("BUTTONS:", buttons[:40])

        # Save a screenshot + HTML for offline inspection
        out = ROOT / "output"
        out.mkdir(exist_ok=True)
        page.screenshot(path=str(out / "edit_sign_up.png"), full_page=True)
        (out / "edit_sign_up.html").write_text(page.content(), encoding="utf-8")
        print("Saved output/edit_sign_up.png and .html")

        browser.close()


if __name__ == "__main__":
    main()
