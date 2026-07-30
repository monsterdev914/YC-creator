import csv
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.auth import login
from src.cofounder_profile import fill_cofounder_preferences, save_and_continue
from src.profile_data import load_profile

cred = next(csv.DictReader(Path("credentials.csv").open(encoding="utf-8-sig")))
# reset status manually not needed
profile = load_profile()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=40)
    page = browser.new_page()
    login(
        page,
        cred["username"],
        cred["password"],
        continue_url="https://www.startupschool.org/cofounder-matching/profile?page=3",
    )
    page.wait_for_timeout(2000)
    try:
        fill_cofounder_preferences(page, profile)
        print("OK", page.url)
    except Exception as exc:
        print("ERR", exc)
        print("URL", page.url)
        print("BUTTONS", page.get_by_role("button").all_inner_texts())
        Path("output/prefs_err.txt").write_text(
            page.locator("body").inner_text(), encoding="utf-8"
        )
        page.screenshot(path="output/prefs_err.png", full_page=True)
    browser.close()
