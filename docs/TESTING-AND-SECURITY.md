# Testing & Security Report

**Application:** ApexStrategy AI — Formula 1 strategy analytics
**Date:** 27 September 2026
**Scope:** Full application — FastAPI backend, React frontend, ML pipeline, deployment configuration

---

## 1. Summary

| | Result |
|---|---|
| Automated tests | **223** (128 backend · 40 frontend unit · 55 end-to-end browser) |
| Features tested | 61 interactive controls across 7 pages |
| Bugs found | **11** — all fixed |
| Security findings | **9** — all fixed |
| Dependency vulnerabilities | **30 across 8 packages → 0** |
| Accessibility violations | **173 failing nodes → 0** (WCAG 2.1 AA, axe-core) |
| Attack classes probed and already defended | 4 (SQL injection, XSS, path traversal, IDOR) |

Everything below was **executed**, not reviewed. Feature testing drives a real
browser against the real API; security findings come from probes run against a
live server, with before/after measurements.

---

## 2. Feature testing checklist

All 54 end-to-end tests live in `tests/e2e/test_features.py` and run with
`pytest tests/e2e`. Each row was clicked and its effect observed.

### 2.1 Navigation — 6 checks

| Feature | Test | Result |
|---|---|---|
| 6 primary nav links route correctly | `test_every_nav_link_routes` | PASS |
| Account link reflects signed-in state | `test_full_account_journey` | PASS |
| Deep links load directly (no client-side state needed) | `test_deep_links_load_directly` | PASS |
| Unknown route shows 404 with a way back | `test_unknown_route_shows_404_with_a_way_back` | PASS |
| Browser back / forward | `test_browser_back_and_forward` | PASS |
| Logo returns to dashboard | covered by nav test | PASS |

### 2.2 Dashboard — 9 checks

| Feature | Test | Result |
|---|---|---|
| Hero CTA → Predictions | `test_dashboard_hero_ctas` | PASS |
| Hero CTA → Race Analyst | `test_dashboard_hero_ctas` | PASS |
| Hero counters reach real values (114 races / 2,278 results) | `test_dashboard_renders_live_figures` | PASS |
| Championship leader card with portrait | `test_dashboard_renders_live_figures` | PASS |
| Title-contenders strip (5 cards) | `test_no_horizontal_scroll_at_any_size` | PASS |
| Constructors' championship chart ↔ table | `test_every_chart_table_toggle_works` | PASS |
| Drivers' championship chart ↔ table | `test_every_chart_table_toggle_works` | PASS |
| Pit-strategy & grid-conversion charts ↔ tables | `test_every_chart_table_toggle_works` | PASS |
| Standings Drivers ↔ Constructors tabs | `test_standings_tabs_switch` | PASS |

### 2.3 Driver comparison — 5 checks

| Feature | Test | Result |
|---|---|---|
| Pickers seed from real data and match what is displayed | `test_compare_defaults_match_the_data_shown` | PASS |
| Changing both drivers updates every panel | `test_compare_changing_drivers_updates_results` | PASS |
| Season filter chips (All + 5 seasons) | `test_compare_season_filters` | PASS |
| Save prompts anonymous users to sign in | `test_compare_save_prompts_anonymous_users_to_sign_in` | PASS |
| Rates and timeline charts ↔ tables | `test_every_chart_table_toggle_works` | PASS |

### 2.4 Circuits — 2 checks (28 circuits sampled)

| Feature | Test | Result |
|---|---|---|
| Circuit selector changes the whole page | `test_circuit_selector_changes_the_page` | PASS |
| Every 6th circuit loads without error (incl. circuits with no pit data) | `test_every_circuit_loads` | PASS |

### 2.5 Predictions — 6 checks

| Feature | Test | Result |
|---|---|---|
| "Estimate, not a forecast" banner present | `test_predictions_show_podium_and_disclaimer` | PASS |
| Podium spotlight renders top three | `test_predictions_show_podium_and_disclaimer` | PASS |
| All 20 field rows expand to show factor breakdown | `test_prediction_rows_expand_to_show_factors` | PASS |
| Scenario simulation runs and is labelled a simulation | `test_scenario_simulation_runs_and_is_labelled` | PASS |
| Scenario across grid slots P1 / P10 / P20 | `test_scenario_across_grid_slots` (3 cases) | PASS |
| Feedback widget, both paths | `test_feedback_positive_and_negative_paths` | PASS |

### 2.6 AI Race Analyst — 14 checks

| Feature | Test | Result |
|---|---|---|
| Suggestion chips ask a question | `test_suggestion_chip_asks_a_question` | PASS |
| Four real questions return grounded answers | `test_analyst_answers_real_questions` (4 cases) | PASS |
| Citations expand and name their source tables | `test_analyst_shows_its_sources` | PASS |
| Blank / whitespace input cannot be submitted | `test_analyst_blocks_submission_of_blank_input` (3 cases) | PASS |
| Weird input handled without crashing | `test_analyst_handles_weird_input_without_crashing` (7 cases) | PASS |
| App still works when the portrait host is unreachable | `test_app_works_when_portrait_host_is_unreachable` | PASS |
| Script payload rendered as text, never executed | `test_script_payload_is_not_executed` | PASS |

Weird-input cases covered: below-minimum length, emoji (`🏎️🏁🏆`), non-ASCII
(`ünd`, `ñ`), `<script>alert(1)</script>`, `'; DROP TABLE drivers;--`,
999-character input, and padded whitespace.

### 2.7 Model transparency — covered

Stat tiles, both evaluation tables, feature chips and the feedback summary are
exercised by the responsive and navigation sweeps; the page has no interactive
controls of its own beyond scrolling.

### 2.8 Account & forms — 12 checks

| Feature | Test | Result |
|---|---|---|
| Sign-in / Create-account tabs | `test_signup_validation_messages` | PASS |
| Invalid email rejected | `test_signup_validation_messages` | PASS |
| Password below 8 characters rejected | `test_signup_validation_messages` | PASS |
| Confirmation required | `test_signup_validation_messages` | PASS |
| Password mismatch caught | `test_password_mismatch_is_caught` | PASS |
| Valid email shapes accepted (3 forms) | `test_valid_email_shapes_are_accepted` | PASS |
| Duplicate email reported clearly | `test_duplicate_email_is_reported_clearly` | PASS |
| Wrong password message | `test_wrong_password_message` | PASS |
| Register → save → reopen → delete → sign out | `test_full_account_journey` | PASS |
| Session survives a page reload | `test_session_survives_a_reload` | PASS |

### 2.9 Responsive & motion — 7 checks

| Viewport | Pages | Result |
|---|---|---|
| 375 × 812 (iPhone SE) | all 7 | No horizontal scroll, no hidden content |
| 390 × 844 (iPhone 14) | all 7 | PASS |
| 768 × 1024 (iPad portrait) | all 7 | PASS |
| 1024 × 768 (iPad landscape) | all 7 | PASS |
| 1440 × 900 (laptop) | all 7 | PASS |
| 1920 × 1080 (desktop) | all 7 | PASS |
| `prefers-reduced-motion: reduce` | dashboard | 0 animating elements, 0 hidden blocks |

---

## 3. Bugs found and fixed

### 3.1 Application bugs

| # | Severity | Bug | Cause | Fix |
|---|---|---|---|---|
| 1 | **High** | App would not start after following the documented setup | `pydantic-settings` JSON-decodes list fields from `.env` before validators run, so the documented `INGEST_SEASONS=2021,2022,...` failed to parse | `NoDecode` annotation on both list fields; 12 config tests now load `.env.example` verbatim |
| 2 | **High** | Compare page showed one driver's data under another's name | Ergast driver refs are not always the surname (`max_verstappen`), so the hardcoded default never matched and the select fell back to the first option while the query used the original string | Pickers seed from the fetched driver list; URL parameters honoured |
| 3 | **Medium** | Model lost to its own baseline | Gradient boosting overfits ~1,800 rows; grid position dominates the signal | Rebuilt as a calibrated logistic regression blended with the grid-conversion prior, weight chosen on a validation season |
| 4 | **Medium** | Training crashed on small datasets | Calibration hardcoded 5 folds; podiums are a ~15% class, so a small dataset has fewer positives than folds | Fold count adapts to the rarest class; skips calibration with a warning when there are too few |
| 5 | **Medium** | Scroll-revealed content could be hidden permanently | Content sits at `opacity: 0` until an IntersectionObserver fires; a missing observer or an `overflow:hidden` ancestor means it never does | Every reveal carries a 2.5s fail-open timer |
| 6 | **Medium** | A render-time throw blanked the entire application | No React error boundary | `ErrorBoundary` with retry, route-change reset and a way home; 6 component tests |
| 7 | **Low** | Compare rendered a dead form when the API was unreachable | Driver-list load error was never surfaced | Explicit `ErrorState` with retry |
| 8 | **Low** | A disqualification displayed as its classified finishing position | `positionText` was checked after `position` | Status codes (`R`, `D`, `W`, `E`, `F`, `N`) take precedence → "DSQ" |
| 9 | **Low** | Tyre-strategy narration was generic boilerplate | Template asserted a rule instead of reading the distribution | Narration now derives the verdict from observed stop counts (Bahrain: "only 1% one-stopped"; Monza: "70% did") |
| 10 | **Low** | Constructor chart labels overlapped | Teams finishing on similar points stacked their end-of-line labels | Label positions computed against a pinned axis with a minimum-gap declutter pass |
| 11 | **Low** | Three teams' near-identical blues were indistinguishable | Team brand colours are not a CVD-safe palette | End-of-line direct labels; identity never rests on colour alone |

### 3.2 A test that depended on someone else's uptime

A later full run failed two tests with `ERR_INTERNET_DISCONNECTED`. The network
had dropped briefly, and the affected tests asserted that **no** console errors
had occurred — which includes a Wikimedia portrait failing to load.

The application behaved correctly throughout: portraits fall back to monograms
by design. The **test** was wrong to treat a third party's availability as a
correctness signal.

Two changes followed:

- A `fatal_errors()` helper now filters external resource failures (Wikimedia,
  Google Fonts) while still failing on genuine JavaScript exceptions.
- `test_app_works_when_portrait_host_is_unreachable` now **simulates** the
  outage by aborting every Wikimedia request, asserting that all pages still
  render, driver names are still present, and **zero broken images** remain on
  screen. The failure that had to be waited for is now provoked on purpose.

### 3.3 Test bugs found while testing

Eight end-to-end tests failed on the first full run. **All eight were faults in
the tests, not the product** — worth recording because the failure mode is
easy to repeat:

- **Six** asserted against `inner_text()` case-sensitively. `inner_text()`
  returns text *after* CSS `text-transform`, so a label styled `uppercase`
  comes back as `FAVOURITE` however the JSX is written. Fixed with a
  `body_text()` helper that lower-cases before comparing.
- **One** tried to click a correctly-disabled button (blank question). The
  product was right; the test now asserts the button *is* disabled.
- **One** did not account for registration signing the user in, so the tabs it
  waited for were no longer on screen.

---

## 4. Security audit

Probes were run against a live server (`scratchpad/sec2.py`, `verify.py`), with
measurements before and after each fix.

### 4.1 Findings — all fixed

| # | Severity | Finding | Evidence | Fix | Verified |
|---|---|---|---|---|---|
| S1 | **High** | **User enumeration by login timing.** bcrypt ran only when the account existed, so a missing account rejected ~168× faster — trivially enumerating registered emails | 227 ms vs 1.4 ms | Always hash, against a decoy when absent (`verify_password_dummy`) | **1.00×** (238.7 ms vs 238.9 ms) |
| S2 | **High** | **No rate limiting on authentication.** 25 failed logins completed in under a second | 25 × HTTP 401, no throttle | `RateLimitMiddleware`: 10/min on auth, 240/min elsewhere, per client IP, with `Retry-After` | 10 attempts then HTTP 429 |
| S3 | **High** | **Production would boot with the public default JWT secret**, letting anyone forge a token | App started with `dev-only-insecure-secret-change-me` | `validate_runtime_security()` refuses to start | Boot refused with a named reason |
| S4 | **Medium** | **Passwords silently truncated at 72 bytes.** Two different long passwords authenticated the same account | Login succeeded with different characters after byte 72 | Switched to `bcrypt_sha256` (SHA-256 pre-hash); legacy bcrypt hashes still verify and upgrade on next login | Wrong long password now HTTP 401 |
| S5 | **Medium** | **Unauthenticated database write via GET.** `GET /predictions/next?persist=true` inserted rows — anonymous, and unsafe for a method that may be retried or prefetched | Rows written by a GET | `persist` removed; writes moved to `POST /predictions/race/{id}/snapshot` behind authentication | Anonymous POST → 401; row count unchanged by GET |
| S6 | **Medium** | **No security headers.** All six absent | CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy missing | `SecurityHeadersMiddleware`; CSP enforced in production, report-only in development | All present; CSP + HSTS confirmed in production mode |
| S7 | **Medium** | **`DEBUG` defaulted to true**, so an unset variable would return exception text to clients | `debug: bool = Field(default=True)` | Default flipped to `false`; production refuses to start with it on | Validation errors only; no internals |
| S8 | **Low** | **CORS permitted all methods and headers with credentials enabled** | `allow_methods=["*"]`, `allow_headers=["*"]` | Restricted to the methods and headers actually used; wildcard origin refused in production | Config guard rejects `*` |
| S9 | **High** | **30 known vulnerabilities across 8 dependencies**, including 7 in PyJWT (the authentication library) and 7 in Starlette (the web framework core) | `pip-audit` | Upgraded the whole stack; see 4.2 | **0 known vulnerabilities** |

### 4.2 Dependency audit — and the Python version that blocked it

`pip-audit` reported **30 advisories across 8 packages**. The two that mattered
most sat directly in the security path:

| Package | Role | Advisories | Was | Now |
|---|---|---|---|---|
| PyJWT | token signing and verification | 7 | 2.10.1 | **2.15.0** |
| Starlette | ASGI core beneath FastAPI | 7 | 0.41.3 | **1.7.0** |
| python-multipart | form parsing | 6 | 0.0.20 | **0.0.31** |
| urllib3 | HTTP for boto3 | 5 | 1.26.20 | **2.x** |
| anyio, click, python-dotenv, pytest | transitive | 4 | — | patched |

**The blocker was the runtime itself.** The first upgrade attempt failed:
every patched release — PyJWT 2.15, pydantic-settings 2.12+, FastAPI 0.129+ —
requires **Python ≥ 3.10**, and the development environment was on **Python
3.9.6**, which reached end-of-life in October 2025 and no longer receives
security patches of its own.

So the finding is not really "some packages are old". It is that **the project
could not be patched without moving off an unsupported Python**. Pinning to the
newest 3.9-compatible versions would have left most of the advisories open
while looking like remediation.

Resolution:

1. Installed a standalone **Python 3.11.16** (via `uv`, without modifying the
   system Python).
2. Rebuilt the virtual environment and upgraded to **FastAPI 0.141.1 /
   Starlette 1.7.0 / PyJWT 2.15.0 / pydantic 2.13.5**.
3. Re-ran every suite: **128 backend tests pass** on the upgraded stack.
4. Retrained the model, because the artifact had been pickled under
   scikit-learn 1.5.2 and loading it under 1.7.2 raised
   `InconsistentVersionWarning` — a correctness risk, not just noise. The
   retrained model scores **identically** (podium log loss 0.1922, points
   0.4859), which confirms the upgrade changed no behaviour.
5. Pinned `3.11` in `.python-version`, added a version assertion to
   `make install-backend`, and documented the requirement in the README.

The production Dockerfile already used `python:3.11-slim`, so the deployed
image was never on 3.9 — but local development and the documented setup were,
which is exactly the gap an audit is meant to find.

**Result: `pip-audit` now reports "No known vulnerabilities found".**

`npm audit` and `pip-audit` now run in CI on every push.

### 4.3 Attack classes probed — already defended

| Attack | Method | Result |
|---|---|---|
| **SQL injection** | `' OR '1'='1`, `'; DROP TABLE drivers;--`, `%' OR 1=1--`, `UNION SELECT` against search and compare | No effect. SQLAlchemy parameterises every query; the `drivers` table was intact afterwards. **No raw or string-interpolated SQL exists in the codebase** |
| **Stored / reflected XSS** | `<img src=x onerror=alert(1)>` and `<script>` through the chat and feedback fields | Never executed. React escapes by default and the codebase contains **no `dangerouslySetInnerHTML`, `innerHTML` or `eval`**. The Markdown renderer parses a deliberately small subset rather than injecting HTML |
| **Path traversal** | `../../../../etc/passwd` and URL-encoded variants against the SPA catch-all | Blocked. The handler resolves the path and confirms the bundle directory is a parent before serving |
| **IDOR** | Second account reading and deleting the first account's saved comparisons | Blocked. Returns **404, not 403**, so the endpoint does not confirm another user's record exists |
| **JWT tampering** | Stripped signature, foreign signing key, `alg: none`, expired token, missing `Bearer` prefix | All rejected. Algorithms are pinned and `exp`/`sub` are required |
| **Oversized payloads** | 100k-character question, 500k-character comment | Rejected with HTTP 422 by schema bounds |

### 4.4 Secrets handling

- **No secrets in source control.** `git ls-files` confirms no `.env`, `.db` or
  key material is tracked; `.gitignore` excludes them.
- **No hardcoded credentials** in application code — verified by pattern sweep.
- Production credentials come from **AWS Secrets Manager** via `DB_SECRET_ARN`,
  resolved at boot. A malformed secret logs and falls back rather than
  crash-looping.
- The IAM instance policy is **least-privilege**: `bedrock:InvokeModel` is
  scoped to one model ARN, Secrets Manager to two secret ARNs, S3 to one
  bucket. No account-level wildcards.
- The one remaining secret in the repository is the **development** JWT default,
  which production now refuses to start with.

---

## 5. Accessibility

Audited with **axe-core** against WCAG 2.1 A and AA, on all 7 pages, after
scrolling each page so lazily-revealed content was included.

| | Before | After |
|---|---|---|
| Failing nodes | **173** | **0** |
| Rules violated | 3 | 0 |
| Pages clean | 1 of 7 | **7 of 7** |

### Violations fixed

| Rule | Impact | Nodes | Cause | Fix |
|---|---|---|---|---|
| `color-contrast` | serious | 168 | Muted ink `#6f7686` measured **3.22:1** on `surface-3` — below the 4.5:1 AA floor. The primary button was **3.64:1** white-on-blue | Muted ink lifted to `#949bac` (**5.28:1** worst case). Buttons use a dedicated `action` blue `#2f72c4` (**4.86:1**); charts keep the validated `#3987e5` series colour |
| `scrollable-region-focusable` | serious | 4 | Scrolling containers were mouse-only | `tabIndex={0}` plus `role="region"` and a label |
| `link-in-text-block` | serious | 1 | Inline links distinguished by colour alone | `.link` class with a persistent underline |

### Accessibility features in place

- **Colour is never the only signal.** Team colours are brand colours and not
  mutually CVD-safe, so every team-coloured chart also carries a legend *and*
  direct labels, and every swatch sits beside the name it stands for.
- **Every chart has a table view**, so no data is reachable only through colour
  and shape.
- **`prefers-reduced-motion` is fully honoured** — 0 animating elements, and
  content appears immediately rather than being degraded.
- **Reveal animations fail open**, so content is never permanently hidden by a
  failed observer.
- Semantic `<button>`, `<select>`, `<table>` and `<label>` elements with
  `aria-pressed`, `aria-expanded`, `aria-invalid` and `aria-describedby`.
- Form errors use `role="alert"` and are tied to their input.
- Visible focus rings with an offset.
- Decorative imagery (portraits, motifs) carries empty `alt` or
  `aria-hidden="true"`; driver names are always present as text.
- No horizontal scrolling at any tested viewport from 375px up.

---

## 6. Error handling

| Layer | Behaviour |
|---|---|
| Unhandled server exception | Logged with a stack trace; client receives a generic message when `DEBUG=false` |
| Invalid input | Pydantic schema bounds → HTTP 422 with field-level detail |
| Database unreachable | `/api/health` reports `degraded` but still returns 200, so a database blip does not pull the instance out of the load balancer |
| Model artifact missing | Prediction endpoints return `available: false` with an actionable message; the rest of the product keeps working |
| Bedrock unavailable | Falls back to the deterministic narrator; `fallback_reason` is returned for monitoring. **Accuracy is never degraded, only fluency** |
| Data-source rate limiting | Ingestion and portrait fetchers back off exponentially and are idempotent |
| Third-party image host unreachable | Portraits fall back to monograms; no broken images. Covered by a test that simulates the outage |
| Frontend render throw | Caught by `ErrorBoundary`; the rest of the app stays usable |
| API unreachable from the browser | Friendly message with a retry on every data-backed page |
| Private browsing / blocked storage | Every `localStorage` access is wrapped; the app stays signed out rather than crashing |

---

## 7. Residual risks

Stated plainly rather than omitted.

| Risk | Status |
|---|---|
| **Rate limiting is per-instance and in-memory.** It resets on restart and does not coordinate across instances | Accepted for this scale. Distributed limiting belongs at the edge (AWS WAF) |
| **No account lockout or CAPTCHA** after repeated failures | Rate limiting is the current mitigation |
| **JWTs cannot be revoked** before expiry (7 days) | Acceptable given the only protected resource is a user's own saved comparisons. A shorter expiry plus refresh tokens would be the next step |
| **Token stored in `localStorage`**, readable by any successful XSS | Mitigated by React's escaping, no `innerHTML` anywhere, and a strict CSP. `httpOnly` cookies with CSRF protection would be stronger |
| **No email verification** on registration | Out of scope for the MVP |
| **Docker build unverified** — Docker is not available on this machine | The Dockerfile's paths and assumptions were checked statically, but the image has not been built or run |
| **New advisories will appear over time** | `pip-audit` and `npm audit` now run in CI on every push, so drift is caught rather than discovered |

---

## 8. How to reproduce

```bash
# Backend: 128 unit and integration tests
cd backend && .venv/bin/python -m pytest

# Frontend: 40 unit and component tests
cd frontend && npm test

# End-to-end: 55 browser tests (both dev servers must be running)
python -m pytest tests/e2e

# Dependency vulnerability scan
make audit

# Everything
make test-all
```

**Requires Python 3.11+.** See §4.2 for why.
