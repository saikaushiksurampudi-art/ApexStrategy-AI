"""Evaluate the podium model against simple, transparent baselines.

A model is only worth shipping if it beats what a fan could do on the back of a
napkin, so every run reports:

* **grid_rule**      -- "the top 3 on the grid get the podium" (a hard 0/1 rule)
* **grid_base_rate** -- historical podium rate for that grid slot, from training
                        data only (a genuinely competitive probabilistic baseline)
* **class_prior**    -- always predict the overall base rate

Scoring uses log loss and Brier score (probability quality) alongside ROC AUC
and accuracy (ranking and classification quality). A reliability table then
checks calibration directly: of the drivers given ~30%, did ~30% get there?
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.model import ModelBundle, predict_proba

logger = logging.getLogger(__name__)

TARGET_COLUMNS = {"podium": "podium", "points": "in_points"}

# Finer at the low end, where most podium probabilities sit.
CALIBRATION_EDGES = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def _safe_metric(fn, *args, **kwargs) -> float:
    """Metrics like ROC AUC are undefined on a single-class slice."""
    try:
        return round(float(fn(*args, **kwargs)), 4)
    except ValueError:
        return float("nan")


def score_probabilities(y_true: np.ndarray, probs: np.ndarray) -> Dict[str, float]:
    clipped = np.clip(probs, 1e-6, 1 - 1e-6)
    predicted_label = (probs >= 0.5).astype(int)
    return {
        "log_loss": _safe_metric(log_loss, y_true, clipped, labels=[0, 1]),
        "brier": _safe_metric(brier_score_loss, y_true, probs),
        "roc_auc": _safe_metric(roc_auc_score, y_true, probs),
        "accuracy": _safe_metric(accuracy_score, y_true, predicted_label),
        "precision": _safe_metric(
            precision_score, y_true, predicted_label, zero_division=0
        ),
        "recall": _safe_metric(recall_score, y_true, predicted_label, zero_division=0),
    }


def _wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple:
    """95% interval for an observed rate; stays sensible for small bins."""
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def calibration_table(y_true: np.ndarray, probs: np.ndarray) -> Dict[str, Any]:
    """Reliability table: mean predicted vs. observed rate per probability bin.

    A well-calibrated model sits on the diagonal. Each bin carries its count
    and a Wilson interval, because a bin of eight drivers proves very little
    and the table should say so rather than imply precision it lacks.
    """
    edges = np.array(CALIBRATION_EDGES)
    # right=True puts exactly 0.0 in the first bin; clip keeps 1.0 in the last.
    idx = np.clip(np.digitize(probs, edges[1:-1], right=True), 0, len(edges) - 2)
    bins: List[Dict[str, Any]] = []
    ece = 0.0
    for i in range(len(edges) - 1):
        mask = idx == i
        n = int(mask.sum())
        if n == 0:
            continue
        predicted = float(probs[mask].mean())
        hits = int(y_true[mask].sum())
        observed = hits / n
        low, high = _wilson_interval(hits, n)
        ece += n / len(probs) * abs(predicted - observed)
        bins.append(
            {
                "lower": float(edges[i]),
                "upper": float(edges[i + 1]),
                "n": n,
                "mean_predicted": round(predicted, 4),
                "observed_rate": round(observed, 4),
                "observed_low": round(low, 4),
                "observed_high": round(high, 4),
            }
        )
    return {"bins": bins, "expected_calibration_error": round(ece, 4)}


def grid_rule_baseline(test: pd.DataFrame, target: str) -> np.ndarray:
    """Deterministic rule: front rows convert, everyone else does not."""
    cutoff = 3 if target == "podium" else 10
    grid = test["grid"].fillna(20.0)
    # Expressed as probabilities so it can be scored on the same footing.
    return np.where(grid <= cutoff, 0.95, 0.05)


def grid_base_rate_baseline(
    train: pd.DataFrame, test: pd.DataFrame, target: str
) -> np.ndarray:
    """Empirical rate of the target for each grid slot, learned on train only."""
    column = TARGET_COLUMNS[target]
    train = train.copy()
    train["grid_bucket"] = train["grid"].fillna(20.0).clip(1, 20).round().astype(int)
    rates = train.groupby("grid_bucket")[column].mean()
    prior = float(train[column].mean())

    buckets = test["grid"].fillna(20.0).clip(1, 20).round().astype(int)
    return buckets.map(rates).fillna(prior).to_numpy(dtype=float)


def class_prior_baseline(train: pd.DataFrame, test: pd.DataFrame, target: str) -> np.ndarray:
    prior = float(train[TARGET_COLUMNS[target]].mean())
    return np.full(len(test), prior)


def evaluate(
    bundle: ModelBundle, df: pd.DataFrame, test_seasons: List[int]
) -> Dict[str, Any]:
    """Compare the model with every baseline on held-out seasons."""
    train = df[df["season"].isin(bundle.train_seasons)]
    test = df[df["season"].isin(test_seasons)]
    if test.empty:
        raise ValueError(f"No rows for test seasons {test_seasons}")

    model_probs = predict_proba(bundle, test)

    report: Dict[str, Any] = {
        "model_version": bundle.version,
        "blend_weights": bundle.blend_weights,
        "validation_season": bundle.validation_season,
        "train_seasons": bundle.train_seasons,
        "test_seasons": sorted(test_seasons),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "targets": {},
    }

    for target, column in TARGET_COLUMNS.items():
        y_true = test[column].astype(int).to_numpy()
        candidates = {
            "model": model_probs[target],
            "grid_base_rate": grid_base_rate_baseline(train, test, target),
            "grid_rule": grid_rule_baseline(test, target),
            "class_prior": class_prior_baseline(train, test, target),
        }
        scores = {
            name: score_probabilities(y_true, probs)
            for name, probs in candidates.items()
        }

        model_ll = scores["model"]["log_loss"]
        best_baseline_name = min(
            (n for n in scores if n != "model"),
            key=lambda n: scores[n]["log_loss"],
        )
        best_baseline_ll = scores[best_baseline_name]["log_loss"]

        report["targets"][target] = {
            "positive_rate": round(float(y_true.mean()), 4),
            "scores": scores,
            "best_baseline": best_baseline_name,
            "log_loss_improvement": round(best_baseline_ll - model_ll, 4),
            "beats_baseline": bool(model_ll < best_baseline_ll),
            "calibration": calibration_table(y_true, np.asarray(model_probs[target])),
        }

    return report


def format_report(report: Dict[str, Any]) -> str:
    """Render an evaluation report as a console table."""
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append(f"Model {report['model_version']}")
    lines.append(
        f"  train seasons {report['train_seasons']} ({report['n_train']} rows)"
        f"  ->  test seasons {report['test_seasons']} ({report['n_test']} rows)"
    )
    if report.get("validation_season"):
        lines.append(
            f"  blend weights {report.get('blend_weights')} "
            f"(selected on validation season {report['validation_season']})"
        )
    for target, block in report["targets"].items():
        lines.append("-" * 78)
        lines.append(
            f"TARGET: {target}   (actual rate in test set: {block['positive_rate']:.1%})"
        )
        header = f"  {'approach':<18}{'log loss':>10}{'brier':>9}{'roc auc':>9}{'acc':>8}{'prec':>8}{'rec':>8}"
        lines.append(header)
        for name, scores in block["scores"].items():
            lines.append(
                f"  {name:<18}{scores['log_loss']:>10.4f}{scores['brier']:>9.4f}"
                f"{scores['roc_auc']:>9.4f}{scores['accuracy']:>8.3f}"
                f"{scores['precision']:>8.3f}{scores['recall']:>8.3f}"
            )
        verdict = "BEATS" if block["beats_baseline"] else "DOES NOT BEAT"
        lines.append(
            f"  -> model {verdict} the best baseline ({block['best_baseline']}) "
            f"by {block['log_loss_improvement']:+.4f} log loss"
        )
        calibration = block.get("calibration")
        if calibration:
            lines.append(
                f"  calibration (ECE {calibration['expected_calibration_error']:.4f}):"
                f"  {'bin':<12}{'n':>5}{'predicted':>11}{'observed':>10}"
            )
            for b in calibration["bins"]:
                label = f"{b['lower']:.0%}-{b['upper']:.0%}"
                lines.append(
                    f"  {'':<26}{label:<12}{b['n']:>5}"
                    f"{b['mean_predicted']:>11.1%}{b['observed_rate']:>10.1%}"
                )
    lines.append("=" * 78)
    return "\n".join(lines)
