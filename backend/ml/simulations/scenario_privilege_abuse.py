"""
scenario_privilege_abuse.py
----------------------------
Simulation: PRIVILEGE ABUSE

An employee accesses a restricted server they never normally use,
logs in from multiple unique machines, and downloads confidential files.

Run from backend/ directory:
    python -m ml.simulations.scenario_privilege_abuse
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from ml.risk_scoring_engine import compute_risk_scores, get_alert_type, RISK_THRESHOLD


SCENARIO_NAME = "PRIVILEGE ABUSE"
USER_ID = "SIM_PRIV_002"
DATE = "2024-03-11"

# ── Synthetic feature vector ─────────────────────────────────────────────────

feature_row = {
    "user": USER_ID,
    "date": pd.Timestamp(DATE),
    # Login — 5 unique PCs (restricted servers accessed)
    "login_count": 7,
    "after_hours_login_count": 2,
    "login_hour_mean": 21.5,
    "unique_pcs": 5,                    # KEY: unusual multi-server access
    # Device
    "usb_connect_count": 1,
    "after_hours_usb": 0,
    # File — sensitive file downloads
    "file_copy_count": 87,
    "after_hours_file_copy": 50,
    # Email
    "email_sent_count": 3,
    "total_recipient_count": 5,
    "external_recipient_count": 2,
    "external_email_ratio": 0.4,
    "total_email_size_bytes": 1_200_000,
    "total_attachments": 3,
    "suspicious_attachment_count": 1,
    "after_hours_email": 2,
    # HTTP
    "http_request_count": 45,
    "file_sharing_visit_count": 1,
    "after_hours_http": 40,
    # Derived
    "exfil_indicator": 87 * 0.4 + 1 * 0.3 + 1 * 0.3,
    "after_hours_activity_total": 2 + 0 + 50 + 2 + 40,
    "behavior_spike_score": 0.82,
}

# ── Synthetic model scores ───────────────────────────────────────────────────

if_score   = np.float64(0.87)
ae_score   = np.float64(0.80)
lstm_score = np.float64(0.76)
gnn_score  = np.float64(0.90)   # GNN specifically flagging unusual server graph edges


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
            "unique_pcs_accessed":    feature_row["unique_pcs"],
            "after_hours_logins":     feature_row["after_hours_login_count"],
            "sensitive_file_copies":  feature_row["file_copy_count"],
            "gnn_score":              float(gnn_score),
        },
        "expected_alert_type": "PRIVILEGE_ABUSE",
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
