from playwright.sync_api import sync_playwright

URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fsign_in"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL, wait_until="networkidle")
    page.get_by_role("button", name="Create an account").click()
    page.wait_for_timeout(2000)

    html = page.locator("form, main, body").first.inner_html()
    print(html[:5000])

    for label in [
        "First Name",
        "Last Name",
        "Email",
        "Username",
        "Password",
        "Your LinkedIn Profile URL",
    ]:
        by_label = page.get_by_label(label, exact=False)
        print(label, "get_by_label count=", by_label.count())

    # Try label -> following input
    for label in ["First Name", "Email"]:
        loc = page.locator("label", has_text=label)
        print(label, "label outer", loc.first.evaluate("e => e.outerHTML"))
        sibling = loc.locator("xpath=following::input[1]")
        print(" following input count", sibling.count())

    browser.close()
