"""Open signup form and fill fields without submitting."""

from playwright.sync_api import sync_playwright

from src.config import load_email_targets, random_username
from src.signup import fill_by_label, open_signup_form

target = load_email_targets()[0]
username = target.username or random_username()
password = target.password
assert password, "Set PASSWORD in .env"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    open_signup_form(page)

    fill_by_label(page, "First Name", target.first_name)
    fill_by_label(page, "Last Name", target.last_name)
    fill_by_label(page, "Email", target.email)
    fill_by_label(page, "Username", username)
    fill_by_label(page, "Password", password)

    fill_by_label(page, "Your LinkedIn Profile URL", target.linkedin_url)

    values = page.locator("input").evaluate_all(
        "els => els.map(e => ({type: e.type, value: e.value}))"
    )
    print("Filled OK")
    print("username:", username)
    for row in values:
        if row["type"] == "password":
            print({"type": "password", "value": "***"})
        else:
            print(row)
    browser.close()
