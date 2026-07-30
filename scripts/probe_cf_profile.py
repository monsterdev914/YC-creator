"""Probe cofounder matching profile pages 1-3."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.auth import login

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CREDS = ROOT / "credentials.csv"
BASE = "https://www.startupschool.org/cofounder-matching/profile"


def dump_page(page, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    info = {
        "url": page.url,
        "body": page.locator("body").inner_text()[:6000],
        "labels": page.locator("label").all_inner_texts()[:80],
        "buttons": page.get_by_role("button").all_inner_texts()[:40],
        "fields": page.locator("input, textarea, select").evaluate_all(
            """els => els.map(e => ({
                tag: e.tagName, type: e.type || '', name: e.name, id: e.id,
                placeholder: (e.placeholder || '').slice(0,120),
                value: (e.value || '').slice(0,120),
                aria: e.getAttribute('aria-label')
            }))"""
        ),
        "radios": page.locator('input[type=radio]').evaluate_all(
            """els => els.map((e,i) => {
                const label = e.closest('label');
                const text = (label && label.innerText || e.parentElement && e.parentElement.innerText || '').trim().slice(0,160);
                return {i, value:e.value, checked:e.checked, text};
            })"""
        ),
    }
    (OUT / f"{name}.json").write_text(
        json.dumps(info, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    print(name, page.url, "fields", len(info["fields"]), "radios", len(info["radios"]))


cred = next(csv.DictReader(CREDS.open(encoding="utf-8-sig")))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=40)
    page = browser.new_page()
    login(
        page,
        cred["username"],
        cred["password"],
        continue_url=f"{BASE}?page=1",
    )
    page.wait_for_timeout(2000)
    if "profile" not in page.url:
        page.goto(f"{BASE}?page=1", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
    dump_page(page, "cf_page1")

    # try tab navigation
    for tab, fname in [
        ("More About You", "cf_page2"),
        ("Co-Founder Preferences", "cf_page3"),
    ]:
        link = page.get_by_text(tab, exact=False)
        if link.count():
            link.first.click()
            page.wait_for_timeout(2000)
        else:
            page_num = 2 if "More" in tab else 3
            page.goto(f"{BASE}?page={page_num}", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
        dump_page(page, fname)

    browser.close()
