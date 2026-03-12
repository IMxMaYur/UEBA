"""
scenario_mass_download.py
--------------------------
Simulation: MASS DATA DOWNLOAD

An employee downloads an unusually high number of files compared to normal
daily activity — indicative of pre-departure data theft or bulk exfiltration.

Run from backend/ directory:
    python -m ml.simulations.scenario_mass_download
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from ml.risk_scoring_engine import compute_risk_scores, get_alert_type, RISK_THRESHOLD


SCENARIO_NAME = "MASS DATA DOWNLOAD"
USER_ID = "SIM_MASS_004"
DATE = "2024-03-13"

# ── Synthetic feature vector ─────────────────────────────────────────────────

feature_row = {
    "user": USER_ID,
    "date": pd.Timestamp(DATE),
    # Login — normal hours, no obvious red flag in login itself
    "login_count": 2,
    "after_hours_login_count": 0,
    "login_hour_mean": 9.0,
    "unique_pcs": 1,
    # Device — no USB
    "usb_connect_count": 0,
    "after_hours_usb": 0,
    # File — KEY: extremely high file copy count during business hours
    "file_copy_count": 520,             # 5–10× normal baseline
    "after_hours_file_copy": 0,
    # Email
    "email_sent_count": 2,
    "total_recipient_count": 4,
    "external_recipient_count": 3,
    "external_email_ratio": 0.75,
    "total_email_size_bytes": 3_500_000,
    "total_attachments": 2,
    "suspicious_attachment_count": 0,
    "after_hours_email": 0,
    # HTTP — heavy file-sharing site visits
    "http_request_count": 180,
    "file_sharing_visit_count": 8,      # KEY: visits to file sharing sites
    "after_hours_http": 0,
    # Derived
    "exfil_indicator": 520 * 0.4 + 0 * 0.3 + 8 * 0.3,
    "after_hours_activity_total": 0,
    "behavior_spike_score": 0.91,
}

# ── Synthetic model scores ───────────────────────────────────────────────────

if_score   = np.float64(0.90)   # very rare file access volume
ae_score   = np.float64(0.86)
lstm_score = np.float64(0.70)
gnn_score  = np.float64(0.68)


def run_simulation() -> dict:
    feature_matrix = pd.DataFrame([feature_row])

    if_s   = pd.Series([if_score],   name="if_score")
    ae_s   = pd.Series([ae_score],   name="ae_score")
    lstm_s = pd.Series([lstm_score], name="lstm_score")
    gnn_s  = pd.Series([gnn_score],  name="gnn_score")

    result_df = compute_risk_scores(feature_matrix, if_s, ae_s, lstm_s, gnn_s)
    row = result_df.iloc[0]

    alert_type = get_alert_type(row)
    triggered  = bool(row["risk_score"] >= RISK_THRESHOLD)

    report = {
        "scenario":   SCENARIO_NAME,
        "user_id":     USER_ID,
        "date":        DATE,
        "is_alert":    triggered,
        "alert_type":  alert_type,
        "risk_score":  round(float(row["risk_score"]), 4),
        "threshold":   RISK_THRESHOLD,
        "score_breakdown": {
            "isolation_forest": round(float(row["if_score"]),   4),
            "autoencoder":      round(float(row["ae_score"]),   4),
            "lstm_sequence":    round(float(row["lstm_score"]), 4),
            "gnn_graph":        round(float(row["gnn_score"]),  4),
            "rule_violations":  round(float(row["rule_score"]), 4),
        },
        "key_indicators": {
            "file_copy_count":         feature_row["file_copy_count"],
            "file_sharing_visits":     feature_row["file_sharing_visit_count"],
            "external_email_ratio":    feature_row["external_email_ratio"],
            "isolation_forest_score":  float(if_score),
        },
        "expected_alert_type": "MASS_DATA_DOWNLOAD",
        "detection_status": "✅ DETECTED" if triggered else "❌ MISSED",
    }
    return report


if __name__ == "__main__":
    report = run_simulation()
    print("\n" + "=" * 60)
    print(f"  UEBA SIMULATION: {report['scenario']}")
    print("=" * 60)
    print(json.dumps(report, indent=2))
    print("=" * 60 + "\n")
    if not report["is_alert"]:
        sys.exit(1)
