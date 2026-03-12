"""
scenario_credential_compromise.py
-----------------------------------
Simulation: CREDENTIAL COMPROMISE / SUSPICIOUS LOGIN

An employee account logs in from a new device, then rapidly accesses multiple
systems and resources — a pattern consistent with compromised credentials.

Run from backend/ directory:
    python -m ml.simulations.scenario_credential_compromise
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from ml.risk_scoring_engine import compute_risk_scores, get_alert_type, RISK_THRESHOLD


SCENARIO_NAME = "CREDENTIAL COMPROMISE"
USER_ID = "SIM_CRED_003"
DATE = "2024-03-12"

# ── Synthetic feature vector ─────────────────────────────────────────────────

feature_row = {
    "user": USER_ID,
    "date": pd.Timestamp(DATE),
    # Login — rapid burst, new device, after-hours
    "login_count": 9,                   # KEY: unusually high login count in one day
    "after_hours_login_count": 4,       # KEY: multiple after-hours attempts
    "login_hour_mean": 23.0,            # predominantly late night
    "unique_pcs": 3,                    # NEW device and 2 others
    # Device
    "usb_connect_count": 0,
    "after_hours_usb": 0,
    # File — rapid resource access
    "file_copy_count": 45,
    "after_hours_file_copy": 44,
    # Email
    "email_sent_count": 1,
    "total_recipient_count": 1,
    "external_recipient_count": 1,
    "external_email_ratio": 1.0,        # sent externally
    "total_email_size_bytes": 500_000,
    "total_attachments": 1,
    "suspicious_attachment_count": 0,
    "after_hours_email": 1,
    # HTTP
    "http_request_count": 220,          # rapid browse / recon
    "file_sharing_visit_count": 0,
    "after_hours_http": 220,
    # Derived
    "exfil_indicator": 45 * 0.4 + 0 * 0.3 + 0 * 0.3,
    "after_hours_activity_total": 4 + 0 + 44 + 1 + 220,
    "behavior_spike_score": 0.88,
}

# ── Synthetic model scores ───────────────────────────────────────────────────

if_score   = np.float64(0.84)
ae_score   = np.float64(0.79)
lstm_score = np.float64(0.91)   # LSTM strongly detects suspicious sequence
gnn_score  = np.float64(0.72)


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
            "login_count":            feature_row["login_count"],
            "after_hours_logins":     feature_row["after_hours_login_count"],
            "unique_pcs":             feature_row["unique_pcs"],
            "lstm_sequence_score":    float(lstm_score),
            "http_burst":             feature_row["http_request_count"],
        },
        "expected_alert_type": "SUSPICIOUS_LOGIN",
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
