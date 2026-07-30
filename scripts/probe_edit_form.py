"""Log in (headed) and dump edit_sign_up fields to JSON."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CREDS = ROOT / "credentials.csv"
LOGIN_URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fedit_sign_up"
)
EDIT_URL = "https://www.startupschool.org/users/edit_sign_up"


def load_first_cred():
    with CREDS.open(encoding="utf-8-sig", newline="") as fh:
        return next(csv.DictReader(fh))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()
    cred = load_first_cred()

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.locator("#ycid-input").fill(cred["username"])
    page.get_by_role("button", name=re.compile(r"Continue", re.I)).click()
    page.locator("#password-input").wait_for(state="visible", timeout=20000)
    page.locator("#password-input").fill(cred["password"])
    page.get_by_role("button", name=re.compile(r"Log.?In", re.I)).click()
    page.wait_for_url(re.compile(r"startupschool\.org"), timeout=60000)

    if "edit_sign_up" not in page.url:
        page.goto(EDIT_URL, wait_until="networkidle")
    page.wait_for_timeout(3000)

    OUT.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT / "edit_form.png"), full_page=True)
    (OUT / "edit_form.html").write_text(page.content(), encoding="utf-8")

    info = {
        "url": page.url,
        "title": page.title(),
        "body_text": page.locator("body").inner_text(),
        "labels": page.locator("label").all_inner_texts(),
        "buttons": page.get_by_role("button").all_inner_texts(),
        "links": page.get_by_role("link").all_inner_texts()[:40],
        "fields": page.locator("input, textarea, select").evaluate_all(
            """els => els.map(e => ({
                tag: e.tagName,
                type: e.type || '',
                name: e.name,
                id: e.id,
                placeholder: e.placeholder,
                aria: e.getAttribute('aria-label'),
                role: e.getAttribute('role'),
                value: (e.value || '').slice(0, 120)
            }))"""
        ),
    }
    (OUT / "edit_form.json").write_text(
        json.dumps(info, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    print("saved", OUT / "edit_form.json")
    print("url", info["url"])
    print("labels", len(info["labels"]), "fields", len(info["fields"]))
    browser.close()
