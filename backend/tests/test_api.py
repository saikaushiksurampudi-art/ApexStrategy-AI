"""End-to-end API tests over the FastAPI app."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Health & metadata
# ---------------------------------------------------------------------------
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert body["database"]["races"] == 6


def test_meta_lists_seasons(client):
    body = client.get("/api/meta").json()
    assert body["seasons"] == [2025, 2024, 2023]
    assert body["first_season"] == 2023
    assert body["last_season"] == 2025


# ---------------------------------------------------------------------------
# Races, drivers, circuits
# ---------------------------------------------------------------------------
def test_list_and_filter_races(client):
    assert len(client.get("/api/races").json()) == 6
    assert len(client.get("/api/races?season=2025").json()) == 2


def test_race_detail_includes_results_and_qualifying(client):
    races = client.get("/api/races?season=2025").json()
    detail = client.get(f"/api/races/{races[0]['id']}").json()
    assert len(detail["results"]) == 4
    assert len(detail["qualifying"]) == 4
    assert detail["results"][0]["position"] == 1


def test_race_not_found(client):
    assert client.get("/api/races/999999").status_code == 404


def test_driver_profile(client):
    body = client.get("/api/drivers/apex").json()
    assert body["summary"]["name"] == "Ada Apex"
    assert body["summary"]["wins"] == 4
    assert len(body["progression"]) == 2  # 2025 has two rounds


def test_driver_not_found(client):
    assert client.get("/api/drivers/nobody").status_code == 404


def test_compare_endpoint(client):
    body = client.get("/api/drivers/compare?a=apex&b=bolt").json()
    assert body["shared_races"] == 6
    assert body["race_head_to_head"]["a"] == 4


def test_compare_rejects_identical_drivers(client):
    response = client.get("/api/drivers/compare?a=apex&b=apex")
    assert response.status_code == 400


def test_compare_season_filter(client):
    body = client.get("/api/drivers/compare?a=apex&b=bolt&seasons=2025").json()
    assert body["shared_races"] == 2


def test_circuit_detail(client):
    body = client.get("/api/circuits/alpha").json()
    assert body["circuit"]["name"] == "Alpha Circuit"
    assert body["pole_to_win_rate"]["win_rate"] == 1.0
    assert body["pit_strategy"]["avg_stops"] == 2.0


def test_standings(client):
    body = client.get("/api/seasons/2025/standings").json()
    assert body["drivers"][0]["name"] == "Ada Apex"


def test_standings_missing_season(client):
    assert client.get("/api/seasons/1999/standings").status_code == 404


def test_search(client):
    body = client.get("/api/search?q=alpha").json()
    assert any(c["ref"] == "alpha" for c in body["circuits"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _register(client, email="fan@example.com", password="supersecret1"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Fan"},
    )


def test_register_and_authenticate(client):
    response = _register(client)
    assert response.status_code == 201
    token = response.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "fan@example.com"


def test_duplicate_registration_conflicts(client):
    _register(client)
    assert _register(client).status_code == 409


def test_login_with_wrong_password_fails(client):
    _register(client)
    response = client.post(
        "/api/auth/login", json={"email": "fan@example.com", "password": "wrong-one"}
    )
    assert response.status_code == 401
    # The message must not reveal whether the account exists.
    assert "password" in response.json()["detail"].lower()


def test_short_password_rejected(client):
    response = client.post(
        "/api/auth/register", json={"email": "x@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_me_requires_a_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_saved_comparisons_require_auth(client):
    assert client.get("/api/saved").status_code == 401


def test_saved_comparison_roundtrip(client):
    token = _register(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/saved",
        headers=headers,
        json={"label": "Apex vs Bolt", "kind": "driver", "payload": {"a": "apex", "b": "bolt"}},
    )
    assert created.status_code == 201
    saved_id = created.json()["id"]

    assert len(client.get("/api/saved", headers=headers).json()) == 1
    assert client.delete(f"/api/saved/{saved_id}", headers=headers).status_code == 204
    assert client.get("/api/saved", headers=headers).json() == []


def test_cannot_delete_another_users_saved_comparison(client):
    token_a = _register(client, "a@example.com").json()["access_token"]
    token_b = _register(client, "b@example.com").json()["access_token"]

    created = client.post(
        "/api/saved",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"label": "Mine", "kind": "driver", "payload": {}},
    )
    saved_id = created.json()["id"]

    response = client.delete(
        f"/api/saved/{saved_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404  # not 403: existence is not confirmed


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def test_chat_answers_and_cites(client):
    response = client.post("/api/chat", json={"question": "Compare Apex and Bolt"})
    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert body["intent"] == "comparison"
    assert len(body["citations"]) > 0
    assert body["generator"] == "template"
    assert "Apex" in body["answer"]


def test_chat_says_so_when_it_has_no_data(client):
    """An unanswerable question must not be answered anyway."""
    body = client.post(
        "/api/chat", json={"question": "How did Ayrton Senna do in 1988?"}
    ).json()
    assert body["grounded"] is False or "2023" in " ".join(body["notes"])
    assert "don't have data" in body["answer"] or "no data" in body["answer"].lower()


def test_chat_tyre_strategy_uses_pit_data(client):
    body = client.post(
        "/api/chat", json={"question": "Is a one-stop risky at Alpha Circuit?"}
    ).json()
    assert body["intent"] == "tyre_strategy"
    assert any(c["source"] == "pit_stops" for c in body["citations"])


def test_chat_rejects_empty_question(client):
    assert client.post("/api/chat", json={"question": "  "}).status_code == 422


def test_chat_session_is_persisted(client):
    first = client.post("/api/chat", json={"question": "Compare Apex and Bolt"}).json()
    session_id = first["session_id"]
    client.post(
        "/api/chat", json={"question": "What about Cruz?", "session_id": session_id}
    )
    transcript = client.get(f"/api/chat/sessions/{session_id}").json()
    assert len(transcript["messages"]) == 4  # two questions, two answers


def test_chat_suggestions(client):
    assert len(client.get("/api/chat/suggestions").json()["questions"]) > 0


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------
def test_model_endpoint_reports_availability(client):
    body = client.get("/api/predictions/model").json()
    assert "available" in body


def test_predictions_degrade_gracefully_without_a_model(client, monkeypatch):
    """No trained artifact must produce a clear message, not a 500."""
    monkeypatch.setattr("app.services.prediction.get_model", lambda *a, **k: None)
    body = client.get("/api/predictions/next").json()
    assert body["available"] is False
    assert body["predictions"] == []
    assert "model" in body["message"].lower()


def test_scenario_rejects_unknown_race(client):
    response = client.post(
        "/api/predictions/scenario", json={"race_id": 99999, "driver_id": 1, "grid": 5}
    )
    assert response.status_code == 404


def test_scenario_validates_grid_range(client):
    response = client.post(
        "/api/predictions/scenario", json={"race_id": 1, "driver_id": 1, "grid": 99}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
def test_feedback_accepts_anonymous_ratings(client):
    response = client.post(
        "/api/feedback", json={"surface": "chat", "rating": "helpful", "reference_id": "1"}
    )
    assert response.status_code == 201


def test_feedback_rejects_unknown_surface(client):
    response = client.post("/api/feedback", json={"surface": "banana", "rating": "helpful"})
    assert response.status_code == 422


def test_feedback_rejects_unknown_rating(client):
    response = client.post("/api/feedback", json={"surface": "chat", "rating": "maybe"})
    assert response.status_code == 422


def test_feedback_stats_aggregate(client):
    client.post("/api/feedback", json={"surface": "chat", "rating": "helpful"})
    client.post(
        "/api/feedback",
        json={"surface": "prediction", "rating": "unhelpful", "reason": "too_vague"},
    )
    body = client.get("/api/feedback/stats").json()
    assert body["total"] == 2
    assert body["helpful"] == 1
    assert body["helpful_rate"] == 0.5
    assert body["top_reasons"][0]["reason"] == "too_vague"
