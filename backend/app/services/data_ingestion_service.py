"""
data_ingestion_service.py
Persists scored feature data from the ML pipeline into PostgreSQL.
"""
import logging
import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.orm_models import User, DailyFeature, RiskScore, Alert
from app.config import settings
from ml.risk_scoring_engine import get_alert_type

logger = logging.getLogger(__name__)


def _severity(risk_score: float) -> str:
    if risk_score >= 0.90: return "CRITICAL"
    if risk_score >= 0.80: return "HIGH"
    if risk_score >= 0.65: return "MEDIUM"
    return "LOW"


def ingest_scored_data(
    scored_df: pd.DataFrame,
    shap_map: Optional[dict] = None,
    db: Session = None,
):
    """
    Upsert users, daily_features, risk_scores, and alerts from scored_df.
    shap_map: optional dict of (user, date) -> shap explanation list.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        users_seen = set()
        for _, row in scored_df.iterrows():
            user_id = str(row["user"])
            record_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]

            # Upsert user
            if user_id not in users_seen:
                existing = db.query(User).filter(User.id == user_id).first()
                if not existing:
                    db.add(User(id=user_id, latest_risk_score=float(row["risk_score"])))
                else:
                    # Update latest risk score if this is newer
                    if float(row["risk_score"]) > existing.latest_risk_score:
                        existing.latest_risk_score = float(row["risk_score"])
                users_seen.add(user_id)

            # Upsert DailyFeature
            feat = db.query(DailyFeature).filter(
                DailyFeature.user_id == user_id, DailyFeature.date == record_date
            ).first()
            feat_data = {
                "login_count": float(row.get("login_count", 0)),
                "after_hours_login_count": float(row.get("after_hours_login_count", 0)),
                "login_hour_mean": float(row.get("login_hour_mean", 0)),
                "unique_pcs": float(row.get("unique_pcs", 0)),
                "usb_connect_count": float(row.get("usb_connect_count", 0)),
                "after_hours_usb": float(row.get("after_hours_usb", 0)),
                "file_copy_count": float(row.get("file_copy_count", 0)),
                "after_hours_file_copy": float(row.get("after_hours_file_copy", 0)),
                "email_sent_count": float(row.get("email_sent_count", 0)),
                "external_email_ratio": float(row.get("external_email_ratio", 0)),
                "suspicious_attachment_count": float(row.get("suspicious_attachment_count", 0)),
                "total_email_size_bytes": float(row.get("total_email_size_bytes", 0)),
                "http_request_count": float(row.get("http_request_count", 0)),
                "file_sharing_visit_count": float(row.get("file_sharing_visit_count", 0)),
                "exfil_indicator": float(row.get("exfil_indicator", 0)),
                "after_hours_activity_total": float(row.get("after_hours_activity_total", 0)),
                "behavior_spike_score": float(row.get("behavior_spike_score", 0)),
            }
            if feat:
                for k, v in feat_data.items():
                    setattr(feat, k, v)
            else:
                db.add(DailyFeature(user_id=user_id, date=record_date, **feat_data))

            # Upsert RiskScore
            rs = db.query(RiskScore).filter(
                RiskScore.user_id == user_id, RiskScore.date == record_date
            ).first()
            rs_data = {
                "if_score": float(row.get("if_score", 0)),
                "ae_score": float(row.get("ae_score", 0)),
                "lstm_score": float(row.get("lstm_score", 0)),
                "gnn_score": float(row.get("gnn_score", 0)),
                "rule_score": float(row.get("rule_score", 0)),
                "risk_score": float(row.get("risk_score", 0)),
            }
            if rs:
                for k, v in rs_data.items():
                    setattr(rs, k, v)
            else:
                db.add(RiskScore(user_id=user_id, date=record_date, **rs_data))

            # Create Alert if threshold exceeded
            if float(row.get("risk_score", 0)) >= settings.risk_threshold:
                existing_alert = db.query(Alert).filter(
                    Alert.user_id == user_id, Alert.date == record_date
                ).first()
                if not existing_alert:
                    shap = None
                    if shap_map and (user_id, record_date) in shap_map:
                        shap = shap_map[(user_id, record_date)]
                    alert_type = get_alert_type(row)
                    sev = _severity(float(row.get("risk_score", 0)))
                    db.add(Alert(
                        user_id=user_id,
                        date=record_date,
                        alert_type=alert_type,
                        severity=sev,
                        risk_score=float(row.get("risk_score", 0)),
                        shap_json=shap,
                    ))

        db.commit()
        logger.info(f"Ingested {len(scored_df):,} rows for {len(users_seen):,} users.")

    except Exception as e:
        db.rollback()
        logger.error(f"DB ingestion error: {e}")
        raise
    finally:
        if own_session:
            db.close()
