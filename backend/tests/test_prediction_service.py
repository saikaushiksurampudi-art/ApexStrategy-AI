"""Prediction service: entry lists, feature assembly, scoring and scenarios."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.ml.features import build_features, load_results_frame
from app.ml.model import train_model
from app.models import QualifyingResult, Race
from app.services import prediction as prediction_service


@pytest.fixture()
def trained_model(db_session, monkeypatch):
    """Train on the fixture data and inject it into the prediction service."""
    df = build_features(load_results_frame(db_session))
    bundle = train_model(df, train_seasons=[2023, 2024], test_seasons=[2025])
    monkeypatch.setattr(prediction_service, "get_model", lambda *a, **k: bundle)
    return bundle


def _race(db_session, season, rnd) -> Race:
    return db_session.scalar(select(Race).where(Race.season == season, Race.round == rnd))


# ---------------------------------------------------------------------------
# Entry list
# ---------------------------------------------------------------------------
def test_entry_list_uses_qualifying_when_available(db_session):
    race = _race(db_session, 2025, 2)
    entries = prediction_service._entry_list(db_session, race)
    assert len(entries) == 4
    assert all(entry.grid_source == "qualifying" for entry in entries)
    assert sorted(entry.grid for entry in entries) == [1.0, 2.0, 3.0, 4.0]


def test_entry_list_projects_a_grid_for_an_unraced_round(db_session):
    """An upcoming race has no qualifying, so the grid must be projected."""
    race = Race(
        season=2026,
        round=1,
        name="Future Grand Prix",
        circuit_id=_race(db_session, 2025, 1).circuit_id,
        is_completed=False,
        weather="dry",
    )
    db_session.add(race)
    db_session.commit()

    entries = prediction_service._entry_list(db_session, race)
    assert len(entries) == 4
    assert all(entry.grid_source == "projected" for entry in entries)
    # A projection is a full 1..N ordering, never ties.
    assert sorted(entry.grid for entry in entries) == [1.0, 2.0, 3.0, 4.0]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def test_predict_race_scores_the_whole_field(db_session, trained_model):
    race = _race(db_session, 2025, 2)
    result = prediction_service.predict_race(db_session, race)

    assert result["available"] is True
    assert len(result["predictions"]) == 4
    assert result["model_version"] == trained_model.version
    assert "disclaimer" in result

    for entry in result["predictions"]:
        assert 0.0 < entry["podium_probability"] < 1.0
        assert 0.0 < entry["points_probability"] < 1.0
        assert entry["expected_position"] >= 1


def test_predictions_are_sorted_by_podium_probability(db_session, trained_model):
    result = prediction_service.predict_race(db_session, _race(db_session, 2025, 2))
    probabilities = [p["podium_probability"] for p in result["predictions"]]
    assert probabilities == sorted(probabilities, reverse=True)


def test_win_probabilities_sum_to_one(db_session, trained_model):
    """There is exactly one winner, so the normalised win column must total 1."""
    result = prediction_service.predict_race(db_session, _race(db_session, 2025, 2))
    total = sum(p["win_probability"] for p in result["predictions"])
    assert total == pytest.approx(1.0, abs=0.01)


def test_expected_positions_are_a_permutation(db_session, trained_model):
    result = prediction_service.predict_race(db_session, _race(db_session, 2025, 2))
    positions = sorted(p["expected_position"] for p in result["predictions"])
    assert positions == [1, 2, 3, 4]


def test_features_are_reported_for_traceability(db_session, trained_model):
    result = prediction_service.predict_race(db_session, _race(db_session, 2025, 2))
    entry = result["predictions"][0]
    assert set(entry["features"]) == set(trained_model.feature_columns)


def test_predictions_can_be_persisted(db_session, trained_model):
    from app.models import Prediction

    race = _race(db_session, 2025, 2)
    prediction_service.predict_race(db_session, race, persist=True)
    stored = db_session.scalars(
        select(Prediction).where(Prediction.race_id == race.id)
    ).all()
    assert len(stored) == 4
    assert all(row.model_version == trained_model.version for row in stored)
    assert all(row.features for row in stored)

    # Re-running must update in place rather than duplicating.
    prediction_service.predict_race(db_session, race, persist=True)
    again = db_session.scalars(
        select(Prediction).where(Prediction.race_id == race.id)
    ).all()
    assert len(again) == 4


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
def test_scenario_moving_backwards_lowers_the_podium_estimate(db_session, trained_model):
    race = _race(db_session, 2025, 2)
    pole_sitter = db_session.scalar(
        select(QualifyingResult).where(
            QualifyingResult.race_id == race.id, QualifyingResult.position == 1
        )
    )

    result = prediction_service.scenario(
        db_session, race, pole_sitter.driver_id, grid=4
    )
    assert result["available"] is True
    assert result["original_grid"] == 1
    assert result["scenario_grid"] == 4
    assert result["after"]["podium_probability"] < result["before"]["podium_probability"]
    assert result["delta"]["podium_probability"] < 0
    assert "simulation" in result["disclaimer"].lower()


def test_scenario_moving_forwards_raises_the_podium_estimate(db_session, trained_model):
    race = _race(db_session, 2025, 2)
    backmarker = db_session.scalar(
        select(QualifyingResult).where(
            QualifyingResult.race_id == race.id, QualifyingResult.position == 4
        )
    )
    result = prediction_service.scenario(
        db_session, race, backmarker.driver_id, grid=1
    )
    assert result["after"]["podium_probability"] > result["before"]["podium_probability"]


def test_scenario_for_a_driver_not_entered(db_session, trained_model):
    race = _race(db_session, 2025, 2)
    result = prediction_service.scenario(db_session, race, driver_id=99999, grid=1)
    assert result["available"] is False


def test_scenario_results_are_never_persisted(db_session, trained_model):
    """A simulation is hypothetical and must not pollute stored predictions."""
    from app.models import Prediction

    race = _race(db_session, 2025, 2)
    pole = db_session.scalar(
        select(QualifyingResult).where(
            QualifyingResult.race_id == race.id, QualifyingResult.position == 1
        )
    )
    prediction_service.predict_race(
        db_session, race, grid_overrides={pole.driver_id: 10}, persist=True
    )
    assert db_session.scalars(select(Prediction)).all() == []


def test_model_status_without_an_artifact(monkeypatch):
    monkeypatch.setattr(prediction_service, "get_model", lambda *a, **k: None)
    status = prediction_service.model_status()
    assert status["available"] is False
    assert "train_model" in status["message"]
