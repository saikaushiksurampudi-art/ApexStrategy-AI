"""Podium / points-finish model: training, blending, persistence and explanation.

Two binary classifiers share one feature matrix:

* ``podium``   -- P(finish in the top 3)
* ``points``   -- P(finish in the top 10)

Architecture
------------
Each target is scored as a **blend of two components**:

1. a calibrated L2 logistic regression over the engineered features, and
2. the empirical conversion rate for the driver's grid slot.

Starting position is so dominant in Formula 1 that a lookup table of "how often
does P4 finish on the podium" is a genuinely hard baseline. Rather than pretend
otherwise, the model keeps that table as an explicit component and learns how
far to lean on it. The blend weight is chosen on a **held-out validation
season** inside the training range -- never on the test seasons -- so the
reported evaluation stays honest.

Gradient boosting was tried and rejected: with roughly 1,800 training rows it
overfits and scores worse on held-out seasons than the linear model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.features import FEATURE_COLUMNS, FEATURE_LABELS, feature_matrix

logger = logging.getLogger(__name__)

TARGETS = ("podium", "points")
TARGET_COLUMNS = {"podium": "podium", "points": "in_points"}
BLEND_WEIGHTS = (0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0)
MAX_GRID = 20


@dataclass
class ModelBundle:
    """Everything needed to score a driver and explain the score."""

    version: str
    trained_at: str
    feature_columns: List[str]
    estimators: Dict[str, Any]
    grid_rates: Dict[str, Dict[int, float]]
    grid_priors: Dict[str, float]
    blend_weights: Dict[str, float]
    baseline_row: Dict[str, float]
    train_seasons: List[int]
    test_seasons: List[int]
    validation_season: Optional[int] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    n_train_rows: int = 0
    n_test_rows: int = 0

    def metadata(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("estimators")
        return payload


CALIBRATION_FOLDS = 5


def _make_estimator(y: Optional[pd.Series] = None):
    """L2 logistic regression, median-imputed, standardised and calibrated.

    The number of calibration folds is capped by the rarest class: podium
    finishes are a ~15% class, and a small or early-season dataset can hold
    fewer positives than folds, which ``CalibratedClassifierCV`` rejects. When
    there are too few examples to calibrate at all, the bare pipeline is
    returned -- logistic regression outputs usable probabilities on its own, so
    the product degrades in calibration quality rather than failing outright.
    """
    pipeline = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.1, max_iter=2000),
    )
    if y is None:
        return CalibratedClassifierCV(pipeline, method="sigmoid", cv=CALIBRATION_FOLDS)

    smallest_class = int(np.bincount(np.asarray(y, dtype=int)).min())
    folds = min(CALIBRATION_FOLDS, smallest_class)
    if folds < 2:
        logger.warning(
            "Only %s examples in the rarest class -- skipping probability "
            "calibration for this target.",
            smallest_class,
        )
        return pipeline
    if folds < CALIBRATION_FOLDS:
        logger.info("Calibrating with %s folds (rarest class has %s examples)", folds, smallest_class)
    return CalibratedClassifierCV(pipeline, method="sigmoid", cv=folds)


# ---------------------------------------------------------------------------
# Grid-rate component
# ---------------------------------------------------------------------------
def _fit_grid_rates(df: pd.DataFrame, target: str) -> Dict[int, float]:
    """Empirical conversion rate per grid slot, learned on training data only."""
    column = TARGET_COLUMNS[target]
    buckets = df["grid"].fillna(float(MAX_GRID)).clip(1, MAX_GRID).round().astype(int)
    rates = df.groupby(buckets)[column].mean()
    return {int(slot): float(rate) for slot, rate in rates.items()}


def _grid_component(
    grid: pd.Series, rates: Dict[int, float], prior: float
) -> np.ndarray:
    buckets = grid.fillna(float(MAX_GRID)).clip(1, MAX_GRID).round().astype(int)
    return buckets.map(rates).fillna(prior).to_numpy(dtype=float)


def _blend(
    model_probs: np.ndarray, grid_probs: np.ndarray, weight: float
) -> np.ndarray:
    return np.clip(weight * model_probs + (1.0 - weight) * grid_probs, 1e-6, 1 - 1e-6)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def _select_blend_weight(
    df: pd.DataFrame, train_seasons: List[int], target: str
) -> tuple:
    """Choose the blend weight on a validation season carved out of training.

    Returns ``(weight, validation_season, scores_by_weight)``. When there is
    only one training season available there is nothing to validate on, so a
    neutral 0.5 is used and reported as such.
    """
    column = TARGET_COLUMNS[target]
    if len(train_seasons) < 2:
        return 0.5, None, {}

    inner_train_seasons = train_seasons[:-1]
    validation_season = train_seasons[-1]
    inner_train = df[df["season"].isin(inner_train_seasons)]
    validation = df[df["season"] == validation_season]
    if inner_train.empty or validation.empty:
        return 0.5, None, {}

    y_inner = inner_train[column].astype(int)
    if y_inner.nunique() < 2:
        return 0.5, None, {}

    estimator = _make_estimator(y_inner)
    estimator.fit(feature_matrix(inner_train.copy()), y_inner)

    rates = _fit_grid_rates(inner_train, target)
    prior = float(y_inner.mean())

    model_probs = estimator.predict_proba(feature_matrix(validation.copy()))[:, 1]
    grid_probs = _grid_component(validation["grid"], rates, prior)
    y_validation = validation[column].astype(int).to_numpy()

    scores: Dict[float, float] = {}
    for weight in BLEND_WEIGHTS:
        blended = _blend(model_probs, grid_probs, weight)
        scores[weight] = float(log_loss(y_validation, blended, labels=[0, 1]))

    best = min(scores, key=scores.get)
    logger.info(
        "%s: blend weight %.2f chosen on validation season %s (log loss %.4f)",
        target, best, validation_season, scores[best],
    )
    return best, validation_season, {str(k): round(v, 5) for k, v in scores.items()}


def train_model(
    df: pd.DataFrame,
    train_seasons: List[int],
    test_seasons: Optional[List[int]] = None,
    version: Optional[str] = None,
) -> ModelBundle:
    """Fit both classifiers, their grid-rate tables and their blend weights."""
    train_seasons = sorted(train_seasons)
    train_df = df[df["season"].isin(train_seasons)]
    if train_df.empty:
        raise ValueError(f"No training rows for seasons {train_seasons}")

    X_train = feature_matrix(train_df.copy())
    estimators: Dict[str, Any] = {}
    grid_rates: Dict[str, Dict[int, float]] = {}
    grid_priors: Dict[str, float] = {}
    blend_weights: Dict[str, float] = {}
    weight_scores: Dict[str, Any] = {}
    validation_season: Optional[int] = None

    for target in TARGETS:
        column = TARGET_COLUMNS[target]
        y = train_df[column].astype(int)
        if y.nunique() < 2:
            raise ValueError(f"Target '{target}' has a single class in training data")

        weight, validation_season, scores = _select_blend_weight(
            df, train_seasons, target
        )
        blend_weights[target] = weight
        weight_scores[target] = scores

        estimator = _make_estimator(y)
        estimator.fit(X_train, y)
        estimators[target] = estimator
        grid_rates[target] = _fit_grid_rates(train_df, target)
        grid_priors[target] = float(y.mean())

        logger.info(
            "trained %s on %s rows (positive rate %.3f, blend weight %.2f)",
            target, len(y), y.mean(), weight,
        )

    bundle = ModelBundle(
        version=version or datetime.now(timezone.utc).strftime("v%Y%m%d-%H%M%S"),
        trained_at=datetime.now(timezone.utc).isoformat(),
        feature_columns=list(FEATURE_COLUMNS),
        estimators=estimators,
        grid_rates=grid_rates,
        grid_priors=grid_priors,
        blend_weights=blend_weights,
        # Column medians act as the "typical driver" reference point used by
        # the occlusion-based explanation below.
        baseline_row={
            col: float(X_train[col].median()) if X_train[col].notna().any() else 0.0
            for col in FEATURE_COLUMNS
        },
        train_seasons=train_seasons,
        test_seasons=sorted(test_seasons or []),
        validation_season=validation_season,
        n_train_rows=len(train_df),
        n_test_rows=int(df["season"].isin(test_seasons or []).sum()),
    )
    bundle.metrics = {"blend_weight_search": weight_scores}
    return bundle


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_frame(bundle: ModelBundle, frame: pd.DataFrame, target: str) -> np.ndarray:
    """Blended probability for one target over an engineered feature frame."""
    X = feature_matrix(frame.copy())
    model_probs = bundle.estimators[target].predict_proba(
        X[bundle.feature_columns].astype(float)
    )[:, 1]
    grid_probs = _grid_component(
        frame["grid"], bundle.grid_rates[target], bundle.grid_priors[target]
    )
    return _blend(model_probs, grid_probs, bundle.blend_weights[target])


def predict_proba(bundle: ModelBundle, frame: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Blended probabilities for every target.

    ``frame`` must be an engineered frame (it needs the ``grid`` column as well
    as the model features), not a bare feature matrix.
    """
    return {target: score_frame(bundle, frame, target) for target in TARGETS}


def estimate_win_probability(podium_probs: np.ndarray) -> np.ndarray:
    """Turn podium probabilities into a normalised win probability.

    There is exactly one winner per race, so the podium scores are rescaled to
    sum to 1. This is a heuristic ranking-to-probability conversion, not a
    separately trained win classifier, and is labelled as such in the UI.
    """
    total = podium_probs.sum()
    if total <= 0:
        return np.full_like(podium_probs, 1.0 / max(len(podium_probs), 1))
    return podium_probs / total


def expected_positions(podium_probs: np.ndarray, points_probs: np.ndarray) -> np.ndarray:
    """A rough expected finishing position from the two probabilities.

    Drivers are ranked by a blended score and mapped onto 1..N. It gives the
    dashboard an ordering to display; it is not a calibrated position forecast.
    """
    score = 0.65 * podium_probs + 0.35 * points_probs
    order = np.argsort(-score)
    positions = np.empty_like(score)
    positions[order] = np.arange(1, len(score) + 1)
    return positions


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------
def explain_prediction(
    bundle: ModelBundle,
    row: pd.Series,
    target: str = "podium",
    top_n: int = 4,
) -> List[Dict[str, Any]]:
    """Attribute a prediction to individual features by occlusion.

    Each feature in turn is replaced with the training median and the whole
    model -- including the grid-rate component -- is re-scored. The resulting
    change in probability is that feature's contribution: positive means the
    driver's actual value *helped*.

    This is a model-agnostic approximation (features are perturbed one at a
    time, so interactions are not split out), but it is faithful in the sense
    that every number shown comes from re-running the real model.
    """
    columns = list(bundle.feature_columns)
    if "grid" not in columns:
        columns.append("grid")

    # Float throughout: occlusion writes float medians into these cells, and
    # an int64 column would raise on assignment in future pandas versions.
    base_frame = pd.DataFrame([{col: row.get(col) for col in columns}]).astype(float)
    actual = float(score_frame(bundle, base_frame, target)[0])

    variants: List[pd.DataFrame] = []
    names: List[str] = []
    for column in bundle.feature_columns:
        value = row.get(column)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            continue
        occluded = base_frame.copy()
        occluded.at[0, column] = bundle.baseline_row.get(column, 0.0)
        variants.append(occluded)
        names.append(column)

    if not variants:
        return []

    stacked = pd.concat(variants, ignore_index=True)
    occluded_probs = score_frame(bundle, stacked, target)

    contributions = []
    for name, occluded_prob in zip(names, occluded_probs):
        delta = actual - float(occluded_prob)
        if abs(delta) < 0.005:  # ignore noise-level effects
            continue
        contributions.append(
            {
                "feature": name,
                "label": FEATURE_LABELS.get(name, name),
                "value": round(float(row[name]), 3),
                "baseline": round(float(bundle.baseline_row.get(name, 0.0)), 3),
                "impact": round(delta, 4),
                "direction": "increases" if delta > 0 else "decreases",
            }
        )

    contributions.sort(key=lambda c: abs(c["impact"]), reverse=True)
    return contributions[:top_n]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_bundle(bundle: ModelBundle, path: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, target)
    meta_path = target.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(bundle.metadata(), indent=2, default=str))
    logger.info("saved model %s -> %s", bundle.version, target)
    return str(target)


def load_bundle(path: str) -> Optional[ModelBundle]:
    target = Path(path)
    if not target.exists():
        logger.warning("no model artifact at %s", target)
        return None
    try:
        return joblib.load(target)
    except Exception as exc:  # pragma: no cover - corrupted artifact
        logger.error("could not load model at %s: %s", target, exc)
        return None
