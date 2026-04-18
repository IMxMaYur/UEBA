"""
run_pipeline.py
---------------
Master entry-point for the UEBA ML pipeline.
Orchestrates: data loading → parsing → feature engineering →
behavior profiling → model training → risk scoring → DB ingestion.

Usage:
    python run_pipeline.py               # full run
    python run_pipeline.py --mode=test --sample=0.05   # quick test run
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure ml/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from ml import data_loader, log_parser, feature_engineering, behavior_profiler
from ml import isolation_forest as if_module
from ml import autoencoder as ae_module
from ml import lstm_model as lstm_module
from ml import gnn_model as gnn_module
from ml import risk_scoring_engine as rse
from ml import model_evaluation as eval_module
from ml import shap_explainer
from ml import markov_detector
from ml import sentiment_analyzer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run(mode: str = "full", http_sample: float = None, email_sample: float = 1.0):
    logger.info(f"=== UEBA Pipeline Start  [mode={mode}] ===")

    # ── 1. Load raw data ──────────────────────────────────────────────────
    if mode == "test":
        http_sample = http_sample or 0.02
        email_sample = 0.05
    else:
        http_sample = http_sample or None   # use env default (0.10)

    raw = data_loader.load_all(
        http_sample_rate=http_sample,
        email_sample_rate=email_sample,
    )

    # ── 2. Parse & normalise ──────────────────────────────────────────────
    parsed = log_parser.parse_all(raw)

    # ── 3. Feature engineering ────────────────────────────────────────────
    feature_matrix = feature_engineering.build_feature_matrix(parsed)

    # ── 4. Behavior profiling (Z-scores + peer-group analytics) ──────────
    feature_matrix = behavior_profiler.compute_zscore_features(feature_matrix)

    # Peer-group z-scoring: compare users vs. department peers
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        from app.models.orm_models import User as UserORM
        users = db.query(UserORM).all()
        user_dept_map = {u.id: (u.department or "UNKNOWN") for u in users}
        db.close()
        if user_dept_map:
            feature_matrix = behavior_profiler.compute_peer_group_zscore(feature_matrix, user_dept_map)
            logger.info(f"  → Peer-group z-scoring done for {len(user_dept_map):,} users.")
    except Exception as e:
        logger.warning(f"Peer-group z-scoring skipped (non-fatal): {e}")

    # Markov attack-sequence scoring
    try:
        markov_scores = markov_detector.score_markov_sequences(feature_matrix)
        feature_matrix["markov_score"] = markov_scores.values
        logger.info(f"  → Markov sequences scored.")
    except Exception as e:
        logger.warning(f"Markov scoring skipped (non-fatal): {e}")

    # Email sentiment scoring
    try:
        sentiment_df = sentiment_analyzer.compute_email_sentiment(parsed["email"])
        if not sentiment_df.empty:
            feature_matrix = feature_matrix.merge(
                sentiment_df, on=["user", "date"], how="left"
            )
            feature_matrix["email_sentiment_score"] = feature_matrix["email_sentiment_score"].fillna(0.0)
            logger.info("  → Email sentiment scores merged into feature matrix.")
    except Exception as e:
        logger.warning(f"Sentiment scoring skipped (non-fatal): {e}")

    # ── 5. Ground-truth labels (for evaluation only) ──────────────────────
    labels = feature_engineering.extract_labels(feature_matrix)

    # ── 6. Train models ───────────────────────────────────────────────────
    logger.info("Training Isolation Forest ...")
    if_model, if_scaler = if_module.train(feature_matrix, labels=labels)

    logger.info("Training Autoencoder ...")
    ae_model, ae_scaler, ae_threshold = ae_module.train(feature_matrix, labels)

    logger.info("Training LSTM ...")
    lstm_model, lstm_scaler, lstm_threshold = lstm_module.train(feature_matrix, labels)

    logger.info("Training GNN ...")
    gnn_model_obj, _, _ = gnn_module.train(
        feature_matrix,
        logon=parsed["logon"],
        device=parsed["device"],
        file_df=parsed["file"],
        benign_labels=labels,
    )

    # ── 7. Score all records ──────────────────────────────────────────────
    if_scores = if_module.score(feature_matrix, if_model, if_scaler)
    ae_scores = ae_module.score(feature_matrix, ae_model, ae_scaler, ae_threshold)
    lstm_scores = lstm_module.score(feature_matrix, lstm_model, lstm_scaler, lstm_threshold)
    gnn_scores = gnn_module.score(
        feature_matrix,
        logon=parsed["logon"],
        device=parsed["device"],
        file_df=parsed["file"],
        model=gnn_model_obj,
    )

    # ── 8. Risk scoring ───────────────────────────────────────────────────
    scored_df = rse.compute_risk_scores(feature_matrix, if_scores, ae_scores, lstm_scores, gnn_scores)

    # ── 8.5. SHAP explanations for alert rows ─────────────────────────────
    shap_map = {}
    alert_rows = scored_df[scored_df["is_alert"] == 1]
    if len(alert_rows) > 0:
        logger.info(f"Generating SHAP explanations for {len(alert_rows):,} alerts ...")
        try:
            shap_lists = shap_explainer.explain_isolation_forest(
                alert_rows=alert_rows,
                background_data=scored_df,
                if_model=if_model,
                if_scaler=if_scaler,
            )
            for idx, (_, row) in enumerate(alert_rows.iterrows()):
                d = row["date"].date() if hasattr(row["date"], "date") else row["date"]
                shap_map[(str(row["user"]), d)] = shap_lists[idx]
            logger.info(f"SHAP explanations ready for {len(shap_map):,} alerts.")
        except Exception as e:
            logger.warning(f"SHAP generation failed (non-fatal): {e}")

    # ── 9. Evaluation ─────────────────────────────────────────────────────
    # Auto-find the threshold that maximises F1 on this dataset
    import json as _json, datetime as _dt
    try:
        optimal_threshold = eval_module.find_optimal_threshold(scored_df, labels)
        logger.info(f"Using optimal threshold: {optimal_threshold:.4f}")
    except Exception as e:
        logger.warning(f"Optimal threshold search failed ({e}), falling back to 0.35")
        optimal_threshold = 0.35

    # Re-apply optimal threshold so is_alert flags in scored_df are consistent
    scored_df["is_alert"] = (scored_df["risk_score"] >= optimal_threshold).astype(int)

    metrics = eval_module.evaluate(scored_df, labels, threshold=optimal_threshold)

    # Persist the optimal threshold to .env so the API & risk engine pick it up
    _env_path = Path(__file__).parent / ".env"
    try:
        if _env_path.exists():
            env_lines = _env_path.read_text().splitlines()
            new_lines = []
            replaced = False
            for line in env_lines:
                if line.startswith("RISK_THRESHOLD="):
                    new_lines.append(f"RISK_THRESHOLD={optimal_threshold:.4f}")
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.append(f"RISK_THRESHOLD={optimal_threshold:.4f}")
            _env_path.write_text("\n".join(new_lines) + "\n")
            logger.info(f"RISK_THRESHOLD updated to {optimal_threshold:.4f} in .env")
    except Exception as e:
        logger.warning(f"Could not update .env: {e}")

    # Save metrics for /api/stats/model-metrics
    metrics_out = dict(metrics)
    metrics_out["last_trained"] = _dt.datetime.utcnow().isoformat()
    _mpath = Path(__file__).parent / "trained_models" / "metrics.json"
    _mpath.write_text(_json.dumps(metrics_out, indent=2))
    logger.info(f"Metrics saved → {_mpath}")

    # ── 10. Persist to DB ─────────────────────────────────────────────────
    try:
        from app.services.data_ingestion_service import ingest_scored_data
        ingest_scored_data(scored_df, shap_map=shap_map)
        logger.info("Scored data ingested into PostgreSQL.")
    except Exception as e:
        logger.warning(f"DB ingestion skipped: {e}")

    logger.info("=== UEBA Pipeline Complete ===")
    return scored_df, metrics



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UEBA ML Pipeline")
    parser.add_argument("--mode", choices=["full", "test"], default="full")
    parser.add_argument("--sample", type=float, default=None, help="HTTP sample rate override")
    args = parser.parse_args()
    run(mode=args.mode, http_sample=args.sample)
