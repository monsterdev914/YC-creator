"""Probe multi-select options on More About You / Preferences."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.auth import login

ROOT = Path(__file__).resolve().parent.parent
CREDS = ROOT / "credentials.csv"
BASE = "https://www.startupschool.org/cofounder-matching/profile?page=2"

cred = next(csv.DictReader(CREDS.open(encoding="utf-8-sig")))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()
    login(page, cred["username"], cred["password"], continue_url=BASE)
    page.wait_for_timeout(2500)
    if "page=2" not in page.url:
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

    # Click More About You tab
    tab = page.get_by_text("More About You", exact=True)
    if tab.count():
        tab.first.click()
        page.wait_for_timeout(1000)

    results = {}
    for label in [
        "Which areas of a startup are you willing to take responsibility for?",
        "Which topics and industries are you interested in?",
    ]:
        heading = page.get_by_text(label, exact=False).first
        heading.scroll_into_view_if_needed()
        # Find nearby combobox / input
        container = heading.locator("xpath=ancestor::div[.//input][1]")
        trigger = container.locator(
            "input, [role='combobox'], .MuiSelect-select, [aria-haspopup='listbox']"
        ).first
        trigger.click()
        page.wait_for_timeout(800)
        options = page.locator(
            '[role="option"], li[role="option"], .MuiAutocomplete-option, .MuiMenuItem-root'
        ).all_inner_texts()
        results[label] = options
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    # Preferences page multi-select
    page.goto("https://www.startupschool.org/cofounder-matching/profile?page=3")
    page.wait_for_timeout(2000)
    for label in [
        "Which areas would you like a co-founder to take responsibility for?",
    ]:
        heading = page.get_by_text(label, exact=False).first
        heading.scroll_into_view_if_needed()
        container = heading.locator("xpath=ancestor::div[.//input][1]")
        trigger = container.locator(
            "input, [role='combobox'], .MuiSelect-select, [aria-haspopup='listbox']"
        ).first
        trigger.click()
        page.wait_for_timeout(800)
        options = page.locator(
            '[role="option"], li[role="option"], .MuiAutocomplete-option, .MuiMenuItem-root'
        ).all_inner_texts()
        results[label] = options
        page.keyboard.press("Escape")

    Path("output/cf_multiselect.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    print(json.dumps(results, indent=2, ensure_ascii=True)[:4000])
    browser.close()
