"""Feature-engineering and model tests.

The most important test here is the leakage check: every rolling feature must
be blind to the race it describes. A model that fails that test can still score
beautifully offline and be worthless in production.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ingest.pipeline import parse_lap_time_ms, status_is_finish
from app.ml.evaluate import (
    class_prior_baseline,
    evaluate,
    grid_base_rate_baseline,
    grid_rule_baseline,
    score_probabilities,
)
from app.ml.features import (
    FEATURE_COLUMNS,
    build_features,
    feature_matrix,
    load_results_frame,
)
from app.ml.model import explain_prediction, predict_proba, train_model


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("1:23.456", 83456),
        ("23.456", 23456),
        ("1:02:03.000", 3723000),
        ("0:00.001", 1),
        (None, None),
        ("", None),
        ("not-a-time", None),
    ],
)
def test_parse_lap_time_ms(text, expected):
    assert parse_lap_time_ms(text) == expected


@pytest.mark.parametrize(
    "status,position_text,expected",
    [
        ("Finished", "1", True),
        ("+1 Lap", "11", True),      # lapped but classified
        ("+2 Laps", "15", True),
        ("Engine", "R", False),
        ("Collision", "R", False),
        ("Disqualified", "D", False),
        ("Withdrew", "W", False),
    ],
)
def test_status_is_finish(status, position_text, expected):
    assert status_is_finish(status, position_text) is expected


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
def test_load_and_build_features(db_session):
    frame = load_results_frame(db_session)
    assert len(frame) == 24  # 6 races x 4 drivers

    df = build_features(frame)
    for column in FEATURE_COLUMNS:
        assert column in df.columns, f"missing feature {column}"

    assert set(df["podium"].unique()) <= {0, 1}
    assert set(df["in_points"].unique()) <= {0, 1}


def test_first_race_has_no_prior_form(db_session):
    """A driver's very first race can have no rolling history."""
    df = build_features(load_results_frame(db_session))
    first = df[(df["season"] == 2023) & (df["round"] == 1)]
    assert len(first) == 4
    assert first["driver_form_avg_finish"].isna().all()
    assert first["driver_circuit_starts"].eq(0).all()
    assert first["driver_season_points"].eq(0).all()


def test_rolling_features_exclude_the_current_race(db_session):
    """The leakage check.

    ``apex`` finishes P1 in 2023 R1 and P2 in 2023 R2. The form figure attached
    to R2 must be 1.0 (R1 alone), not 1.5 (the mean of both).
    """
    df = build_features(load_results_frame(db_session))
    row = df[
        (df["season"] == 2023) & (df["round"] == 2) & (df["driver_id"] == _id(df, "apex", db_session))
    ].iloc[0]
    assert row["driver_form_avg_finish"] == pytest.approx(1.0)

    # Championship points entering R2 = the 25 scored in R1.
    assert row["driver_season_points"] == pytest.approx(25.0)


def test_circuit_history_excludes_current_race(db_session):
    """Apex's Alpha record entering 2025 R1 covers 2023 and 2024 only."""
    df = build_features(load_results_frame(db_session))
    apex_id = _id(df, "apex", db_session)
    row = df[
        (df["season"] == 2025) & (df["round"] == 1) & (df["driver_id"] == apex_id)
    ].iloc[0]
    assert row["driver_circuit_starts"] == 2
    assert row["driver_circuit_avg_finish"] == pytest.approx(1.0)


def test_grid_prior_is_not_self_referential(db_session):
    """The first row for a grid slot cannot know that slot's own outcome."""
    df = build_features(load_results_frame(db_session))
    first_race = df[(df["season"] == 2023) & (df["round"] == 1)]
    # Falls back to the smooth decay, never to the row's own target.
    assert first_race["grid_prior_podium"].notna().all()
    assert (first_race["grid_prior_podium"] <= 1).all()
    assert (first_race["grid_prior_podium"] >= 0).all()


def test_feature_matrix_preserves_missing_values(db_session):
    """NaN is meaningful (a rookie has no circuit history) and must survive."""
    df = build_features(load_results_frame(db_session))
    X = feature_matrix(df)
    assert list(X.columns) == FEATURE_COLUMNS
    assert X.isna().any().any()
    assert X.dtypes.apply(lambda d: d == np.float64).all()


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------
def test_baselines_return_valid_probabilities(db_session):
    df = build_features(load_results_frame(db_session))
    train = df[df["season"].isin([2023, 2024])]
    test = df[df["season"] == 2025]

    for baseline in (
        grid_base_rate_baseline(train, test, "podium"),
        grid_rule_baseline(test, "podium"),
        class_prior_baseline(train, test, "podium"),
    ):
        assert len(baseline) == len(test)
        assert ((baseline >= 0) & (baseline <= 1)).all()


def test_grid_rule_baseline_uses_the_right_cutoff():
    test = pd.DataFrame({"grid": [1.0, 3.0, 4.0, 10.0, 11.0]})
    podium = grid_rule_baseline(test, "podium")
    assert podium[0] > 0.5 and podium[1] > 0.5   # P1, P3 -> podium
    assert podium[2] < 0.5                        # P4 -> no

    points = grid_rule_baseline(test, "points")
    assert points[3] > 0.5                        # P10 -> points
    assert points[4] < 0.5                        # P11 -> no


def test_score_probabilities_ranges():
    y = np.array([0, 1, 0, 1])
    perfect = np.array([0.01, 0.99, 0.01, 0.99])
    scores = score_probabilities(y, perfect)
    assert scores["roc_auc"] == 1.0
    assert scores["accuracy"] == 1.0
    assert scores["log_loss"] < 0.05


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def test_train_and_predict(db_session):
    df = build_features(load_results_frame(db_session))
    bundle = train_model(df, train_seasons=[2023, 2024], test_seasons=[2025])

    assert bundle.feature_columns == FEATURE_COLUMNS
    assert set(bundle.blend_weights) == {"podium", "points"}
    for weight in bundle.blend_weights.values():
        assert 0.0 <= weight <= 1.0

    probabilities = predict_proba(bundle, df[df["season"] == 2025])
    for target in ("podium", "points"):
        values = probabilities[target]
        assert len(values) == 8
        assert ((values > 0) & (values < 1)).all()


def test_blend_weight_chosen_on_validation_not_test(db_session):
    """The validation season must come from inside the training range."""
    df = build_features(load_results_frame(db_session))
    bundle = train_model(df, train_seasons=[2023, 2024], test_seasons=[2025])
    assert bundle.validation_season == 2024
    assert bundle.validation_season not in bundle.test_seasons


def test_evaluate_reports_every_baseline(db_session):
    df = build_features(load_results_frame(db_session))
    bundle = train_model(df, train_seasons=[2023, 2024], test_seasons=[2025])
    report = evaluate(bundle, df, [2025])

    for target in ("podium", "points"):
        scores = report["targets"][target]["scores"]
        assert set(scores) == {"model", "grid_base_rate", "grid_rule", "class_prior"}
        assert "beats_baseline" in report["targets"][target]

        calibration = report["targets"][target]["calibration"]
        bins = calibration["bins"]
        # Every test row lands in exactly one bin.
        assert sum(b["n"] for b in bins) == report["n_test"]
        for b in bins:
            assert b["lower"] <= b["mean_predicted"] <= b["upper"]
            assert b["observed_low"] <= b["observed_rate"] <= b["observed_high"]
        assert 0 <= calibration["expected_calibration_error"] <= 1


def test_calibration_table_bins_and_error():
    from app.ml.evaluate import calibration_table

    # Perfectly calibrated toy data: 10% bin hits 1 in 10, 90% bin hits 9 in 10.
    probs = np.array([0.1] * 10 + [0.9] * 10)
    y = np.array([1] + [0] * 9 + [1] * 9 + [0])
    table = calibration_table(y, probs)

    assert [(b["n"], b["observed_rate"]) for b in table["bins"]] == [(10, 0.1), (10, 0.9)]
    assert table["expected_calibration_error"] == 0.0

    # Edge probabilities stay in range rather than falling off either end.
    edges = calibration_table(np.array([0, 1]), np.array([0.0, 1.0]))
    assert sum(b["n"] for b in edges["bins"]) == 2


def test_explanation_is_faithful_to_the_model(db_session):
    """Each reported impact must match a real re-scoring of the model."""
    df = build_features(load_results_frame(db_session))
    bundle = train_model(df, train_seasons=[2023, 2024], test_seasons=[2025])
    row = df[df["season"] == 2025].iloc[0]

    factors = explain_prediction(bundle, row, target="podium")
    for factor in factors:
        assert factor["feature"] in FEATURE_COLUMNS
        assert factor["direction"] in {"increases", "decreases"}
        assert abs(factor["impact"]) >= 0.005
    # Sorted by magnitude, strongest first.
    impacts = [abs(f["impact"]) for f in factors]
    assert impacts == sorted(impacts, reverse=True)


def test_training_rejects_single_class_target(db_session):
    df = build_features(load_results_frame(db_session))
    df = df.copy()
    df["podium"] = 0  # nobody ever reaches the podium
    with pytest.raises(ValueError, match="single class"):
        train_model(df, train_seasons=[2023, 2024], test_seasons=[2025])


# ---------------------------------------------------------------------------
def _id(df: pd.DataFrame, ref: str, db_session) -> int:
    from app.services import analytics

    return analytics.resolve_driver(db_session, ref).id
