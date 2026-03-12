"""
cert_detector.py  (optimised)
------------------------------
STRATEGY (3-tier, fastest-first):

  Tier 1 – DB Query (fastest, milliseconds)
    If run_pipeline.py has already been run, the DB contains pre-computed
    risk_scores and daily_features for every CERT user.  We just query the DB
    for the user whose anomaly pattern best matches the requested scenario.
    No CSV reading, no model inference needed.

  Tier 2 – Parquet cache (fast, seconds)
    If the DB is empty but a feature_cache.parquet exists in trained_models/,
    load from Parquet (10-50× faster than CSV) and run saved models in inference-only
    mode (no retraining).  Parquet is written automatically after each CSV load.

  Tier 3 – CSV fallback (slow, use only when nothing else is available)
    Load CSVs with aggressive sampling (5% HTTP, 10% email) to keep it manageable.
    After processing, cache the feature matrix to Parquet so tiers 1-2 work next time.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

BACKEND_DIR   = Path(__file__).parent.parent
MODEL_DIR     = BACKEND_DIR / "trained_models"
CACHE_PARQUET = MODEL_DIR / "feature_cache.parquet"

# Add backend to sys.path so ml.* imports work from app context
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Scenario → DB column to sort by (for Tier-1 DB query)
# ---------------------------------------------------------------------------
SCENARIO_PROFILE = {
    "data_exfiltration":    {"col": "file_copy_count",          "min": 1.0,  "alert_type": "DATA_EXFILTRATION",  "severity": "CRITICAL"},
    "privilege_abuse":      {"col": "unique_pcs",               "min": 2.0,  "alert_type": "PRIVILEGE_ABUSE",    "severity": "HIGH"},
    "credential_compromise":{"col": "login_count",              "min": 5.0,  "alert_type": "SUSPICIOUS_LOGIN",   "severity": "HIGH"},
    "mass_download":        {"col": "http_request_count",       "min": 50.0, "alert_type": "MASS_DATA_DOWNLOAD", "severity": "HIGH"},
    "sabotage":             {"col": "after_hours_activity_total","min": 1.0,  "alert_type": "POTENTIAL_SABOTAGE", "severity": "CRITICAL"},
}

# DailyFeature columns the DB allows
DAILY_FEATURE_COLS = {
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb", "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "external_email_ratio", "suspicious_attachment_count",
    "total_email_size_bytes", "http_request_count", "file_sharing_visit_count",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
}

# In-process Parquet cache (avoid even disk reads if called twice in same process)
_FM_MEMORY_CACHE: Optional[pd.DataFrame] = None
_PARSED_MEMORY_CACHE: Optional[dict]     = None


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 – query pre-computed DB results
# ─────────────────────────────────────────────────────────────────────────────
def _detect_from_db(scenario_name: str, db) -> Optional[dict]:
    """
    Query PostgreSQL for the best matching real user.
    Returns None if the DB has no pipeline data.
    """
    try:
        from app.models.orm_models import User, DailyFeature, RiskScore, Alert
        from sqlalchemy import func, desc

        cfg = SCENARIO_PROFILE[scenario_name]
        col = cfg["col"]

        # Check if DB has any risk data at all
        count = db.query(func.count(RiskScore.id)).scalar()
        if not count:
            logger.info("cert_detector Tier-1: DB empty, falling through to Tier-2.")
            return None

        # Find user with best risk_score × scenario-specific feature
        # Join RiskScore ↔ DailyFeature to get both scores and feature values
        feat_col = getattr(DailyFeature, col, None)
        if feat_col is None:
            # Fallback: just pick highest risk user
            top_rs = (
                db.query(RiskScore)
                .filter(RiskScore.user_id.notlike("SIM_%"))
                .order_by(desc(RiskScore.risk_score))
                .first()
            )
        else:
            top_rs = (
                db.query(RiskScore)
                .join(DailyFeature,
                      (DailyFeature.user_id == RiskScore.user_id) &
                      (DailyFeature.date    == RiskScore.date))
                .filter(RiskScore.user_id.notlike("SIM_%"))
                .filter(feat_col >= cfg["min"])
                .order_by(desc(RiskScore.risk_score))
                .first()
            )

        if not top_rs:
            # Relax filter — just pick highest risk
            top_rs = (
                db.query(RiskScore)
                .filter(RiskScore.user_id.notlike("SIM_%"))
                .order_by(desc(RiskScore.risk_score))
                .first()
            )

        if not top_rs:
            return None

        # Fetch matching DailyFeature row for the feature snapshot
        df_row = (
            db.query(DailyFeature)
            .filter(DailyFeature.user_id == top_rs.user_id,
                    DailyFeature.date    == top_rs.date)
            .first()
        )

        # Fetch existing SHAP from alert if available
        alert = (
            db.query(Alert)
            .filter(Alert.user_id == top_rs.user_id)
            .order_by(desc(Alert.risk_score))
            .first()
        )
        shap_values = alert.shap_json if alert and alert.shap_json else []

        feature_row = {}
        if df_row:
            for col_name in DAILY_FEATURE_COLS:
                v = getattr(df_row, col_name, None)
                if v is not None:
                    feature_row[col_name] = float(v)

        logger.info(f"cert_detector Tier-1 ✓  user={top_rs.user_id} risk={top_rs.risk_score:.3f}")
        return {
            "user_id":      top_rs.user_id,
            "risk_score":   float(top_rs.risk_score),
            "date":         str(top_rs.date),
            "alert_type":   cfg["alert_type"],
            "severity":     cfg["severity"],
            "feature_row":  feature_row,
            "shap_values":  shap_values,
            "model_scores": {
                "if_score":   float(top_rs.if_score   or 0),
                "ae_score":   float(top_rs.ae_score   or 0),
                "lstm_score": float(top_rs.lstm_score or 0),
                "gnn_score":  float(top_rs.gnn_score  or 0),
                "rule_score": float(top_rs.rule_score or 0),
            },
        }

    except Exception as e:
        logger.warning(f"cert_detector Tier-1 failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 / 3 – feature matrix (Parquet cache or CSV load → model inference)
# ─────────────────────────────────────────────────────────────────────────────
def _load_feature_matrix() -> tuple:
    """
    Load the feature matrix from (in order of preference):
      a) in-process memory cache
      b) Parquet file (fast, if pipeline was run before)
      c) raw CERT CSVs with aggressive sampling (slow, last resort)
    Returns (feature_matrix_df, parsed_dict)
    """
    global _FM_MEMORY_CACHE, _PARSED_MEMORY_CACHE

    # (a) memory cache
    if _FM_MEMORY_CACHE is not None:
        logger.info("cert_detector: using memory-cached feature matrix.")
        return _FM_MEMORY_CACHE, _PARSED_MEMORY_CACHE

    # (b) Parquet cache
    if CACHE_PARQUET.exists():
        logger.info(f"cert_detector Tier-2: loading feature cache from {CACHE_PARQUET} ...")
        fm = pd.read_parquet(CACHE_PARQUET)
        logger.info(f"  → {len(fm):,} rows loaded from Parquet.")
        _FM_MEMORY_CACHE = fm
        _PARSED_MEMORY_CACHE = None   # parsed not cached in Parquet; GNN will skip
        return fm, None

    # (c) CSV fallback with heavy sampling
    logger.info("cert_detector Tier-3: loading CERT dataset from CSV (sampled) ...")
    from ml import data_loader, log_parser, feature_engineering, behavior_profiler

    raw = data_loader.load_all(
        http_sample_rate=0.05,     # 5% of ~28M rows → ~1.4M
        email_sample_rate=0.10,    # 10% of email
    )
    parsed = log_parser.parse_all(raw)
    fm     = feature_engineering.build_feature_matrix(parsed)
    fm     = behavior_profiler.compute_zscore_features(fm)

    # Save to Parquet so next call uses Tier-2
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        fm.to_parquet(CACHE_PARQUET, index=False)
        logger.info(f"cert_detector: feature cache saved → {CACHE_PARQUET}")
    except Exception as e:
        logger.warning(f"cert_detector: Parquet save failed (non-fatal): {e}")

    _FM_MEMORY_CACHE    = fm
    _PARSED_MEMORY_CACHE = parsed
    return fm, parsed


def _detect_from_models(scenario_name: str) -> dict:
    """
    Tier 2/3: load feature matrix then run saved models (inference-only).
    """
    from ml import isolation_forest as if_module
    from ml import autoencoder      as ae_module
    from ml import lstm_model       as lstm_module
    from ml import gnn_model        as gnn_module
    from ml import risk_scoring_engine as rse
    from ml import shap_explainer

    cfg = SCENARIO_PROFILE[scenario_name]
    fm, parsed = _load_feature_matrix()

    # Filter candidates by scenario feature
    sort_col = cfg["col"]
    if sort_col in fm.columns:
        candidates = fm[fm[sort_col] >= cfg["min"]].copy()
        if len(candidates) == 0:
            candidates = fm.copy()
    else:
        candidates = fm.copy()

    logger.info(f"cert_detector: scoring {len(candidates):,} candidates ...")

    if_scores   = if_module.score(candidates)
    ae_scores   = ae_module.score(candidates)
    lstm_scores = lstm_module.score(candidates)

    # GNN needs parsed data; skip gracefully if not available
    try:
        if parsed:
            gnn_scores = gnn_module.score(candidates, logon=parsed["logon"],
                                          device=parsed["device"], file_df=parsed["file"], model=None)
        else:
            gnn_scores = pd.Series(0.5, index=candidates.index)
    except Exception:
        gnn_scores = pd.Series(0.5, index=candidates.index)

    scored = rse.compute_risk_scores(candidates, if_scores, ae_scores, lstm_scores, gnn_scores)

    if sort_col in scored.columns:
        scored["_rank"] = scored["risk_score"] * scored[sort_col].clip(lower=0)
    else:
        scored["_rank"] = scored["risk_score"]

    top = scored.sort_values("_rank", ascending=False).iloc[0]
    user_id    = str(top["user"])
    risk_score = float(top["risk_score"])
    date_val   = top["date"]
    if hasattr(date_val, "date"):
        date_val = date_val.date()

    model_scores = {k: float(top.get(k, 0)) for k in
                    ["if_score","ae_score","lstm_score","gnn_score","rule_score"]}

    numeric_feats = top.drop(labels=["user","date","risk_score","is_alert","_rank",
                                      "if_score","ae_score","lstm_score","gnn_score","rule_score"],
                              errors="ignore")
    feature_dict = {k: float(v) for k, v in numeric_feats.items()
                    if isinstance(v, (int, float, np.integer, np.floating)) and not np.isnan(float(v))}

    shap_values = []
    try:
        if_model, if_scaler = if_module.load_model()
        shap_lists = shap_explainer.explain_isolation_forest(
            alert_rows=top.to_frame().T.copy(),
            background_data=scored,
            if_model=if_model, if_scaler=if_scaler,
        )
        if shap_lists:
            shap_values = shap_lists[0]
    except Exception as e:
        logger.warning(f"SHAP failed (non-fatal): {e}")

    logger.info(f"cert_detector Tier-2/3 ✓  user={user_id} risk={risk_score:.3f}")
    return {
        "user_id": user_id, "risk_score": risk_score, "date": str(date_val),
        "alert_type": cfg["alert_type"], "severity": cfg["severity"],
        "feature_row": feature_dict, "shap_values": shap_values,
        "model_scores": model_scores,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def detect_scenario(scenario_name: str, db=None) -> dict:
    """
    Main entry point.  Tries Tier-1 (DB) first; falls back to Tier-2/3.
    db: optional SQLAlchemy Session (required for Tier-1).
    """
    if scenario_name not in SCENARIO_PROFILE:
        raise ValueError(f"Unknown scenario: {scenario_name}")

    # Tier 1: query DB if session provided
    if db is not None:
        result = _detect_from_db(scenario_name, db)
        if result:
            return result

    # Tier 2 / 3: feature matrix + model inference
    return _detect_from_models(scenario_name)
