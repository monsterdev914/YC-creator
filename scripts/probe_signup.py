from playwright.sync_api import sync_playwright

URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fsign_in"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(2000)

    el = page.get_by_text("Create an account", exact=False)
    print("text count", el.count())
    for i in range(el.count()):
        info = el.nth(i).evaluate(
            """e => ({
                tag: e.tagName,
                role: e.getAttribute('role'),
                href: e.getAttribute('href'),
                className: e.className,
                type: e.getAttribute('type'),
                outer: e.outerHTML.slice(0, 400)
            })"""
        )
        print(i, info)

    el.first.click()
    page.wait_for_timeout(2500)
    print("URL", page.url)
    print("BODY", page.locator("body").inner_text()[:1500])
    print("LABELS", page.locator("label").all_inner_texts())
    inputs = page.locator("input").evaluate_all(
        """els => els.map(e => ({
            type: e.type,
            name: e.name,
            id: e.id,
            placeholder: e.placeholder,
            aria: e.getAttribute('aria-label'),
            autocomplete: e.autocomplete
        }))"""
    )
    print("INPUTS", inputs)
    print("BUTTONS", page.get_by_role("button").all_inner_texts())
    browser.close()
