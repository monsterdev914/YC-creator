import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from src.auth import login

cred = next(csv.DictReader(Path("credentials.csv").open(encoding="utf-8-sig")))

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
    page.get_by_text("Co-Founder Preferences", exact=True).first.click()
    page.wait_for_timeout(1000)

    labels = page.get_by_text("How important is this to you?", exact=False)
    print("importance labels", labels.count())
    info = []
    for i in range(labels.count()):
        lab = labels.nth(i)
        lab.scroll_into_view_if_needed()
        parent = lab.locator("xpath=ancestor::div[1]")
        html = parent.evaluate("e => e.outerHTML.slice(0,500)")
        # sibling selects
        selects = lab.locator(
            "xpath=following::div[contains(@class,'MuiSelect-select') or @role='combobox' or @aria-haspopup='listbox'][1]"
        )
        print(i, "select count", selects.count())
        if selects.count():
            selects.first.click()
            page.wait_for_timeout(500)
            opts = page.locator('[role="option"], .MuiMenuItem-root, li').all_inner_texts()
            print(" opts", opts[:10])
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            info.append({"i": i, "opts": opts[:10], "html": html})
    Path("output/importance.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    browser.close()
