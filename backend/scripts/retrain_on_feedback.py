"""
retrain_on_feedback.py
----------------------
Nightly active-learning retraining script.

Loads all analyst-reviewed DailyFeature rows from the database and retrains
the Isolation Forest model excluding confirmed false positives. This ensures
the ML models continuously improve from human analyst feedback.

Usage:
    python scripts/retrain_on_feedback.py

Schedule via: Windows Task Scheduler / cron
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def retrain():
    logger.info("=== Nightly Feedback Retraining START ===")

    from app.database import SessionLocal
    from app.models.orm_models import DailyFeature
    import pandas as pd
    from ml import isolation_forest as if_module

    db = SessionLocal()
    try:
        logger.info("Loading DailyFeature rows from DB ...")
        rows = db.query(DailyFeature).all()

        if not rows:
            logger.warning("No DailyFeature rows found — skipping retrain.")
            return

        # Convert to DataFrame
        data = []
        for r in rows:
            data.append({
                "user":                      r.user_id,
                "date":                      r.date,
                "login_count":               r.login_count or 0,
                "after_hours_login_count":   r.after_hours_login_count or 0,
                "login_hour_mean":           r.login_hour_mean or 0,
                "unique_pcs":                r.unique_pcs or 0,
                "usb_connect_count":         r.usb_connect_count or 0,
                "after_hours_usb":           r.after_hours_usb or 0,
                "file_copy_count":           r.file_copy_count or 0,
                "after_hours_file_copy":     r.after_hours_file_copy or 0,
                "email_sent_count":          r.email_sent_count or 0,
                "external_email_ratio":      r.external_email_ratio or 0,
                "suspicious_attachment_count": r.suspicious_attachment_count or 0,
                "total_email_size_bytes":    r.total_email_size_bytes or 0,
                "http_request_count":        r.http_request_count or 0,
                "file_sharing_visit_count":  r.file_sharing_visit_count or 0,
                "exfil_indicator":           r.exfil_indicator or 0,
                "after_hours_activity_total": r.after_hours_activity_total or 0,
                "behavior_spike_score":      r.behavior_spike_score or 0,
                "peer_risk_score":           r.peer_risk_score or 0,
                "is_false_positive":         r.is_false_positive or False,
            })

        df = pd.DataFrame(data)
        total   = len(df)
        fp_count = df["is_false_positive"].sum()

        logger.info(f"  → {total:,} rows loaded, {fp_count:,} marked as false positive.")
        logger.info("Retraining Isolation Forest with FP exclusion ...")

        # isolation_forest.train() already handles is_false_positive filtering internally
        if_module.train(df)

        logger.info("=== Retraining COMPLETE — model saved to trained_models/ ===")

    finally:
        db.close()


if __name__ == "__main__":
    retrain()
