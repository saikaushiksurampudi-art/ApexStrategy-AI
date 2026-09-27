"""Turn the trained model into race-weekend predictions.

The awkward part of predicting an *upcoming* race is that its feature row does
not exist yet. The approach here is to build a synthetic entry list, append it
to the historical frame and re-run the ordinary feature pipeline. Because every
rolling feature is shifted by one race, the synthetic rows automatically pick up
history-only values -- the same code path that produced the training data.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.features import build_features, load_results_frame
from app.ml.model import (
    ModelBundle,
    estimate_win_probability,
    expected_positions,
    explain_prediction,
    load_bundle,
    predict_proba,
)
from app.models import (
    Constructor,
    Driver,
    Prediction,
    QualifyingResult,
    Race,
    RaceResult,
)

logger = logging.getLogger(__name__)

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: Dict[str, Optional[ModelBundle]] = {"bundle": None, "loaded": False}


# ---------------------------------------------------------------------------
# Model access
# ---------------------------------------------------------------------------
def _fetch_model_from_s3() -> bool:
    """Pull the latest model artifact from S3 into the local model path.

    Container images deliberately ship without a model: artifacts are large,
    change on a different cadence to the code, and are produced by a separate
    training job. In AWS the artifact therefore lives in S3, and this is what
    bridges the two at start-up. Returns True when a file was downloaded.
    """
    if not settings.s3_bucket:
        return False
    try:
        import boto3

        client = boto3.client("s3", region_name=settings.aws_region)
        response = client.list_objects_v2(
            Bucket=settings.s3_bucket, Prefix=settings.s3_model_prefix
        )
        candidates = [
            item
            for item in response.get("Contents", [])
            if item["Key"].endswith(settings.model_file)
        ]
        if not candidates:
            logger.info("No model artifact under s3://%s/%s", settings.s3_bucket, settings.s3_model_prefix)
            return False

        newest = max(candidates, key=lambda item: item["LastModified"])
        Path(settings.model_path).parent.mkdir(parents=True, exist_ok=True)
        client.download_file(settings.s3_bucket, newest["Key"], settings.model_path)
        logger.info("Downloaded model from s3://%s/%s", settings.s3_bucket, newest["Key"])
        return True
    except Exception as exc:  # pragma: no cover - depends on AWS environment
        logger.warning("Could not fetch a model from S3: %s", exc)
        return False


def get_model(force_reload: bool = False) -> Optional[ModelBundle]:
    """Load the model artifact once and cache it for the process lifetime.

    Looks locally first, then falls back to S3. A missing model is not fatal:
    the prediction endpoints report that they are unavailable and the rest of
    the product carries on working.
    """
    with _MODEL_LOCK:
        if force_reload or not _MODEL_CACHE["loaded"]:
            bundle = load_bundle(settings.model_path)
            if bundle is None and _fetch_model_from_s3():
                bundle = load_bundle(settings.model_path)
            _MODEL_CACHE["bundle"] = bundle
            _MODEL_CACHE["loaded"] = True
        return _MODEL_CACHE["bundle"]


def model_status() -> Dict[str, Any]:
    bundle = get_model()
    if bundle is None:
        return {
            "available": False,
            "message": (
                "No trained model found. Run `python -m scripts.train_model` "
                "after ingesting data."
            ),
        }
    metrics = bundle.metrics.get("targets", {}) if bundle.metrics else {}
    return {
        "available": True,
        "version": bundle.version,
        "trained_at": bundle.trained_at,
        "train_seasons": bundle.train_seasons,
        "test_seasons": bundle.test_seasons,
        "n_train_rows": bundle.n_train_rows,
        "features": bundle.feature_columns,
        "evaluation": {
            target: {
                "model": block["scores"]["model"],
                "best_baseline": block["best_baseline"],
                "baseline_scores": block["scores"][block["best_baseline"]],
                "beats_baseline": block["beats_baseline"],
                "log_loss_improvement": block["log_loss_improvement"],
            }
            for target, block in metrics.items()
        },
    }


# ---------------------------------------------------------------------------
# Entry list construction
# ---------------------------------------------------------------------------
@dataclass
class Entry:
    driver_id: int
    constructor_id: int
    grid: float
    grid_source: str  # "qualifying" | "projected" | "scenario"


def _entry_list(db: Session, race: Race) -> List[Entry]:
    """Work out who is racing and where they will start."""
    qualifying = db.execute(
        select(QualifyingResult).where(QualifyingResult.race_id == race.id)
    ).scalars().all()
    if qualifying:
        return [
            Entry(q.driver_id, q.constructor_id, float(q.position), "qualifying")
            for q in qualifying
        ]

    results = db.execute(
        select(RaceResult).where(RaceResult.race_id == race.id)
    ).scalars().all()
    if results:
        return [
            Entry(
                r.driver_id,
                r.constructor_id,
                float(r.grid) if r.grid else 20.0,
                "qualifying",
            )
            for r in results
        ]

    # Nothing for this race yet: carry the last completed race's entry list
    # forward and project a grid from recent qualifying form.
    previous = db.scalars(
        select(Race)
        .where(
            Race.is_completed.is_(True),
            (Race.season < race.season)
            | ((Race.season == race.season) & (Race.round < race.round)),
        )
        .order_by(Race.season.desc(), Race.round.desc())
        .limit(1)
    ).first()
    if previous is None:
        return []

    field = db.execute(
        select(RaceResult.driver_id, RaceResult.constructor_id).where(
            RaceResult.race_id == previous.id
        )
    ).all()

    projected = _projected_grid(db, [driver_id for driver_id, _ in field], race)
    return [
        Entry(driver_id, constructor_id, projected.get(driver_id, 20.0), "projected")
        for driver_id, constructor_id in field
    ]


def _projected_grid(
    db: Session, driver_ids: List[int], race: Race, window: int = 3
) -> Dict[int, float]:
    """Rank drivers by their recent average qualifying position."""
    averages: Dict[int, float] = {}
    for driver_id in driver_ids:
        rows = db.execute(
            select(QualifyingResult.position)
            .join(Race, QualifyingResult.race_id == Race.id)
            .where(
                QualifyingResult.driver_id == driver_id,
                (Race.season < race.season)
                | ((Race.season == race.season) & (Race.round < race.round)),
            )
            .order_by(Race.season.desc(), Race.round.desc())
            .limit(window)
        ).all()
        positions = [p for (p,) in rows if p]
        averages[driver_id] = sum(positions) / len(positions) if positions else 20.0

    ordered = sorted(averages.items(), key=lambda kv: kv[1])
    return {driver_id: float(rank) for rank, (driver_id, _) in enumerate(ordered, start=1)}


# ---------------------------------------------------------------------------
# Feature assembly for a target race
# ---------------------------------------------------------------------------
def build_race_features(
    db: Session, race: Race, entries: List[Entry]
) -> pd.DataFrame:
    """Return one feature row per entry for ``race``."""
    history = load_results_frame(db)
    history = history[
        (history["season"] < race.season)
        | ((history["season"] == race.season) & (history["round"] < race.round))
    ]

    synthetic = pd.DataFrame(
        [
            {
                "race_id": race.id,
                "driver_id": entry.driver_id,
                "constructor_id": entry.constructor_id,
                "grid": entry.grid,
                "position": np.nan,
                "points": 0.0,
                "finished": False,
                "season": race.season,
                "round": race.round,
                "date": race.date,
                "circuit_id": race.circuit_id,
                "weather": race.weather or "dry",
                "circuit_ref": race.circuit.ref,
                "overtaking_difficulty": race.circuit.overtaking_difficulty,
                "tyre_degradation": race.circuit.tyre_degradation,
                "circuit_type": race.circuit.circuit_type,
                "quali_position": entry.grid,
                "quali_best_ms": np.nan,
                "q3_ms": np.nan,
                "pole_ms": np.nan,
            }
            for entry in entries
        ]
    )

    # Real qualifying times, when the session has actually run.
    quali_rows = db.execute(
        select(QualifyingResult).where(QualifyingResult.race_id == race.id)
    ).scalars().all()
    if quali_rows:
        pole_ms = min((q.best_ms for q in quali_rows if q.best_ms), default=None)
        by_driver = {q.driver_id: q for q in quali_rows}
        for index, row in synthetic.iterrows():
            quali = by_driver.get(row["driver_id"])
            if quali:
                synthetic.at[index, "quali_position"] = float(quali.position)
                synthetic.at[index, "quali_best_ms"] = quali.best_ms
                synthetic.at[index, "q3_ms"] = quali.q3_ms
                synthetic.at[index, "pole_ms"] = pole_ms

    combined = pd.concat([history, synthetic], ignore_index=True)
    engineered = build_features(combined)
    return engineered[engineered["race_id"] == race.id].copy()


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def predict_race(
    db: Session,
    race: Race,
    grid_overrides: Optional[Dict[int, int]] = None,
    explain: bool = True,
    persist: bool = False,
) -> Dict[str, Any]:
    """Score every driver for one race.

    ``grid_overrides`` maps driver_id -> grid slot and powers the scenario
    explorer. Results built with overrides are marked as simulations and are
    never written to the predictions table.
    """
    bundle = get_model()
    if bundle is None:
        return {
            "available": False,
            "message": model_status()["message"],
            "race_id": race.id,
            "predictions": [],
        }

    entries = _entry_list(db, race)
    if not entries:
        return {
            "available": False,
            "message": "No entry list could be determined for this race.",
            "race_id": race.id,
            "predictions": [],
        }

    if grid_overrides:
        for entry in entries:
            if entry.driver_id in grid_overrides:
                entry.grid = float(grid_overrides[entry.driver_id])
                entry.grid_source = "scenario"

    frame = build_race_features(db, race, entries)
    if frame.empty:
        return {
            "available": False,
            "message": "Not enough history to build features for this race.",
            "race_id": race.id,
            "predictions": [],
        }

    probabilities = predict_proba(bundle, frame)
    podium = probabilities["podium"]
    points = probabilities["points"]
    win = estimate_win_probability(podium)
    expected = expected_positions(podium, points)

    drivers = {
        d.id: d
        for d in db.scalars(
            select(Driver).where(Driver.id.in_(frame["driver_id"].tolist()))
        )
    }
    constructors = {
        c.id: c
        for c in db.scalars(
            select(Constructor).where(
                Constructor.id.in_(frame["constructor_id"].tolist())
            )
        )
    }
    grid_source = {entry.driver_id: entry.grid_source for entry in entries}

    predictions: List[Dict[str, Any]] = []
    for position_index, (_, row) in enumerate(frame.iterrows()):
        driver = drivers.get(int(row["driver_id"]))
        constructor = constructors.get(int(row["constructor_id"]))
        if driver is None:
            continue

        factors = (
            explain_prediction(bundle, row, target="podium")
            if explain
            else []
        )
        predictions.append(
            {
                "driver_id": driver.id,
                "ref": driver.ref,
                "driver": f"{driver.given_name} {driver.family_name}",
                "code": driver.code,
                "constructor": constructor.name if constructor else None,
                "color": constructor.color if constructor else "#9AA0A6",
                "image_url": driver.image_url,
                "image_author": driver.image_author,
                "image_license": driver.image_license,
                "grid": int(row["grid"]) if pd.notna(row["grid"]) else None,
                "grid_source": grid_source.get(driver.id, "projected"),
                "podium_probability": round(float(podium[position_index]), 4),
                "points_probability": round(float(points[position_index]), 4),
                "win_probability": round(float(win[position_index]), 4),
                "expected_position": int(expected[position_index]),
                "top_factors": factors,
                "features": {
                    column: (
                        None
                        if pd.isna(row[column])
                        else round(float(row[column]), 4)
                    )
                    for column in bundle.feature_columns
                },
            }
        )

    predictions.sort(key=lambda p: -p["podium_probability"])

    if persist and not grid_overrides:
        _persist(db, race, bundle, predictions)

    return {
        "available": True,
        "race_id": race.id,
        "race": race.name,
        "season": race.season,
        "round": race.round,
        "circuit": race.circuit.name,
        "date": race.date.isoformat() if race.date else None,
        "is_completed": race.is_completed,
        "is_simulation": bool(grid_overrides),
        "model_version": bundle.version,
        "grid_source": "scenario"
        if grid_overrides
        else (entries[0].grid_source if entries else "projected"),
        "predictions": predictions,
        "disclaimer": (
            "These are model estimates based on historical data, not forecasts of "
            "what will happen. Probabilities are calibrated on past seasons and do "
            "not account for crashes, penalties, reliability failures or weather "
            "changes on the day."
        ),
    }


def _persist(
    db: Session, race: Race, bundle: ModelBundle, predictions: List[Dict[str, Any]]
) -> None:
    """Store predictions so an explanation can be traced back to its inputs."""
    for item in predictions:
        row = db.scalar(
            select(Prediction).where(
                Prediction.race_id == race.id,
                Prediction.driver_id == item["driver_id"],
                Prediction.model_version == bundle.version,
            )
        )
        if row is None:
            row = Prediction(
                race_id=race.id,
                driver_id=item["driver_id"],
                model_version=bundle.version,
            )
            db.add(row)
        row.constructor_id = None
        row.podium_probability = item["podium_probability"]
        row.points_probability = item["points_probability"]
        row.win_probability = item["win_probability"]
        row.expected_position = item["expected_position"]
        row.features = item["features"]
        row.top_factors = item["top_factors"]
    db.commit()


def scenario(
    db: Session, race: Race, driver_id: int, grid: int
) -> Dict[str, Any]:
    """Re-score a race with one driver moved to a different grid slot."""
    baseline = predict_race(db, race, explain=False)
    if not baseline.get("available"):
        return baseline

    simulated = predict_race(db, race, grid_overrides={driver_id: grid}, explain=True)
    before = next(
        (p for p in baseline["predictions"] if p["driver_id"] == driver_id), None
    )
    after = next(
        (p for p in simulated["predictions"] if p["driver_id"] == driver_id), None
    )
    if before is None or after is None:
        return {
            "available": False,
            "message": "That driver is not on the entry list for this race.",
        }

    return {
        "available": True,
        "race": baseline["race"],
        "race_id": race.id,
        "driver": after["driver"],
        "driver_id": driver_id,
        "original_grid": before["grid"],
        "scenario_grid": grid,
        "before": {
            "podium_probability": before["podium_probability"],
            "points_probability": before["points_probability"],
            "win_probability": before["win_probability"],
            "expected_position": before["expected_position"],
        },
        "after": {
            "podium_probability": after["podium_probability"],
            "points_probability": after["points_probability"],
            "win_probability": after["win_probability"],
            "expected_position": after["expected_position"],
        },
        "delta": {
            "podium_probability": round(
                after["podium_probability"] - before["podium_probability"], 4
            ),
            "points_probability": round(
                after["points_probability"] - before["points_probability"], 4
            ),
            "expected_position": after["expected_position"]
            - before["expected_position"],
        },
        "top_factors": after["top_factors"],
        "field": simulated["predictions"],
        "disclaimer": (
            "This is a simulation, not a race forecast. Only the starting grid was "
            "changed; everything else -- car pace, reliability, strategy and "
            "weather -- is held at its current estimate."
        ),
    }
