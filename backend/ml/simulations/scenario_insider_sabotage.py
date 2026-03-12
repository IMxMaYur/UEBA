"""
scenario_insider_sabotage.py
-----------------------------
Simulation: INSIDER SABOTAGE

An employee accesses production servers after hours, deletes/modifies critical
files, and sends data externally — potential sabotage before resignation.

Run from backend/ directory:
    python -m ml.simulations.scenario_insider_sabotage
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from ml.risk_scoring_engine import compute_risk_scores, get_alert_type, RISK_THRESHOLD


SCENARIO_NAME = "INSIDER SABOTAGE"
USER_ID = "SIM_SABOTAGE_005"
DATE = "2024-03-14"

# ── Synthetic feature vector ─────────────────────────────────────────────────

feature_row = {
    "user": USER_ID,
    "date": pd.Timestamp(DATE),
    # Login — after hours on unusual production servers
    "login_count": 3,
    "after_hours_login_count": 3,       # ALL after hours
    "login_hour_mean": 1.5,             # ~1:30 AM
    "unique_pcs": 4,                    # production servers (unusual access pattern)
    # Device
    "usb_connect_count": 2,
    "after_hours_usb": 2,
    # File — mass file activity (modifications/deletions represented as high copy count)
    "file_copy_count": 195,             # file modifications proxy
    "after_hours_file_copy": 195,       # all after hours — no legitimate reason
    # Email — external exfil attempt
    "email_sent_count": 5,
    "total_recipient_count": 5,
    "external_recipient_count": 5,
    "external_email_ratio": 1.0,        # KEY: 100% external
    "total_email_size_bytes": 8_000_000, # 8 MB — large attachments
    "total_attachments": 5,
    "suspicious_attachment_count": 3,   # KEY: suspicious attachments
    "after_hours_email": 5,
    # HTTP — config repositories and doc sites
    "http_request_count": 60,
    "file_sharing_visit_count": 4,
    "after_hours_http": 60,
    # Derived
    "exfil_indicator": 195 * 0.4 + 2 * 0.3 + 4 * 0.3,
    "after_hours_activity_total": 3 + 2 + 195 + 5 + 60,
    "behavior_spike_score": 0.97,
}

# ── Synthetic model scores ───────────────────────────────────────────────────

if_score   = np.float64(0.95)   # extremely rare behavioural pattern
ae_score   = np.float64(0.93)
lstm_score = np.float64(0.88)   # after-hours login → file delete → email sequence
gnn_score  = np.float64(0.85)   # production server graph anomaly


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
            "after_hours_login":          feature_row["after_hours_login_count"],
            "production_servers_accessed": feature_row["unique_pcs"],
            "file_modifications":         feature_row["file_copy_count"],
            "external_emails":            feature_row["email_sent_count"],
            "suspicious_attachments":     feature_row["suspicious_attachment_count"],
            "100pct_external_email":      True,
        },
        "expected_alert_type": "DATA_EXFILTRATION or BEHAVIORAL_ANOMALY",
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
