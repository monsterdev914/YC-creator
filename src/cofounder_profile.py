from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page

from .profile_data import ProfileData

CF_PROFILE_URL = "https://www.startupschool.org/cofounder-matching/profile"


def fill_named(page: Page, name: str, value: str) -> None:
    field = page.locator(f'[name="{name}"]').first
    field.wait_for(state="visible", timeout=20000)
    field.scroll_into_view_if_needed()
    field.click()
    field.fill("")
    field.fill(value)


def click_tab(page: Page, tab_name: str) -> None:
    tab = page.get_by_text(tab_name, exact=True)
    if tab.count() == 0:
        tab = page.get_by_text(tab_name, exact=False)
    tab.first.scroll_into_view_if_needed()
    tab.first.click()
    page.wait_for_timeout(1000)


def click_radio_by_text(page: Page, option_text: str) -> None:
    option = page.get_by_text(option_text, exact=True)
    if option.count() == 0:
        option = page.get_by_text(option_text, exact=False)
    option.first.scroll_into_view_if_needed()
    option.first.click()
    page.wait_for_timeout(200)


def click_radio_value_near_question(
    page: Page, question: str, value: str
) -> None:
    """Click a radio with a known value under a question heading."""
    heading = page.get_by_text(question, exact=False).first
    heading.scroll_into_view_if_needed()
    block = heading.locator(
        "xpath=ancestor::div[.//input[@type='radio']][1]"
    )
    radio = block.locator(f'input[type="radio"][value="{value}"]').first
    if radio.count():
        radio.check()
    else:
        # fallback: click label text if value mapping differs
        page.locator(f'input[type="radio"][value="{value}"]').first.check()


def select_importance_near_question(
    page: Page, question: str, importance: str
) -> None:
    heading = page.get_by_text(question, exact=False).first
    heading.scroll_into_view_if_needed()
    trigger = heading.locator(
        "xpath=following::*[contains(normalize-space(.),'How important is this to you')]"
        "/following::div[contains(@class,'MuiSelect-select') or @role='combobox' or @aria-haspopup='listbox'][1]"
    ).first
    if trigger.count() == 0:
        trigger = heading.locator(
            "xpath=following::div[contains(@class,'MuiSelect-select')][1]"
        ).first
    if trigger.count() == 0:
        print(f"  warn: no importance dropdown for: {question[:48]}")
        return
    trigger.click()
    page.wait_for_timeout(500)
    opt = page.get_by_role(
        "option", name=re.compile(rf"^{re.escape(importance)}$", re.I)
    )
    if opt.count() == 0:
        opt = page.locator(".MuiMenuItem-root, [role='option'], li").filter(
            has_text=re.compile(rf"^{re.escape(importance)}$", re.I)
        )
    if opt.count() == 0:
        page.keyboard.press("Escape")
        print(f"  warn: importance option not found: {importance}")
        return
    opt.first.click()
    page.wait_for_timeout(300)


def open_multiselect_near_label(page: Page, label: str):
    heading = page.get_by_text(label, exact=False).first
    heading.scroll_into_view_if_needed()
    container = heading.locator("xpath=ancestor::div[.//input][1]")
    trigger = container.locator(
        "input, [role='combobox'], .MuiSelect-select, [aria-haspopup='listbox']"
    ).first
    trigger.click()
    page.wait_for_timeout(500)
    return trigger


def _option_selected(opt) -> bool:
    aria = (opt.get_attribute("aria-selected") or "").lower()
    cls = opt.get_attribute("class") or ""
    return aria == "true" or "Mui-selected" in cls


def _option_label(opt) -> str:
    try:
        text = (opt.inner_text() or "").strip()
    except Exception:
        text = ""
    if not text:
        text = (opt.get_attribute("data-value") or opt.get_attribute("aria-label") or "").strip()
    return text


def select_multiselect_options(page: Page, label: str, options: list[str]) -> None:
    """Sync multiselect to exactly ``options`` (select missing, deselect extras)."""
    wanted = {o.strip().lower() for o in options if o and str(o).strip()}
    open_multiselect_near_label(page, label)

    # Walk all options; MUI may re-render after each click so re-query each pass.
    for _ in range(30):
        opts = page.locator(
            '[role="option"], .MuiAutocomplete-option, .MuiMenuItem-root'
        )
        changed = False
        for i in range(opts.count()):
            opt = opts.nth(i)
            try:
                name = _option_label(opt)
                if not name:
                    continue
                should = name.strip().lower() in wanted
                selected = _option_selected(opt)
                if should != selected:
                    opt.click()
                    page.wait_for_timeout(150)
                    changed = True
                    break
            except Exception:
                continue
        if not changed:
            break

    # Also remove leftover chips/tags that are not in wanted (closed dropdown state).
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    _remove_unwanted_chips(page, label, wanted)


def _remove_unwanted_chips(page: Page, label: str, wanted: set[str]) -> None:
    """Click chip delete icons for values not in ``wanted``."""
    heading = page.get_by_text(label, exact=False).first
    try:
        heading.scroll_into_view_if_needed()
    except Exception:
        return
    container = heading.locator("xpath=ancestor::div[.//input][1]")
    for _ in range(20):
        chips = container.locator(
            ".MuiChip-root, [class*='Chip'], [data-tag-index], .MuiAutocomplete-tag"
        )
        removed = False
        for i in range(chips.count()):
            chip = chips.nth(i)
            try:
                text = (chip.inner_text() or "").strip().split("\n")[0].strip()
                if not text or text.strip().lower() in wanted:
                    continue
                delete_btn = chip.locator(
                    "svg, [class*='deleteIcon'], [aria-label*='Delete'], button"
                ).first
                if delete_btn.count():
                    delete_btn.click()
                else:
                    chip.click()
                page.wait_for_timeout(150)
                removed = True
                break
            except Exception:
                continue
        if not removed:
            break


def select_all_multiselect_options(page: Page, label: str) -> None:
    open_multiselect_near_label(page, label)
    # Re-query after each click; MUI autocomplete re-renders the list.
    for _ in range(40):
        options = page.locator('[role="option"], .MuiAutocomplete-option')
        clicked = False
        for i in range(options.count()):
            opt = options.nth(i)
            try:
                if not _option_selected(opt):
                    opt.click()
                    page.wait_for_timeout(120)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            break
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def _find_save_button(page: Page, patterns: list[str]):
    for pattern in patterns:
        btn = page.get_by_role("button", name=re.compile(pattern, re.I))
        if btn.count():
            return btn.first, pattern
        btn = page.get_by_text(re.compile(pattern, re.I))
        if btn.count():
            return btn.first, pattern
    return None, None


def save_and_continue(page: Page, *, final_step: bool = False) -> None:
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # Early steps use "Save & continue"; later/complete profiles use
    # "Save for later" / "Submit for review" on every tab.
    # On the final step prefer Submit — both buttons are often present, and
    # matching "Save for later" first would skip the actual submission.
    if final_step:
        patterns = [
            r"Submit for review",
            r"Save\s*&\s*continue",
            r"Save for later",
        ]
    else:
        patterns = [r"Save\s*&\s*continue", r"Save for later"]

    target, matched = _find_save_button(page, patterns)
    if target is None:
        raise RuntimeError(
            f"Save button not found on {page.url}; "
            f"buttons={page.get_by_role('button').all_inner_texts()[:20]}"
        )

    target.scroll_into_view_if_needed()
    target.wait_for(state="visible", timeout=20000)
    if not target.is_enabled():
        print(f"  {matched} disabled — skipping and refreshing")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        return

    print(f"  Clicking: {matched}")
    _click_save_button(page, target, matched, final_step=final_step)


def _click_save_button(
    page: Page, target, matched: str, *, final_step: bool
) -> None:
    """Click save/submit and verify it took effect; retry if needed."""
    submit_re = re.compile(r"Submit for review", re.I)

    for attempt in range(3):
        try:
            target.click(timeout=10000)
        except Exception:
            target.click(force=True, timeout=10000)

        page.wait_for_timeout(2500)
        body = page.locator("body").inner_text()
        lowered = body.lower()
        if "please fix" in lowered or "form errors" in lowered:
            lines = [
                line.strip()
                for line in body.splitlines()
                if line.strip()
                and any(
                    k in line.lower()
                    for k in ("please", "error", "required", "form", "invalid")
                )
            ]
            raise RuntimeError(
                "Save rejected with validation errors: " + " | ".join(lines[:6])
            )

        if not final_step:
            return

        # Final submit: succeed when the button is gone, disabled, or the page
        # shows a post-submit state (under review / submitted / etc.).
        still = page.get_by_role("button", name=submit_re)
        if (
            still.count() == 0
            or not still.first.is_visible()
            or not still.first.is_enabled()
        ):
            print("  Submit for review succeeded")
            return
        if any(
            phrase in lowered
            for phrase in (
                "under review",
                "submitted for review",
                "awaiting review",
                "profile is being reviewed",
            )
        ):
            print("  Submit for review succeeded")
            return

        if attempt < 2:
            print(f"  Submit did not stick (attempt {attempt + 1}), retrying...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            target, _ = _find_save_button(page, [r"Submit for review"])
            if target is None:
                print("  Submit button gone after retry lookup — treating as success")
                return
            target.scroll_into_view_if_needed()

    raise RuntimeError(
        "Submit for review clicked but page still shows the button; "
        f"url={page.url}"
    )



def upload_avatar(page: Page, avatar_path: Path) -> None:
    if not avatar_path.exists():
        raise FileNotFoundError(f"Avatar not found: {avatar_path}")
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(str(avatar_path))
    page.wait_for_timeout(1500)


def fill_basics(page: Page, profile: ProfileData, email: str) -> None:
    page.goto(f"{CF_PROFILE_URL}?page=1", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    click_tab(page, "Basics")
    page.locator('[name="ssoUser.firstName"]').wait_for(state="visible", timeout=30000)

    upload_avatar(page, profile.avatar_path)

    fill_named(page, "ssoUser.firstName", profile.first_name)
    fill_named(page, "ssoUser.lastName", profile.last_name)
    if page.locator('[name="ssoUser.email"]').input_value().strip() != email:
        fill_named(page, "ssoUser.email", email)
    fill_named(page, "ssoUser.linkedin", profile.linkedin_url)
    fill_named(page, "currentUser.location", profile.location)
    fill_named(
        page,
        "cofounderMatching.profile.intro",
        profile.introduction or profile.accomplishment,
    )
    if profile.video_link:
        fill_named(page, "cofounderMatching.profile.videoLink", profile.video_link)
    fill_named(page, "currentUser.impressiveThing", profile.accomplishment)
    fill_named(page, "currentUser.education", profile.education)
    fill_named(page, "currentUser.employment", profile.employment)

    click_radio_value_near_question(
        page,
        "Are you technical?",
        "true" if profile.is_technical else "false",
    )

    if profile.gender:
        fill_named(page, "currentUser.gender", profile.gender)
    page.locator('[name="currentUser.birthdate"]').fill(profile.birthday)

    if profile.calendly_url:
        fill_named(
            page, "cofounderMatching.profile.calendlyLink", profile.calendly_url
        )
    if profile.twitter_url:
        fill_named(page, "currentUser.twitterLink", profile.twitter_url)
    if profile.instagram_url:
        fill_named(page, "currentUser.instagramLink", profile.instagram_url)
    if profile.how_heard:
        fill_named(page, "cofounderMatching.profile.howHeard", profile.how_heard)

    save_and_continue(page)


def fill_more_about_you(page: Page, profile: ProfileData) -> None:
    page.goto(f"{CF_PROFILE_URL}?page=2", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    click_tab(page, "More About You")
    page.get_by_text(
        "Do you already have a startup or idea", exact=False
    ).first.wait_for(state="visible", timeout=30000)
    more = profile.more_about_you

    idea_value = {
        "committed": "committed",
        "open": "open",
        "none": "none",
    }.get(more.has_startup_idea, "none")
    page.locator(f'input[type="radio"][value="{idea_value}"]').first.check()

    if more.ideas:
        fill_named(page, "cofounderMatching.profile.ideas", more.ideas)

    heading = page.get_by_text("Do you already have a co-founder?", exact=False).first
    heading.scroll_into_view_if_needed()
    cofounder_value = "true" if more.already_has_cofounder else "false"
    heading.locator(
        f"xpath=following::input[@type='radio'][@value='{cofounder_value}'][1]"
    ).check()

    timing_value = {
        "active": "active",
        "ready": "ready",
        "year": "year",
        "passive": "passive",
    }.get(more.full_time_timing, "passive")
    page.locator(f'input[type="radio"][value="{timing_value}"]').first.check()

    select_multiselect_options(
        page,
        "Which areas of a startup are you willing to take responsibility for?",
        more.responsibilities,
    )

    if more.interests:
        select_all_multiselect_options(
            page, "Which topics and industries are you interested in?"
        )

    if more.equity_expectations:
        fill_named(page, "cofounderMatching.profile.equity", more.equity_expectations)
    if more.free_time:
        fill_named(page, "cofounderMatching.profile.freeTime", more.free_time)
    if more.life_story:
        fill_named(page, "cofounderMatching.profile.lifeStory", more.life_story)
    if more.anything_else:
        fill_named(page, "cofounderMatching.profile.other", more.anything_else)

    save_and_continue(page)


def fill_cofounder_preferences(page: Page, profile: ProfileData) -> None:
    page.goto(f"{CF_PROFILE_URL}?page=3", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    click_tab(page, "Co-Founder Preferences")
    page.get_by_text(
        "Co-Founder Requirements and Preferences", exact=False
    ).first.wait_for(state="visible", timeout=30000)
    prefs = profile.cofounder_preferences

    if prefs.looking_for:
        fill_named(page, "cofounderMatching.profile.reqFreeText", prefs.looking_for)

    idea_pref_map = {
        "has_idea": "I want to see co-founders who have a specific idea",
        "no_idea": "I want to see co-founders who are not set on a specific idea",
        "no_preference": "No preference",
    }
    # Ambiguous "No preference" texts exist; prefer specific options first.
    if prefs.idea_preference == "no_preference":
        click_radio_value_near_question(
            page,
            "Are you looking for a co-founder who already has a specific idea",
            "No preference",
        )
    else:
        click_radio_by_text(
            page, idea_pref_map.get(prefs.idea_preference, idea_pref_map["has_idea"])
        )
    select_importance_near_question(
        page,
        "Are you looking for a co-founder who already has a specific idea",
        prefs.idea_preference_importance,
    )

    tech_map = {
        "technical": "Technical",
        "non_technical": "Non-technical",
        "no_preference": "No preference",
    }
    if prefs.technical_preference == "no_preference":
        click_radio_value_near_question(
            page,
            "Do you prefer either technical or non-technical profiles?",
            "No preference",
        )
    else:
        click_radio_by_text(
            page, tech_map.get(prefs.technical_preference, tech_map["non_technical"])
        )
    select_importance_near_question(
        page,
        "Do you prefer either technical or non-technical profiles?",
        prefs.technical_preference_importance,
    )

    timing_map = {
        "require": "I only want to see co-founders who match my timing",
        "prefer": "I prefer to see co-founders who match my timing, but it's not required",
        "no_preference": "No preference",
    }
    if prefs.timing_preference == "no_preference":
        click_radio_value_near_question(
            page,
            "Do you prefer to see co-founders who match up with your timing?",
            "ignore",
        )
    else:
        click_radio_by_text(
            page, timing_map.get(prefs.timing_preference, timing_map["no_preference"])
        )

    location_map = {
        "distance": "Within a certain distance of me",
        "country": "In my country",
        "region": "In my region",
        "no_preference": "No preference",
    }
    if prefs.location_preference == "no_preference":
        click_radio_value_near_question(
            page, "Do you have a location preference?", "No preference"
        )
    elif prefs.location_preference in {"country", "region", "distance"}:
        value_map = {
            "distance": "geographic",
            "country": "country",
            "region": "region",
        }
        click_radio_value_near_question(
            page,
            "Do you have a location preference?",
            value_map[prefs.location_preference],
        )
    else:
        click_radio_by_text(page, location_map["no_preference"])
    select_importance_near_question(
        page, "Do you have a location preference?", prefs.location_preference_importance
    )

    if prefs.age_preference == "no_preference":
        click_radio_value_near_question(
            page, "Do you have an age preference?", "No preference"
        )
    else:
        click_radio_value_near_question(
            page, "Do you have an age preference?", "range"
        )
    select_importance_near_question(
        page, "Do you have an age preference?", prefs.age_preference_importance
    )

    select_multiselect_options(
        page,
        "Which areas would you like a co-founder to take responsibility for?",
        prefs.desired_responsibilities,
    )
    select_importance_near_question(
        page,
        "Which areas would you like a co-founder to take responsibility for?",
        prefs.desired_responsibilities_importance,
    )

    interests_map = {
        "require": "I only want to match with co-founders who share my interests",
        "prefer": "I prefer to match with co-founders who share my interests, but it's not required",
        "no_preference": "No preference",
    }
    if prefs.shared_interests_preference == "no_preference":
        click_radio_value_near_question(
            page,
            "Do you prefer to match candidates who share your interests?",
            "ignore",
        )
    else:
        click_radio_by_text(
            page,
            interests_map.get(
                prefs.shared_interests_preference, interests_map["no_preference"]
            ),
        )

    alert = page.get_by_text(
        "Alert me when a new profile that matches all my preferences joins",
        exact=False,
    )
    if alert.count():
        box = page.locator('input[type="checkbox"]').last
        try:
            if prefs.alert_on_match and not box.is_checked():
                box.check()
            elif not prefs.alert_on_match and box.is_checked():
                box.uncheck()
        except Exception:
            if prefs.alert_on_match:
                alert.first.click()

    save_and_continue(page, final_step=True)


def fill_cofounder_matching_profile(
    page: Page, profile: ProfileData, email: str
) -> None:
    """Fill Basics → More About You → Co-Founder Preferences."""
    print("  Filling Basics...")
    fill_basics(page, profile, email)
    print("  Filling More About You...")
    fill_more_about_you(page, profile)
    print("  Filling Co-Founder Preferences...")
    fill_cofounder_preferences(page, profile)
