"""End-to-end training: load -> engineer -> fit -> evaluate -> persist."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.ml.evaluate import evaluate, format_report
from app.ml.features import build_features, load_results_frame
from app.ml.model import ModelBundle, save_bundle, train_model

logger = logging.getLogger(__name__)


def run_training(
    db: Session,
    train_seasons: Optional[List[int]] = None,
    test_seasons: Optional[List[int]] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Train on earlier seasons and evaluate on later ones.

    The split is chronological on purpose: a random split would let the model
    learn from races that happen after the ones it is tested on.
    """
    frame = load_results_frame(db)
    if frame.empty:
        raise RuntimeError("No completed races in the database -- run the ingest first.")

    df = build_features(frame)
    seasons = sorted(df["season"].unique().tolist())
    logger.info("feature frame: %s rows across seasons %s", len(df), seasons)

    if not train_seasons or not test_seasons:
        if len(seasons) < 2:
            raise RuntimeError("Need at least two seasons of data to train and test.")
        train_seasons = seasons[:-1]
        test_seasons = [seasons[-1]]

    bundle: ModelBundle = train_model(df, train_seasons, test_seasons)
    report = evaluate(bundle, df, test_seasons)
    # Preserve the blend-weight search recorded during training.
    report["blend_weight_search"] = bundle.metrics.get("blend_weight_search", {})
    bundle.metrics = report

    path = save_bundle(bundle, output_path or settings.model_path)
    report_path = Path(path).with_name("evaluation_report.json")
    report_path.write_text(json.dumps(report, indent=2, default=str))

    return {
        "model_path": path,
        "report_path": str(report_path),
        "version": bundle.version,
        "report": report,
        "summary": format_report(report),
    }
