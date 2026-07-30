import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from src.auth import login

ROOT = Path(__file__).resolve().parent.parent
cred = next(csv.DictReader((ROOT / "credentials.csv").open(encoding="utf-8-sig")))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    login(page, cred["username"], cred["password"])
    page.locator('[name="ssoUser.firstName"]').wait_for(state="visible")

    gender = page.locator('[name="gender"]')
    print("gender tag", gender.evaluate("e => ({tag:e.tagName, role:e.getAttribute('role'), list:e.getAttribute('aria-haspopup'), outer:e.outerHTML.slice(0,400)})"))
    gender.click()
    page.wait_for_timeout(500)
    opts = page.locator('[role="option"], li, [role="listbox"] *').all_inner_texts()
    print("options after gender click", opts[:40])
    page.keyboard.press("Escape")

    hear = page.get_by_text("How did you first hear about Startup School?")
    # find nearby input
    box = page.locator("input").nth(-4)
    info = page.locator("body").evaluate(
        """() => {
          const labels = [...document.querySelectorAll('label,div,p,span')].filter(e => (e.textContent||'').includes('How did you first hear'));
          return labels.slice(0,3).map(e => ({tag:e.tagName, html:e.outerHTML.slice(0,300), next: (e.parentElement&&e.parentElement.innerHTML||'').slice(0,500)}));
        }"""
    )
    Path("output/selects.json").write_text(json.dumps(info, indent=2)[:5000], encoding="utf-8")
    print(json.dumps(info, indent=2)[:2000])
    browser.close()
