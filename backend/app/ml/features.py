"""Feature engineering for the podium / points-finish model.

Design rule: **every feature must be computable before the race starts.**
All rolling statistics are shifted by one race within their group, so a row for
Round 7 only ever sees data from Rounds 1-6. Breaking that rule would produce
excellent offline scores and worthless predictions.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Circuit, QualifyingResult, Race, RaceResult

logger = logging.getLogger(__name__)

PODIUM_POSITION = 3
POINTS_POSITION = 10
FORM_WINDOW = 5
RELIABILITY_WINDOW = 10

ORDINAL_MAPS: Dict[str, Dict[str, float]] = {
    "overtaking_difficulty": {"low": 0.0, "medium": 1.0, "high": 2.0},
    "tyre_degradation": {"low": 0.0, "medium": 1.0, "high": 2.0},
    "weather": {"dry": 0.0, "mixed": 1.0, "wet": 2.0},
    "circuit_type": {"permanent": 0.0, "hybrid": 1.0, "street": 2.0},
}

FEATURE_COLUMNS: List[str] = [
    "grid",
    "grid_prior_podium",
    "grid_prior_points",
    "quali_position",
    "quali_gap_to_pole_s",
    "reached_q3",
    "driver_form_avg_finish",
    "driver_form_avg_points",
    "driver_form_finish_rate",
    "driver_form_podium_rate",
    "driver_season_points",
    "driver_season_rank",
    "constructor_form_avg_points",
    "constructor_form_finish_rate",
    "constructor_reliability",
    "constructor_season_points",
    "constructor_season_rank",
    "driver_circuit_starts",
    "driver_circuit_avg_finish",
    "driver_circuit_podium_rate",
    "overtaking_difficulty",
    "tyre_degradation",
    "circuit_type",
    "weather",
]

# Human-readable labels used by the explanation layer.
FEATURE_LABELS: Dict[str, str] = {
    "grid": "starting grid position",
    "grid_prior_podium": "historical podium rate from this grid slot",
    "grid_prior_points": "historical points rate from this grid slot",
    "quali_position": "qualifying position",
    "quali_gap_to_pole_s": "qualifying gap to pole (seconds)",
    "reached_q3": "reached Q3",
    "driver_form_avg_finish": f"average finish over the last {FORM_WINDOW} races",
    "driver_form_avg_points": f"average points over the last {FORM_WINDOW} races",
    "driver_form_finish_rate": f"finish rate over the last {FORM_WINDOW} races",
    "driver_form_podium_rate": f"podium rate over the last {FORM_WINDOW} races",
    "driver_season_points": "championship points so far this season",
    "driver_season_rank": "championship position entering the race",
    "constructor_form_avg_points": f"team points per car over the last {FORM_WINDOW} races",
    "constructor_form_finish_rate": f"team finish rate over the last {FORM_WINDOW} races",
    "constructor_reliability": f"team reliability over the last {RELIABILITY_WINDOW} races",
    "constructor_season_points": "constructors' championship points so far",
    "constructor_season_rank": "constructors' championship position",
    "driver_circuit_starts": "previous starts at this circuit",
    "driver_circuit_avg_finish": "average finish at this circuit",
    "driver_circuit_podium_rate": "podium rate at this circuit",
    "overtaking_difficulty": "how hard this circuit is to overtake at",
    "tyre_degradation": "tyre degradation at this circuit",
    "circuit_type": "circuit type (permanent / hybrid / street)",
    "weather": "weather category",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_results_frame(db: Session, include_incomplete: bool = False) -> pd.DataFrame:
    """Load every race entry with its qualifying and circuit context."""
    # Pole time per race, via GROUP BY min() so the query works on SQLite too.
    pole = (
        select(
            QualifyingResult.race_id.label("race_id"),
            func.min(QualifyingResult.best_ms).label("pole_ms"),
        )
        .group_by(QualifyingResult.race_id)
        .subquery()
    )

    query = (
        select(
            RaceResult.race_id,
            RaceResult.driver_id,
            RaceResult.constructor_id,
            RaceResult.grid,
            RaceResult.position,
            RaceResult.points,
            RaceResult.finished,
            Race.season,
            Race.round,
            Race.date,
            Race.circuit_id,
            Race.weather,
            Circuit.ref.label("circuit_ref"),
            Circuit.overtaking_difficulty,
            Circuit.tyre_degradation,
            Circuit.circuit_type,
            QualifyingResult.position.label("quali_position"),
            QualifyingResult.best_ms.label("quali_best_ms"),
            QualifyingResult.q3_ms,
            pole.c.pole_ms,
        )
        .join(Race, RaceResult.race_id == Race.id)
        .join(Circuit, Race.circuit_id == Circuit.id)
        .outerjoin(
            QualifyingResult,
            (QualifyingResult.race_id == RaceResult.race_id)
            & (QualifyingResult.driver_id == RaceResult.driver_id),
        )
        .outerjoin(pole, pole.c.race_id == RaceResult.race_id)
    )
    if not include_incomplete:
        query = query.where(Race.is_completed.is_(True))

    rows = db.execute(query.order_by(Race.season, Race.round)).mappings().all()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["season", "round", "driver_id"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------
def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add model features and targets to a loaded results frame."""
    if frame.empty:
        return frame

    df = frame.copy()
    df["grid"] = df["grid"].replace(0, np.nan)  # 0 = pit lane start in Ergast
    df["finished"] = df["finished"].astype(bool)
    df["podium"] = ((df["position"].notna()) & (df["position"] <= PODIUM_POSITION)).astype(int)
    df["in_points"] = (
        (df["position"].notna()) & (df["position"] <= POINTS_POSITION)
    ).astype(int)
    df["win"] = ((df["position"].notna()) & (df["position"] == 1)).astype(int)

    df["quali_gap_to_pole_s"] = np.where(
        df["quali_best_ms"].notna() & df["pole_ms"].notna(),
        (df["quali_best_ms"] - df["pole_ms"]) / 1000.0,
        np.nan,
    )
    df["reached_q3"] = df["q3_ms"].notna().astype(int)

    # Fall back to grid when a qualifying row is missing (e.g. sprint formats).
    df["quali_position"] = df["quali_position"].fillna(df["grid"])
    df["grid"] = df["grid"].fillna(df["quali_position"])

    df = _add_driver_form(df)
    df = _add_constructor_form(df)
    df = _add_season_standings(df)
    df = _add_circuit_history(df)
    df = _add_grid_priors(df)

    for column, mapping in ORDINAL_MAPS.items():
        df[column] = df[column].map(mapping).astype(float)

    return df


def _rolling_prior(series: pd.Series, window: int, how: str = "mean") -> pd.Series:
    """Rolling statistic over the *previous* rows only."""
    shifted = series.shift(1)
    rolled = shifted.rolling(window, min_periods=1)
    return getattr(rolled, how)()


def _add_driver_form(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("driver_id", sort=False)
    # `position` is NaN for a DNF; treat it as a notional 20th for form purposes
    # so that retirements count against a driver rather than vanishing.
    finish_for_form = df["position"].fillna(20.0)

    df["driver_form_avg_finish"] = (
        finish_for_form.groupby(df["driver_id"])
        .transform(lambda s: _rolling_prior(s, FORM_WINDOW))
    )
    df["driver_form_avg_points"] = grouped["points"].transform(
        lambda s: _rolling_prior(s, FORM_WINDOW)
    )
    df["driver_form_finish_rate"] = (
        df["finished"].astype(float).groupby(df["driver_id"])
        .transform(lambda s: _rolling_prior(s, FORM_WINDOW))
    )
    df["driver_form_podium_rate"] = (
        df["podium"].astype(float).groupby(df["driver_id"])
        .transform(lambda s: _rolling_prior(s, FORM_WINDOW))
    )
    return df


def _add_constructor_form(df: pd.DataFrame) -> pd.DataFrame:
    """Team form, averaged across both cars and shifted to exclude this race."""
    per_race = (
        df.groupby(["constructor_id", "season", "round"], as_index=False)
        .agg(
            race_points=("points", "mean"),
            race_finish_rate=("finished", "mean"),
        )
        .sort_values(["constructor_id", "season", "round"])
    )
    per_race["constructor_form_avg_points"] = per_race.groupby("constructor_id")[
        "race_points"
    ].transform(lambda s: _rolling_prior(s, FORM_WINDOW))
    per_race["constructor_form_finish_rate"] = per_race.groupby("constructor_id")[
        "race_finish_rate"
    ].transform(lambda s: _rolling_prior(s, FORM_WINDOW))
    per_race["constructor_reliability"] = per_race.groupby("constructor_id")[
        "race_finish_rate"
    ].transform(lambda s: _rolling_prior(s, RELIABILITY_WINDOW))

    return df.merge(
        per_race[
            [
                "constructor_id",
                "season",
                "round",
                "constructor_form_avg_points",
                "constructor_form_finish_rate",
                "constructor_reliability",
            ]
        ],
        on=["constructor_id", "season", "round"],
        how="left",
    )


def _add_season_standings(df: pd.DataFrame) -> pd.DataFrame:
    """Championship points and rank *entering* each race."""
    df = df.sort_values(["season", "round", "driver_id"]).reset_index(drop=True)

    df["driver_season_points"] = (
        df.groupby(["driver_id", "season"])["points"]
        .transform(lambda s: s.shift(1).cumsum())
        .fillna(0.0)
    )

    constructor_race_points = (
        df.groupby(["constructor_id", "season", "round"], as_index=False)["points"]
        .sum()
        .sort_values(["constructor_id", "season", "round"])
    )
    constructor_race_points["constructor_season_points"] = (
        constructor_race_points.groupby(["constructor_id", "season"])["points"]
        .transform(lambda s: s.shift(1).cumsum())
        .fillna(0.0)
    )
    df = df.merge(
        constructor_race_points[
            ["constructor_id", "season", "round", "constructor_season_points"]
        ],
        on=["constructor_id", "season", "round"],
        how="left",
    )

    df["driver_season_rank"] = (
        df.groupby(["season", "round"])["driver_season_points"]
        .rank(ascending=False, method="min")
    )
    df["constructor_season_rank"] = (
        df.groupby(["season", "round"])["constructor_season_points"]
        .rank(ascending=False, method="dense")
    )
    return df


def _add_circuit_history(df: pd.DataFrame) -> pd.DataFrame:
    """Expanding record for each driver at each circuit, excluding this race."""
    df = df.sort_values(["driver_id", "circuit_id", "season", "round"]).reset_index(
        drop=True
    )
    grouped = df.groupby(["driver_id", "circuit_id"], sort=False)

    df["driver_circuit_starts"] = grouped.cumcount().astype(float)
    df["driver_circuit_avg_finish"] = (
        df["position"].fillna(20.0)
        .groupby([df["driver_id"], df["circuit_id"]])
        .transform(lambda s: s.shift(1).expanding().mean())
    )
    df["driver_circuit_podium_rate"] = (
        df["podium"].astype(float)
        .groupby([df["driver_id"], df["circuit_id"]])
        .transform(lambda s: s.shift(1).expanding().mean())
    )
    return df.sort_values(["season", "round", "driver_id"]).reset_index(drop=True)


def _add_grid_priors(df: pd.DataFrame) -> pd.DataFrame:
    """Historical conversion rate for each grid slot, as of before this race.

    Starting position is overwhelmingly the strongest signal in F1, and a
    lookup table of "how often does P4 finish on the podium" is a genuinely
    hard baseline to beat. Handing that prior to the model as a feature means
    it starts from baseline-level information and spends its capacity learning
    *adjustments* -- form, reliability, circuit history -- rather than
    re-discovering the shape of the grid curve from scratch.

    The expanding mean is shifted by one row within each grid slot, so a race
    never contributes to its own prior.
    """
    df = df.sort_values(["season", "round", "driver_id"]).reset_index(drop=True)
    bucket = df["grid"].fillna(20.0).clip(1, 20).round().astype(int)

    for source, name in (("podium", "grid_prior_podium"), ("in_points", "grid_prior_points")):
        values = df[source].astype(float)
        df[name] = values.groupby(bucket).transform(
            lambda s: s.shift(1).expanding().mean()
        )
        # Early rows have no history for their slot: fall back to a smooth
        # decay with grid position rather than leaving them empty.
        fallback = np.clip(1.0 - (bucket - 1) / 20.0, 0.02, 0.98)
        cutoff = 3 if source == "podium" else 10
        fallback = np.where(bucket <= cutoff, fallback, fallback * 0.3)
        df[name] = df[name].fillna(pd.Series(fallback, index=df.index))

    return df


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Select the model's input columns, as floats with NaNs preserved.

    NaN is meaningful here (a rookie genuinely has no circuit history), and the
    gradient-boosting model handles missing values natively rather than being
    fed an invented zero.
    """
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    for column in missing:
        df[column] = np.nan
    return df[FEATURE_COLUMNS].astype(float)


def describe_features(row: Dict[str, Optional[float]]) -> List[Dict[str, object]]:
    """Render a feature dict into labelled, human-readable pairs."""
    described = []
    for name in FEATURE_COLUMNS:
        value = row.get(name)
        described.append(
            {
                "feature": name,
                "label": FEATURE_LABELS.get(name, name),
                "value": None if value is None or (isinstance(value, float) and np.isnan(value)) else round(float(value), 4),
            }
        )
    return described
