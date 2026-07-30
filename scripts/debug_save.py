import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.auth import login
from src.complete_profile import fill_named, fill_profile_form
from src.profile_data import load_profile

ROOT = Path(__file__).resolve().parent.parent
cred = next(csv.DictReader((ROOT / "credentials.csv").open(encoding="utf-8-sig")))
profile = load_profile()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=40)
    page = browser.new_page()
    login(page, cred["username"], cred["password"])
    page.locator('[name="ssoUser.firstName"]').wait_for(state="visible", timeout=30000)

    try:
        fill_profile_form(page, profile, cred["email"])
        print("fill_profile_form OK")
    except Exception as exc:
        print("fill_profile_form ERROR:", exc)

    before = page.locator("body").inner_text()
    page.get_by_role("button", name=re.compile(r"^Save$")).click()
    page.wait_for_timeout(4000)
    after = page.locator("body").inner_text()
    Path("output/after_save.txt").write_text(after, encoding="utf-8")
    page.screenshot(path="output/after_save.png", full_page=True)

    # values after save
    vals = page.locator("input, textarea").evaluate_all(
        """els => els.filter(e => e.name).map(e => ({name:e.name, value:(e.value||'').slice(0,100), type:e.type}))"""
    )
    radios = page.locator('input[type=radio]').evaluate_all(
        "els => els.map(e => ({value:e.value, checked:e.checked}))"
    )
    Path("output/after_save.json").write_text(
        json.dumps({"vals": vals, "radios": radios, "url": page.url}, indent=2),
        encoding="utf-8",
    )
    print("URL", page.url)
    # print lines mentioning save/error/required
    for line in after.splitlines():
        low = line.lower()
        if any(k in low for k in ("save", "error", "required", "unsaved", "invalid", "character")):
            print(">", line)
    browser.close()
