"""
scenario_data_exfiltration.py
------------------------------
Simulation: DATA EXFILTRATION

An employee logs in during late night hours, copies hundreds of files,
and exports them to a USB device.

Run from backend/ directory:
    python -m ml.simulations.scenario_data_exfiltration
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from ml.risk_scoring_engine import compute_risk_scores, get_alert_type, RISK_THRESHOLD


SCENARIO_NAME = "DATA EXFILTRATION"
USER_ID = "SIM_EXFIL_001"
DATE = "2024-03-10"

# ── Synthetic feature vector (1 user-day) ───────────────────────────────────

feature_row = {
    "user": USER_ID,
    "date": pd.Timestamp(DATE),
    # Login
    "login_count": 1,
    "after_hours_login_count": 1,       # logged in at 02:00 AM
    "login_hour_mean": 2.0,
    "unique_pcs": 1,
    # Device (USB)
    "usb_connect_count": 4,             # 4 USB connect events
    "after_hours_usb": 4,
    # File
    "file_copy_count": 312,             # mass file copy
    "after_hours_file_copy": 310,
    # Email
    "email_sent_count": 0,
    "total_recipient_count": 0,
    "external_recipient_count": 0,
    "external_email_ratio": 0.0,
    "total_email_size_bytes": 0,
    "total_attachments": 0,
    "suspicious_attachment_count": 0,
    "after_hours_email": 0,
    # HTTP
    "http_request_count": 12,
    "file_sharing_visit_count": 2,
    "after_hours_http": 12,
    # Derived
    "exfil_indicator": 312 * 0.4 + 4 * 0.3 + 2 * 0.3,
    "after_hours_activity_total": 1 + 4 + 310 + 0 + 12,
    "behavior_spike_score": 0.95,
}

# ── Synthetic model scores (emulating trained model outputs) ─────────────────

# Isolation Forest: high anomaly — near-1.0
if_score = np.float64(0.92)
# Autoencoder: high reconstruction error
ae_score = np.float64(0.88)
# LSTM: suspicious action sequence
lstm_score = np.float64(0.85)
# GNN: unusual peer/resource access
gnn_score = np.float64(0.78)


def run_simulation() -> dict:
    feature_matrix = pd.DataFrame([feature_row])

    if_s  = pd.Series([if_score],   name="if_score")
    ae_s  = pd.Series([ae_score],   name="ae_score")
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
            "after_hours_login":  feature_row["after_hours_login_count"],
            "file_copy_count":    feature_row["file_copy_count"],
            "usb_connect_count":  feature_row["usb_connect_count"],
            "exfil_indicator":    round(feature_row["exfil_indicator"], 2),
        },
        "expected_alert_type": "DATA_EXFILTRATION",
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
