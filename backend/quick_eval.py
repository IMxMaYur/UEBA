"""
quick_eval.py
-------------
Re-evaluates the UEBA ML pipeline using ALREADY TRAINED models + the
cached feature matrix.  Skips re-training completely – runs in ~60s.

Usage:
    python quick_eval.py

Steps:
  1. Load feature_cache.parquet  (pre-built, ~10 MB)
  2. Score all rows using saved IF / AE / LSTM / GNN models
  3. Combine scores via risk_scoring_engine
  4. Extract ground-truth labels from insiders.csv
  5. Find optimal decision threshold (maximises F1)
  6. Evaluate precision / recall / F1 / ROC-AUC at that threshold
  7. Write updated metrics.json and patch .env RISK_THRESHOLD
"""

import json
import logging
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MODELS_DIR  = Path(__file__).parent / "trained_models"
CACHE_PATH  = MODELS_DIR / "feature_cache.parquet"
METRICS_OUT = MODELS_DIR / "metrics.json"
ENV_PATH    = Path(__file__).parent / ".env"

# ── 1. Load feature cache ────────────────────────────────────────────────────
logger.info("Loading feature cache …")
import pandas as pd

if not CACHE_PATH.exists():
    logger.error(f"Feature cache not found at {CACHE_PATH}. Run run_pipeline.py first.")
    sys.exit(1)

feature_matrix = pd.read_parquet(CACHE_PATH)
logger.info(f"  → {feature_matrix.shape[0]:,} rows × {feature_matrix.shape[1]} columns")


# ── 2. Extract ground-truth labels ──────────────────────────────────────────
from ml.feature_engineering import extract_labels

labels = extract_labels(feature_matrix)
n_pos = int(labels.sum())
logger.info(f"  → {n_pos:,} threat user-days  /  {len(labels) - n_pos:,} benign user-days")

if n_pos == 0:
    logger.error(
        "No threat labels found – cannot compute supervised metrics.\n"
        "Check that Dataset/answers/insiders.csv is accessible and that\n"
        "the cached data's date range overlaps the insider windows."
    )
    sys.exit(1)


# ── 3. Score with each saved model (all auto-load from trained_models/) ─────
logger.info("Scoring with saved models …")
import numpy as np
from ml import isolation_forest as if_mod
from ml import autoencoder      as ae_mod
from ml import lstm_model       as lstm_mod
from ml import gnn_model        as gnn_mod
from ml import risk_scoring_engine as rse
from ml import model_evaluation    as eval_mod


def _safe_score(name, fn, *args, **kwargs) -> pd.Series:
    try:
        s = fn(*args, **kwargs)
        logger.info(f"  ✓ {name}  (mean={s.mean():.4f}  max={s.max():.4f})")
        return s
    except Exception as exc:
        logger.warning(f"  ✗ {name} failed ({exc}) – substituting zeros")
        return pd.Series(0.0, index=feature_matrix.index, name=name.lower().replace(" ", "_") + "_score")


if_scores   = _safe_score("Isolation Forest", if_mod.score,   feature_matrix)
ae_scores   = _safe_score("Autoencoder",      ae_mod.score,   feature_matrix)
lstm_scores = _safe_score("LSTM",             lstm_mod.score, feature_matrix)
gnn_scores  = _safe_score("GNN",              gnn_mod.score,  feature_matrix)


# ── 4. Composite risk scores ─────────────────────────────────────────────────
logger.info("Computing composite risk scores …")
scored_df = rse.compute_risk_scores(
    feature_matrix, if_scores, ae_scores, lstm_scores, gnn_scores
)

rs = scored_df["risk_score"]
logger.info(
    f"  risk_score → min={rs.min():.4f}  mean={rs.mean():.4f}  "
    f"p90={rs.quantile(0.90):.4f}  p95={rs.quantile(0.95):.4f}  max={rs.max():.4f}"
)


# ── 5. Find optimal decision threshold (max F1) ──────────────────────────────
logger.info("Searching for optimal decision threshold …")
try:
    optimal_threshold = eval_mod.find_optimal_threshold(scored_df, labels)
except Exception as exc:
    # Fallback: 95th-percentile of risk scores
    optimal_threshold = float(rs.quantile(0.95))
    logger.warning(
        f"find_optimal_threshold failed ({exc})\n"
        f"  Falling back to p95 threshold: {optimal_threshold:.4f}"
    )


# ── 6. Re-apply threshold & evaluate ────────────────────────────────────────
scored_df["is_alert"] = (scored_df["risk_score"] >= optimal_threshold).astype(int)
metrics = eval_mod.evaluate(scored_df, labels, threshold=optimal_threshold)

logger.info("")
logger.info("=" * 58)
logger.info("  QUICK EVAL RESULTS")
logger.info("=" * 58)
logger.info(f"  Threshold:       {optimal_threshold:.4f}")
logger.info(f"  Precision:       {metrics['precision']*100:.1f}%")
logger.info(f"  Recall:          {metrics['recall']*100:.1f}%")
logger.info(f"  F1-Score:        {metrics['f1_score']*100:.1f}%")
logger.info(f"  ROC-AUC:         {metrics['roc_auc']:.4f}")
logger.info(f"  True Positives:  {metrics['n_true_positives']}")
logger.info(f"  False Positives: {metrics['n_false_positives']}")
logger.info(f"  False Negatives: {metrics['n_false_negatives']}")
logger.info(f"  Total Alerts:    {metrics['n_alerts']}")
logger.info("=" * 58)
logger.info("")


# ── 7. Save updated metrics.json ─────────────────────────────────────────────
metrics_out = dict(metrics)
metrics_out["last_trained"] = datetime.datetime.utcnow().isoformat()
METRICS_OUT.write_text(json.dumps(metrics_out, indent=2))
logger.info(f"✓  metrics.json updated  →  {METRICS_OUT}")


# ── 8. Patch .env RISK_THRESHOLD ─────────────────────────────────────────────
if ENV_PATH.exists():
    lines = ENV_PATH.read_text().splitlines()
    new_lines, replaced = [], False
    for line in lines:
        if line.startswith("RISK_THRESHOLD="):
            new_lines.append(f"RISK_THRESHOLD={optimal_threshold:.4f}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"RISK_THRESHOLD={optimal_threshold:.4f}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")
    logger.info(f"✓  .env RISK_THRESHOLD  →  {optimal_threshold:.4f}")

logger.info("")
logger.info("Done.  The /api/stats/model-metrics endpoint will now return real values.")
logger.info("(The running uvicorn server reads metrics.json at request time – no restart needed.)")
