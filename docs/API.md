# API reference

Base path `/api`. Interactive docs at `/api/docs` (Swagger) and `/api/redoc`.

Most endpoints are public — the product is readable without an account. Only a
user's own saved comparisons require authentication (`Authorization: Bearer
<token>`).

---

## Health & metadata

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service status, row counts, model status, Bedrock reachability. Returns 200 whenever the service can serve traffic. |
| `GET` | `/meta` | Seasons available, next/latest race, which AI generator is active. |

---

## Races & seasons

| Method | Path | Description |
|---|---|---|
| `GET` | `/races?season=&completed_only=` | Race list |
| `GET` | `/races/next` | Next race without results (falls back to the most recent), with circuit history and pit strategy |
| `GET` | `/races/{race_id}` | Results, qualifying and pit strategy |
| `GET` | `/races/{race_id}/circuit-history?seasons=` | Historical performance at that circuit |
| `GET` | `/seasons/{season}/standings` | Driver and constructor standings |
| `GET` | `/seasons/{season}/constructor-progression` | Cumulative points per round |

---

## Drivers & constructors

| Method | Path | Description |
|---|---|---|
| `GET` | `/drivers?season=` | Driver list |
| `GET` | `/drivers/{identifier}?seasons=` | Profile, season progression, qualifying trend |
| `GET` | `/drivers/{identifier}/circuits` | Per-circuit record |
| `GET` | `/drivers/compare?a=&b=&seasons=&circuit_id=` | Head-to-head |
| `GET` | `/constructors` | Constructor list |
| `GET` | `/constructors/{identifier}?seasons=` | Constructor profile |
| `GET` | `/constructors/compare?a=&b=&seasons=` | Team comparison |
| `GET` | `/circuits` | Circuit list |
| `GET` | `/circuits/{identifier}?seasons=` | Circuit history, grid analysis, pit strategy |
| `GET` | `/search?q=` | Cross-entity search |

`{identifier}` accepts a ref (`max_verstappen`), a code (`VER`), a surname or a
full name. Note that Ergast refs are not always the surname.

### Head-to-head semantics

`GET /drivers/compare` counts a race in the head-to-head tally **only when both
drivers were classified**. A retirement is not a "loss" — it is a different kind
of event, and is reported separately as a DNF rate. Qualifying head-to-head is
counted independently, over sessions where both set a time.

---

## Predictions

| Method | Path | Description |
|---|---|---|
| `GET` | `/predictions/model` | Version, training window, evaluation vs baselines |
| `GET` | `/predictions/next?persist=` | Probabilities for the next race |
| `GET` | `/predictions/race/{race_id}?persist=` | Probabilities for a specific race |
| `POST` | `/predictions/scenario` | Re-score with one driver on a different grid slot |

```jsonc
// GET /api/predictions/next
{
  "available": true,
  "race": "Abu Dhabi Grand Prix",
  "model_version": "v20260927-212507",
  "grid_source": "qualifying",       // or "projected" when qualifying hasn't run
  "is_simulation": false,
  "predictions": [
    {
      "driver": "Max Verstappen",
      "constructor": "Red Bull",
      "grid": 1,
      "podium_probability": 0.8293,
      "points_probability": 0.9546,
      "win_probability": 0.2637,      // normalised so the field sums to 1
      "expected_position": 1,
      "top_factors": [
        {
          "label": "starting grid position",
          "value": 1.0,
          "baseline": 10.0,
          "impact": 0.3428,
          "direction": "increases"
        }
      ],
      "features": { "...": "every model input, for traceability" }
    }
  ],
  "disclaimer": "These are model estimates based on historical data, not forecasts..."
}
```

```jsonc
// POST /api/predictions/scenario
// { "race_id": 114, "driver_id": 1, "grid": 12 }
{
  "driver": "Max Verstappen",
  "original_grid": 1,
  "scenario_grid": 12,
  "before": { "podium_probability": 0.8293, "...": "..." },
  "after":  { "podium_probability": 0.2867, "...": "..." },
  "delta":  { "podium_probability": -0.5426, "...": "..." },
  "disclaimer": "This is a simulation, not a race forecast..."
}
```

Scenario results are **never persisted** — a simulation must not pollute the
stored prediction history. `persist=true` is likewise ignored when grid
overrides are supplied.

---

## AI Race Analyst

| Method | Path | Description |
|---|---|---|
| `GET` | `/chat/suggestions` | Starter questions |
| `POST` | `/chat` | Ask a question |
| `GET` | `/chat/sessions/{session_id}` | Transcript |
| `POST` | `/chat/insight` | Narrate a chart the user is looking at |

```jsonc
// POST /api/chat
// { "question": "Why might a one-stop strategy be risky at Bahrain?" }
{
  "session_id": "6f2a...",
  "message_id": 12,
  "answer": "...",
  "intent": "tyre_strategy",
  "grounded": true,                 // false => retrieval found nothing
  "citations": [
    { "source": "pit_stops", "detail": "Bahrain International Circuit: stop counts from 98 driver-races" },
    { "source": "circuit_metadata", "detail": "track character (degradation: high, overtaking: low)" }
  ],
  "notes": ["The database covers seasons 2021-2025."],
  "context": { "...": "the exact facts the answer was allowed to use" },
  "generator": "bedrock",           // or "template"
  "fallback_reason": null           // set when Bedrock failed and the narrator answered
}
```

### Grounding contract

1. The question is parsed for entities (drivers, constructors, circuits,
   seasons) and classified into an intent.
2. Matching rows are retrieved from the database through the **same analytics
   module the charts use**, and a citation is recorded for each block.
3. The context pack is passed to Amazon Bedrock with a system prompt forbidding
   any fact not present in it.
4. If Bedrock is disabled or unreachable, a deterministic template narrator
   renders the identical context pack. Answers become less fluent, never less
   accurate.
5. If retrieval found nothing, `grounded` is `false` and the answer says which
   part it cannot address.

The full context pack is returned to the client so the UI can show the user
exactly what the answer rested on.

---

## Feedback & saved comparisons

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/feedback` | optional | Submit a rating |
| `GET` | `/feedback/stats` | – | Aggregate ratings, top complaint reasons |
| `GET` | `/feedback/recent?limit=` | – | Recent submissions |
| `POST` | `/saved` | required | Save a comparison |
| `GET` | `/saved` | required | List saved comparisons |
| `DELETE` | `/saved/{id}` | required | Delete one |

`surface` ∈ `chat | prediction | insight | scenario | comparison | circuit`,
`rating` ∈ `helpful | unhelpful`.

Feedback is accepted anonymously by design — requiring an account would reduce
the sample to near zero, and the ratings are the product's main quality signal.

Deleting another user's saved comparison returns **404, not 403**, so the
endpoint does not confirm that someone else's record exists.

---

## Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create an account (password ≥ 8 chars) |
| `POST` | `/auth/login` | Exchange credentials for a JWT |
| `GET` | `/auth/me` | Current user |

Passwords are bcrypt-hashed (minimum 8 characters, enforced on both the client
and the server). Login returns the same error message whether the email is
unknown or the password is wrong, so the endpoint does not disclose which
addresses are registered.

The token is stored in `localStorage` and re-validated against `/auth/me` on
page load, so a revoked or expired token signs the user out rather than leaving
the UI in a falsely authenticated state.

---

## Errors

Standard HTTP codes with a FastAPI `{"detail": "..."}` body. In production
(`DEBUG=false`) unhandled exceptions return a generic message; the stack trace
goes to the logs, never to the client.

| Code | Meaning |
|---|---|
| 400 | Invalid request (e.g. comparing a driver with themselves) |
| 401 | Missing or invalid token |
| 404 | Not found |
| 409 | Email already registered |
| 422 | Schema validation failure |
| 500 | Unhandled error |
