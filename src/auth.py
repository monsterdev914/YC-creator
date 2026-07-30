from __future__ import annotations

import re

from playwright.sync_api import Page

LOGIN_URL_TEMPLATE = (
    "https://account.ycombinator.com/?continue={continue_url}"
)


def login(
    page: Page,
    username: str,
    password: str,
    continue_url: str = "https://www.startupschool.org/users/edit_sign_up",
) -> None:
    """Sign in via YC account and land on the continue URL."""
    from urllib.parse import quote

    url = LOGIN_URL_TEMPLATE.format(continue_url=quote(continue_url, safe=""))
    page.goto(url, wait_until="domcontentloaded")
    page.locator("#ycid-input").wait_for(state="visible", timeout=20000)
    page.locator("#ycid-input").fill(username)

    page.get_by_role("button", name=re.compile(r"Continue", re.I)).click()
    page.locator("#password-input").wait_for(state="visible", timeout=20000)
    page.locator("#password-input").fill(password)
    page.get_by_role("button", name=re.compile(r"Log.?In", re.I)).click()

    page.wait_for_url(re.compile(r"startupschool\.org"), timeout=90000)
    page.wait_for_load_state("domcontentloaded")
