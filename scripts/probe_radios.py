import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CREDS = ROOT / "credentials.csv"
LOGIN_URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fedit_sign_up"
)

cred = next(csv.DictReader(CREDS.open(encoding="utf-8-sig")))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(LOGIN_URL, wait_until="networkidle")
    page.locator("#ycid-input").fill(cred["username"])
    page.get_by_role("button", name=re.compile(r"Continue", re.I)).click()
    page.locator("#password-input").fill(cred["password"])
    page.get_by_role("button", name=re.compile(r"Log.?In", re.I)).click()
    page.wait_for_url(re.compile(r"startupschool\.org"), timeout=60000)
    page.wait_for_load_state("networkidle")
    page.locator('[name="ssoUser.firstName"]').wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(1000)

    radios = page.locator('input[type="radio"]').evaluate_all(
        """els => els.map((e, i) => {
            const label = e.closest('label') || e.parentElement;
            const text = (label && label.innerText || '').trim().slice(0, 80);
            let parent = e.parentElement;
            let context = '';
            for (let n=0; n<6 && parent; n++) {
                const t = (parent.innerText || '').trim().split('\\n')[0];
                if (t && t.length > 10) { context = t.slice(0, 120); break; }
                parent = parent.parentElement;
            }
            return {i, value: e.value, text, context, checked: e.checked};
        })"""
    )
    Path("output/radios.json").write_text(json.dumps(radios, indent=2), encoding="utf-8")
    print(json.dumps(radios, indent=2))
    browser.close()
