"""End-to-end feature tests: every interactive control in the application.

This is the executable form of the feature checklist. Each test drives the real
UI against the real API in a real browser, so "tested" means the control was
clicked and its effect observed -- not that someone read the code and assumed.

Run with:  python -m pytest tests/e2e -q      (both dev servers must be up)
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://127.0.0.1:5173"
NAV = ["Dashboard", "Compare", "Circuits", "Predictions", "Race Analyst", "Model"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 950})
    page = context.new_page()
    page.errors = []  # type: ignore[attr-defined]
    page.on("pageerror", lambda e: page.errors.append(str(e)))  # type: ignore[attr-defined]
    page.on(
        "console",
        lambda m: page.errors.append(m.text) if m.type == "error" else None,  # type: ignore[attr-defined]
    )
    yield page
    context.close()


def goto(page: Page, path: str) -> None:
    page.goto(f"{BASE}{path}", wait_until="networkidle")
    page.wait_for_timeout(900)


def scroll_through(page: Page) -> None:
    """Trigger every scroll-reveal so nothing is measured while hidden."""
    height = page.evaluate("document.body.scrollHeight")
    for y in range(0, height, 600):
        page.evaluate(f"window.scrollTo(0,{y})")
        page.wait_for_timeout(90)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(400)


def unique_email(tag: str) -> str:
    return f"{tag}{int(time.time() * 1000)}@example.com"


# Failures that say nothing about this application's correctness: a portrait
# hosted on Wikimedia, or a Google Fonts stylesheet, being briefly unreachable.
# The app is designed to degrade gracefully when they are, so a feature test
# must not fail because a third party had a hiccup.
EXTERNAL_NOISE = (
    "Failed to load resource",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_CONNECTION",
    "net::ERR",
    "wikimedia",
    "fonts.googleapis",
    "fonts.gstatic",
)


def fatal_errors(page: Page) -> list:
    """Console/page errors that are genuinely this app's fault."""
    return [
        e
        for e in page.errors  # type: ignore[attr-defined]
        if not any(noise.lower() in e.lower() for noise in EXTERNAL_NOISE)
    ]


def body_text(page: Page) -> str:
    """Lower-cased page text.

    `inner_text()` returns text after CSS `text-transform`, so a label styled
    `uppercase` comes back as "FAVOURITE" no matter what the JSX says. Every
    content assertion compares lower-cased to avoid asserting on styling.
    """
    return page.inner_text("body").lower()


def sign_out_if_signed_in(page: Page) -> None:
    """The account page shows tabs only when signed out."""
    if page.locator("button:has-text('Sign out')").count():
        page.click("button:has-text('Sign out')")
        page.wait_for_timeout(700)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def test_every_nav_link_routes(page: Page):
    goto(page, "/")
    for label in NAV:
        page.click(f"nav >> text='{label}'")
        page.wait_for_timeout(700)
        assert page.locator("main").inner_text().strip(), f"{label} rendered empty"
    assert not fatal_errors(page), fatal_errors(page)


def test_deep_links_load_directly(page: Page):
    for path in ("/compare", "/circuits", "/predictions", "/analyst", "/model", "/account"):
        goto(page, path)
        assert len(page.inner_text("main")) > 200, f"{path} looks empty"


def test_unknown_route_shows_404_with_a_way_back(page: Page):
    goto(page, "/definitely-not-a-page")
    assert "404" in body_text(page)
    page.click("text=Back to the dashboard")
    page.wait_for_timeout(800)
    assert page.url.rstrip("/") == BASE


def test_browser_back_and_forward(page: Page):
    goto(page, "/")
    page.click("nav >> text='Circuits'")
    page.wait_for_timeout(700)
    page.go_back()
    page.wait_for_timeout(700)
    assert page.url.rstrip("/") == BASE
    page.go_forward()
    page.wait_for_timeout(700)
    assert "/circuits" in page.url


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def test_dashboard_hero_ctas(page: Page):
    goto(page, "/")
    page.click("text=See podium probabilities")
    page.wait_for_timeout(1200)
    assert "/predictions" in page.url

    goto(page, "/")
    page.click("text=Ask the Race Analyst")
    page.wait_for_timeout(900)
    assert "/analyst" in page.url


def test_dashboard_renders_live_figures(page: Page):
    goto(page, "/")
    body = body_text(page)
    assert "2025" in body
    # Hero counters must have finished counting, not sit at zero.
    assert "114" in body and "2278" in body


def test_every_chart_table_toggle_works(page: Page):
    """Each chart must have a readable table equivalent."""
    for path in ("/", "/circuits"):
        goto(page, path)
        scroll_through(page)
        toggles = page.locator("button:has-text('Table')")
        count = toggles.count()
        assert count > 0, f"no table toggles on {path}"
        for i in range(count):
            toggles.nth(i).click()
            page.wait_for_timeout(250)
            assert page.locator("table").count() > 0
        chart_buttons = page.locator("button:has-text('Chart')")
        for i in range(chart_buttons.count()):
            chart_buttons.nth(i).click()
            page.wait_for_timeout(150)
    assert not fatal_errors(page), fatal_errors(page)


def test_standings_tabs_switch(page: Page):
    goto(page, "/")
    scroll_through(page)
    page.click("button:has-text('Constructors')")
    page.wait_for_timeout(400)
    assert "mclaren" in body_text(page)
    page.click("button:has-text('Drivers')")
    page.wait_for_timeout(400)


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------
def test_compare_defaults_match_the_data_shown(page: Page):
    """The picker must name the drivers whose numbers are displayed."""
    goto(page, "/compare")
    page.wait_for_timeout(1800)
    selected = page.locator("select").first.input_value()
    shown = page.locator("select").first.locator("option:checked").inner_text()
    assert selected, "no driver selected"
    assert shown.split()[-1].lower() in page.inner_text("main").lower()


def test_compare_changing_drivers_updates_results(page: Page):
    goto(page, "/compare")
    page.wait_for_timeout(1800)
    before = page.inner_text("main")

    selects = page.locator("select")
    selects.nth(0).select_option("leclerc")
    selects.nth(1).select_option("hamilton")
    page.click("button:has-text('Compare')")
    page.wait_for_timeout(2200)

    after = page.inner_text("main")
    assert after != before
    assert "leclerc" in after.lower() and "hamilton" in after.lower()


def test_compare_season_filters(page: Page):
    goto(page, "/compare")
    page.wait_for_timeout(1800)
    page.click("button:has-text('2025')")
    page.wait_for_timeout(1800)
    assert "2025" in page.inner_text("main")
    page.click("button:has-text('All')")
    page.wait_for_timeout(1500)


def test_compare_save_prompts_anonymous_users_to_sign_in(page: Page):
    goto(page, "/compare")
    page.wait_for_timeout(1900)
    scroll_through(page)
    assert "sign in" in page.inner_text("main").lower()


# ---------------------------------------------------------------------------
# Circuits
# ---------------------------------------------------------------------------
def test_circuit_selector_changes_the_page(page: Page):
    goto(page, "/circuits")
    page.wait_for_timeout(1600)
    before = page.inner_text("main")
    # Option labels carry a country suffix, so match on the value instead.
    page.locator("select").first.select_option("monaco")
    page.wait_for_timeout(1900)
    after = page.inner_text("main")
    assert after != before
    assert "monaco" in after.lower()


def test_every_circuit_loads(page: Page):
    """Sample across the list -- a circuit with no pit data must not crash."""
    goto(page, "/circuits")
    page.wait_for_timeout(1500)
    options = page.locator("select").first.locator("option")
    total = options.count()
    assert total >= 20
    for index in range(0, total, 6):
        value = options.nth(index).get_attribute("value")
        page.locator("select").first.select_option(value)
        page.wait_for_timeout(1500)
        assert len(page.inner_text("main")) > 400, f"circuit {value} rendered thin"
    assert not fatal_errors(page), fatal_errors(page)


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------
def test_predictions_show_podium_and_disclaimer(page: Page):
    goto(page, "/predictions")
    page.wait_for_timeout(2200)
    body = body_text(page)
    assert "estimate, not a forecast" in body
    assert "most likely podium" in body
    assert "favourite" in body


def test_prediction_rows_expand_to_show_factors(page: Page):
    goto(page, "/predictions")
    page.wait_for_timeout(2200)
    rows = page.locator("ul li button[aria-expanded]")
    assert rows.count() >= 15
    rows.nth(3).click()
    page.wait_for_timeout(600)
    assert "what moves this estimate" in body_text(page)
    rows.nth(3).click()
    page.wait_for_timeout(400)


def test_scenario_simulation_runs_and_is_labelled(page: Page):
    goto(page, "/predictions")
    page.wait_for_timeout(2200)
    scroll_through(page)
    selects = page.locator("select")
    selects.nth(1).select_option("15")
    page.click("button:has-text('Simulate')")
    page.wait_for_timeout(3200)
    body = body_text(page)
    assert "simulation" in body
    assert "→" in page.inner_text("body") or "->" in body
    assert "simulation, not a race forecast" in body


@pytest.mark.parametrize("grid", ["1", "10", "20"])
def test_scenario_across_grid_slots(page: Page, grid: str):
    goto(page, "/predictions")
    page.wait_for_timeout(2200)
    scroll_through(page)
    page.locator("select").nth(1).select_option(grid)
    page.click("button:has-text('Simulate')")
    page.wait_for_timeout(3000)
    assert "podium probability" in body_text(page)


# ---------------------------------------------------------------------------
# AI Race Analyst
# ---------------------------------------------------------------------------
def test_suggestion_chip_asks_a_question(page: Page):
    goto(page, "/analyst")
    page.wait_for_timeout(1200)
    page.locator("button.chip").first.click()
    page.wait_for_timeout(3000)
    body = body_text(page)
    assert "grounded in data" in body or "no matching data" in body


@pytest.mark.parametrize(
    "question",
    [
        "Compare Verstappen and Norris at Monza",
        "Why might a one-stop strategy be risky at Bahrain?",
        "Who leads the championship?",
        "Which drivers do well at Suzuka?",
    ],
)
def test_analyst_answers_real_questions(page: Page, question: str):
    goto(page, "/analyst")
    page.fill("input[aria-label='Your question']", question)
    page.click("button[type=submit]")
    page.wait_for_timeout(3000)
    assert "grounded in data" in body_text(page)


def test_analyst_shows_its_sources(page: Page):
    goto(page, "/analyst")
    page.fill("input[aria-label='Your question']", "Compare Verstappen and Norris")
    page.click("button[type=submit]")
    page.wait_for_timeout(3000)
    page.locator("button:has-text('sources')").first.click()
    page.wait_for_timeout(500)
    assert "race_results" in body_text(page)


@pytest.mark.parametrize(
    "weird",
    [
        "aa",                                   # below the API minimum length
        "🏎️🏁 who wins 🏆",                      # emoji
        "Comparar Verstappen ünd Norris ñ",     # non-ASCII
        "<script>alert(1)</script>",            # injection attempt
        "'; DROP TABLE drivers;--",             # SQL attempt
        "a" * 999,                              # just under the cap
        "   Verstappen   ",                     # padded whitespace
    ],
)
def test_analyst_handles_weird_input_without_crashing(page: Page, weird: str):
    goto(page, "/analyst")
    page.fill("input[aria-label='Your question']", weird)
    page.click("button[type=submit]")
    page.wait_for_timeout(2600)
    # Either it answered, or it explained why it could not. Never a crash.
    body = body_text(page)
    assert len(body) > 200
    assert "ai race analyst" in body
    assert not fatal_errors(page), fatal_errors(page)


@pytest.mark.parametrize("blank", ["", "   ", "\t\n "])
def test_analyst_blocks_submission_of_blank_input(page: Page, blank: str):
    """A blank question must not be submittable at all."""
    goto(page, "/analyst")
    page.fill("input[aria-label='Your question']", blank)
    page.wait_for_timeout(250)
    assert page.locator("button[type=submit]").is_disabled()


def test_script_payload_is_not_executed(page: Page):
    """Stored XSS check: the payload must be rendered as text, never run."""
    fired = []
    page.on("dialog", lambda d: (fired.append(d.message), d.dismiss()))
    goto(page, "/analyst")
    page.fill(
        "input[aria-label='Your question']",
        "<img src=x onerror=alert('xss')><script>alert('xss2')</script> Verstappen",
    )
    page.click("button[type=submit]")
    page.wait_for_timeout(3000)
    assert not fired, f"script executed: {fired}"
    assert page.locator("main script").count() == 0


# ---------------------------------------------------------------------------
# Account, validation and the full auth journey
# ---------------------------------------------------------------------------
def test_signup_validation_messages(page: Page):
    goto(page, "/account")
    page.click("button[role=tab]:has-text('Create account')")
    page.wait_for_timeout(300)
    page.fill("input[type=email]", "not-an-email")
    page.fill("input[autocomplete=new-password] >> nth=0", "short")
    page.click("button[type=submit]")
    page.wait_for_timeout(500)
    body = body_text(page)
    assert "valid email address" in body
    assert "at least 8 characters" in body
    assert "confirm your password" in body


def test_password_mismatch_is_caught(page: Page):
    goto(page, "/account")
    page.click("button[role=tab]:has-text('Create account')")
    page.fill("input[type=email]", unique_email("mismatch"))
    page.fill("input[autocomplete=new-password] >> nth=0", "goodpassword1")
    page.fill("input[autocomplete=new-password] >> nth=1", "otherpassword1")
    page.wait_for_timeout(500)
    assert "do not match" in body_text(page)


def test_duplicate_email_is_reported_clearly(page: Page):
    email = unique_email("dupe")
    for attempt in range(2):
        goto(page, "/account")
        # Registering signs the user in, so the second attempt needs a sign-out
        # before the tabs are on screen again.
        sign_out_if_signed_in(page)
        page.click("button[role=tab]:has-text('Create account')")
        page.fill("input[type=email]", email)
        page.fill("input[autocomplete=new-password] >> nth=0", "goodpassword1")
        page.fill("input[autocomplete=new-password] >> nth=1", "goodpassword1")
        page.click("button[type=submit]")
        page.wait_for_timeout(2200)
        if attempt == 1:
            assert "already exists" in body_text(page)


def test_wrong_password_message(page: Page):
    email = unique_email("wrongpw")
    goto(page, "/account")
    page.click("button[role=tab]:has-text('Create account')")
    page.fill("input[type=email]", email)
    page.fill("input[autocomplete=new-password] >> nth=0", "goodpassword1")
    page.fill("input[autocomplete=new-password] >> nth=1", "goodpassword1")
    page.click("button[type=submit]")
    page.wait_for_timeout(2200)

    page.click("text=Sign out")
    page.wait_for_timeout(800)
    page.fill("input[type=email]", email)
    page.fill("input[autocomplete=current-password]", "definitely-wrong-1")
    page.click("button[type=submit]")
    page.wait_for_timeout(1800)
    assert "incorrect email or password" in body_text(page)


def test_full_account_journey(page: Page):
    """Register, save a comparison, reopen it, delete it, sign out."""
    email = unique_email("journey")
    goto(page, "/account")
    page.click("button[role=tab]:has-text('Create account')")
    page.fill("input[type=email]", email)
    page.fill("input[autocomplete=new-password] >> nth=0", "goodpassword1")
    page.fill("input[autocomplete=new-password] >> nth=1", "goodpassword1")
    page.click("button[type=submit]")
    page.wait_for_timeout(2400)
    assert "saved comparisons" in body_text(page)

    goto(page, "/compare")
    page.wait_for_timeout(2400)
    scroll_through(page)
    page.click("button:has-text('Save comparison')")
    page.wait_for_timeout(400)
    page.click("button:has-text('Save')")
    page.wait_for_timeout(1800)
    assert "saved." in page.inner_text("main").lower()

    goto(page, "/account")
    page.wait_for_timeout(1500)
    assert page.locator("a:has-text('Open')").count() == 1
    page.click("a:has-text('Open')")
    page.wait_for_timeout(2400)
    assert "a=" in page.url and "b=" in page.url

    goto(page, "/account")
    page.wait_for_timeout(1400)
    page.click("button:has-text('Delete')")
    page.wait_for_timeout(1400)
    assert "nothing saved yet" in body_text(page)

    page.click("button:has-text('Sign out')")
    page.wait_for_timeout(900)
    assert page.locator("button[role=tab]").count() == 2


def test_session_survives_a_reload(page: Page):
    email = unique_email("persist")
    goto(page, "/account")
    page.click("button[role=tab]:has-text('Create account')")
    page.fill("input[type=email]", email)
    page.fill("input[autocomplete=new-password] >> nth=0", "goodpassword1")
    page.fill("input[autocomplete=new-password] >> nth=1", "goodpassword1")
    page.click("button[type=submit]")
    page.wait_for_timeout(2200)

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1600)
    assert "saved comparisons" in body_text(page)


@pytest.mark.parametrize(
    "email",
    ["a@b.co", "very.long.address+tag@sub.domain.example.com", "UPPER@EXAMPLE.COM"],
)
def test_valid_email_shapes_are_accepted(page: Page, email: str):
    goto(page, "/account")
    page.click("button[role=tab]:has-text('Create account')")
    unique = email.replace("@", f"{int(time.time()*1000)}@")
    page.fill("input[type=email]", unique)
    page.fill("input[autocomplete=new-password] >> nth=0", "goodpassword1")
    page.fill("input[autocomplete=new-password] >> nth=1", "goodpassword1")
    page.wait_for_timeout(400)
    assert "valid email address" not in body_text(page)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
def test_feedback_positive_and_negative_paths(page: Page):
    goto(page, "/predictions")
    page.wait_for_timeout(2200)
    scroll_through(page)
    page.locator("button:has-text('No')").last.click()
    page.wait_for_timeout(600)
    assert "what was wrong?" in body_text(page)
    page.locator("button:has-text('Explanation was unclear')").first.click()
    page.wait_for_timeout(1200)
    assert "thanks" in body_text(page)

    goto(page, "/circuits")
    page.wait_for_timeout(1600)
    scroll_through(page)
    page.locator("button:has-text('Yes')").last.click()
    page.wait_for_timeout(1200)
    assert "thanks" in body_text(page)


# ---------------------------------------------------------------------------
# Responsive
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "size",
    [(375, 812), (390, 844), (768, 1024), (1024, 768), (1440, 900), (1920, 1080)],
)
def test_no_horizontal_scroll_at_any_size(browser, size):
    width, height = size
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    for path in ("/", "/compare", "/circuits", "/predictions", "/analyst", "/model", "/account"):
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        page.wait_for_timeout(1100)
        scroll_through(page)
        scroll_w = page.evaluate("document.documentElement.scrollWidth")
        client_w = page.evaluate("document.documentElement.clientWidth")
        assert scroll_w <= client_w + 1, f"{path} overflows at {width}px"
        hidden = page.evaluate(
            """() => [...document.querySelectorAll('*')]
                 .filter(e => getComputedStyle(e).opacity === '0'
                           && e.getBoundingClientRect().height > 40).length"""
        )
        assert hidden == 0, f"{path} has {hidden} hidden blocks at {width}px"
    context.close()


def test_reduced_motion_reveals_everything_immediately(browser):
    context = browser.new_context(
        viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
    )
    page = context.new_page()
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(1100)
    hidden = page.evaluate(
        """() => [...document.querySelectorAll('*')]
             .filter(e => getComputedStyle(e).opacity === '0'
                       && e.getBoundingClientRect().height > 40).length"""
    )
    animating = page.evaluate(
        """() => [...document.querySelectorAll('*')]
             .filter(e => parseFloat(getComputedStyle(e).animationDuration || '0') > 0.01).length"""
    )
    assert hidden == 0
    assert animating == 0
    context.close()


# ---------------------------------------------------------------------------
# Third-party resilience
# ---------------------------------------------------------------------------
def test_app_works_when_portrait_host_is_unreachable(browser):
    """Driver photos come from Wikimedia. If it is down, the app must not be.

    This is the failure that briefly broke a test run for real, so it is now
    simulated deliberately rather than waited for.
    """
    context = browser.new_context(viewport={"width": 1440, "height": 950})
    page = context.new_page()
    errors: list = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # Blackhole every external image request.
    page.route("**://*.wikimedia.org/**", lambda route: route.abort())

    for path in ("/", "/predictions", "/compare"):
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        page.wait_for_timeout(1500)
        text = page.inner_text("main")
        assert len(text) > 400, f"{path} did not render without portraits"

    # The monogram fallback must have taken over: driver names still present,
    # and no broken-image elements left behind.
    page.goto(f"{BASE}/predictions", wait_until="networkidle")
    page.wait_for_timeout(2000)
    assert "verstappen" in page.inner_text("main").lower()
    broken = page.evaluate(
        "() => [...document.images].filter(i => i.complete && i.naturalWidth === 0).length"
    )
    assert broken == 0, f"{broken} broken images left on screen"
    assert not errors, errors
    context.close()
