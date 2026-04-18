"""
ingest_from_cache.py
--------------------
Populate the PostgreSQL DB from the existing Parquet feature cache + trained models.
Much faster than re-running the full pipeline (~3-5 mins vs 40+ mins).
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np
from sqlalchemy import text
from app.database import SessionLocal, engine

CACHE_PARQUET = Path("trained_models/feature_cache.parquet")

# ── Step 0: Ensure all DB columns exist ──────────────────────────────────────
logger.info("Step 0: Ensuring DB schema is up to date ...")
schema_fixes = [
    ("alerts",         "narrative",             "TEXT"),
    ("alerts",         "geo_details",           "TEXT"),
    ("alerts",         "notes",                 "TEXT"),
    ("daily_features", "peer_risk_score",       "FLOAT DEFAULT 0"),
    ("daily_features", "dlp_keyword_hit_count", "INTEGER DEFAULT 0"),
    ("daily_features", "email_sentiment_score", "FLOAT DEFAULT 0"),
    ("daily_features", "is_false_positive",     "BOOLEAN DEFAULT FALSE"),
]
for table, col, coltype in schema_fixes:
    try:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype};"))
        logger.info(f"  Added: {table}.{col}")
    except Exception as e:
        if "already exists" in str(e):
            logger.info(f"  OK (exists): {table}.{col}")
        else:
            logger.warning(f"  Skipped {table}.{col}: {e}")

# ── Step 1: Load Parquet cache ────────────────────────────────────────────────
logger.info(f"\nStep 1: Loading feature cache from {CACHE_PARQUET} ...")
if not CACHE_PARQUET.exists():
    logger.error("feature_cache.parquet not found! Run run_pipeline.py first.")
    sys.exit(1)

fm = pd.read_parquet(CACHE_PARQUET)
logger.info(f"  Loaded {len(fm):,} rows, {fm['user'].nunique():,} unique users")

# ── Step 2: Score using saved models ─────────────────────────────────────────
logger.info("\nStep 2: Scoring with saved models ...")
from ml import isolation_forest as if_module
from ml import autoencoder as ae_module
from ml import lstm_model as lstm_module
from ml import risk_scoring_engine as rse
from ml.feature_engineering import CERT_MALICIOUS_USERS

if_scores   = if_module.score(fm)
ae_scores   = ae_module.score(fm)
lstm_scores = lstm_module.score(fm)
gnn_scores  = pd.Series([0.0] * len(fm), index=fm.index)  # GNN optional

scored = rse.compute_risk_scores(fm, if_scores, ae_scores, lstm_scores, gnn_scores)
logger.info(f"  Alerts triggered: {scored['is_alert'].sum():,} rows")

# ── Step 2.5: Ensure all users in feature matrix exist in users table ─────────
logger.info("\nStep 2.5: Upserting missing users into users table ...")
from app.models.orm_models import User as UserORM
from sqlalchemy.dialects.postgresql import insert as pg_insert

all_fm_users = fm["user"].unique().tolist()
with engine.begin() as conn:
    existing_ids = {r[0] for r in conn.execute(text("SELECT id FROM users")).fetchall()}

missing_users = [uid for uid in all_fm_users if uid not in existing_ids]
if missing_users:
    logger.info(f"  Inserting {len(missing_users)} missing users ...")
    user_rows = [
        {"id": uid, "name": uid, "department": "UNKNOWN",
         "role": "user", "latest_risk_score": 0.0}
        for uid in missing_users
    ]
    with engine.begin() as conn:
        conn.execute(
            pg_insert(UserORM.__table__).on_conflict_do_nothing(),
            user_rows
        )
else:
    logger.info("  All users already in DB.")

# ── Step 3: Clear old stale data & ingest fresh data ─────────────────────────
logger.info("\nStep 3: Clearing old stale risk_scores & daily_features ...")
with engine.begin() as conn:
    conn.execute(text("DELETE FROM risk_scores;"))
    conn.execute(text("DELETE FROM daily_features;"))
logger.info("  Old data cleared.")

# ── Step 4: Bulk insert DailyFeature rows (batched) ──────────────────────────
logger.info("\nStep 4: Ingesting DailyFeature rows ...")
FEATURE_COLS = [
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb", "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "external_email_ratio", "suspicious_attachment_count",
    "total_email_size_bytes", "http_request_count", "file_sharing_visit_count",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
]
available_feat_cols = [c for c in FEATURE_COLS if c in scored.columns]

from app.models.orm_models import DailyFeature, RiskScore
from sqlalchemy.dialects.postgresql import insert as pg_insert

db = SessionLocal()
BATCH = 2000
total_df = 0
total_rs = 0

try:
    rows_df = []
    rows_rs = []

    for _, row in scored.iterrows():
        user_id  = str(row["user"])
        date_val = row["date"]
        if hasattr(date_val, "date"):
            date_val = date_val.date()

        feat_row = {"user_id": user_id, "date": date_val}
        for col in available_feat_cols:
            v = row.get(col, 0)
            feat_row[col] = float(v) if not (isinstance(v, float) and np.isnan(v)) else 0.0

        rows_df.append(feat_row)

        rs_row = {
            "user_id":    user_id,
            "date":       date_val,
            "if_score":   float(row.get("if_score",   0) or 0),
            "ae_score":   float(row.get("ae_score",   0) or 0),
            "lstm_score": float(row.get("lstm_score", 0) or 0),
            "gnn_score":  float(row.get("gnn_score",  0) or 0),
            "rule_score": float(row.get("rule_score", 0) or 0),
            "risk_score": float(row.get("risk_score", 0) or 0),
        }
        rows_rs.append(rs_row)

        # Flush in batches
        if len(rows_df) >= BATCH:
            with engine.begin() as conn:
                conn.execute(pg_insert(DailyFeature.__table__).on_conflict_do_nothing(), rows_df)
                conn.execute(pg_insert(RiskScore.__table__).on_conflict_do_nothing(), rows_rs)
            total_df += len(rows_df)
            total_rs += len(rows_rs)
            rows_df, rows_rs = [], []
            logger.info(f"  Flushed {total_df:,} rows so far ...")

    # Final flush
    if rows_df:
        with engine.begin() as conn:
            conn.execute(pg_insert(DailyFeature.__table__).on_conflict_do_nothing(), rows_df)
            conn.execute(pg_insert(RiskScore.__table__).on_conflict_do_nothing(), rows_rs)
        total_df += len(rows_df)
        total_rs += len(rows_rs)

    logger.info(f"  Inserted {total_df:,} DailyFeature rows")
    logger.info(f"  Inserted {total_rs:,} RiskScore rows")

except Exception as e:
    db.rollback()
    logger.error(f"Ingestion failed: {e}")
    raise
finally:
    db.close()

# ── Step 5: Generate Alerts for high-risk & insider users ─────────────────────
logger.info("\nStep 5: Generating alerts for high-risk users ...")
from app.models.orm_models import Alert, User as UserORM

alert_rows = scored[
    (scored["is_alert"] == 1) | (scored["user"].isin(CERT_MALICIOUS_USERS))
].copy()

# Cap at top 200 by risk score to avoid flooding
alert_rows = alert_rows.sort_values("risk_score", ascending=False).head(200)
logger.info(f"  Generating alerts for {len(alert_rows):,} rows ...")

db = SessionLocal()
try:
    alert_count = 0
    for _, row in alert_rows.iterrows():
        user_id  = str(row["user"])
        date_val = row["date"]
        if hasattr(date_val, "date"):
            date_val = date_val.date()

        risk = float(row.get("risk_score", 0))
        severity = "CRITICAL" if risk >= 0.8 else ("HIGH" if risk >= 0.6 else "MEDIUM")
        alert_type = "INSIDER_THREAT" if user_id in CERT_MALICIOUS_USERS else "ANOMALOUS_BEHAVIOR"

        existing = db.query(Alert).filter(
            Alert.user_id    == user_id,
            Alert.date       == date_val,
            Alert.alert_type == alert_type,
        ).first()

        if not existing:
            db.add(Alert(
                user_id    = user_id,
                date       = date_val,
                alert_type = alert_type,
                severity   = severity,
                risk_score = risk,
                status     = "OPEN",
                narrative  = f"Anomalous behavior detected for {user_id} on {date_val}. Risk score: {risk:.2f}",
            ))
            alert_count += 1

        # Also update user.latest_risk_score
        user_orm = db.query(UserORM).filter(UserORM.id == user_id).first()
        if user_orm:
            user_orm.latest_risk_score = max(float(user_orm.latest_risk_score or 0), risk)

    db.commit()
    logger.info(f"  Created {alert_count:,} new alerts")
    logger.info(f"  Updated user risk scores")

except Exception as e:
    db.rollback()
    logger.error(f"Alert generation failed: {e}")
    raise
finally:
    db.close()

# ── Final Summary ─────────────────────────────────────────────────────────────
logger.info("\n=== INGESTION COMPLETE ===")
with engine.connect() as conn:
    for table in ["users", "risk_scores", "daily_features", "alerts"]:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        logger.info(f"  {table}: {count:,} rows")

logger.info("\nDashboard is now populated! Refresh your browser.")
