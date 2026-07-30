import csv
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.auth import login
from src.cofounder_profile import fill_more_about_you, click_tab
from src.profile_data import load_profile

cred = next(csv.DictReader(Path("credentials.csv").open(encoding="utf-8-sig")))
profile = load_profile()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=40)
    page = browser.new_page()
    login(
        page,
        cred["username"],
        cred["password"],
        continue_url="https://www.startupschool.org/cofounder-matching/profile?page=2",
    )
    page.wait_for_timeout(2000)
    try:
        fill_more_about_you(page, profile)
        print("OK")
    except Exception as exc:
        print("ERR", exc)
        Path("output/more_about_err.txt").write_text(
            page.locator("body").inner_text(), encoding="utf-8"
        )
        page.screenshot(path="output/more_about_err.png", full_page=True)
        print("saved output/more_about_err.*")
    browser.close()
