"""
risk_scoring_engine.py
----------------------
Combines anomaly scores from all four models into a single final risk score
and applies rule-based violation bonuses.

Formula:
  risk_score = 0.35×IF + 0.30×AE + 0.20×LSTM + 0.10×GNN + 0.05×rules
"""

import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.65"))

# Weights (must sum to 1.0)
W_IF = 0.35
W_AE = 0.30
W_LSTM = 0.20
W_GNN = 0.10
W_RULES = 0.05


# ---------------------------------------------------------------------------
# Rule-based violation scorer
# ---------------------------------------------------------------------------

def compute_rule_violations(feature_matrix: pd.DataFrame) -> pd.Series:
    """
    Hard-coded behavioural rules that add a bounded bonus to the risk score.
    Each rule sets a flag ∈ {0, 1}; the mean of all flags is the rule score ∈ [0,1].
    """
    df = feature_matrix.copy()

    rules = pd.DataFrame(index=df.index)

    # R1: After-hours login AND USB usage on same day
    rules["r1_ah_login_usb"] = (
        (df.get("after_hours_login_count", 0) > 0).astype(int)
        & (df.get("usb_connect_count", 0) > 0).astype(int)
    )

    # R2: File copy volume spike (>5× daily median for that user)
    fc_med = df.groupby("user")["file_copy_count"].transform("median")
    rules["r2_file_copy_spike"] = (
        df.get("file_copy_count", 0) > 5 * fc_med.replace(0, 1)
    ).astype(int)

    # R3: High external email ratio (>0.5) with attachments
    rules["r3_exfil_email"] = (
        (df.get("external_email_ratio", 0) > 0.5).astype(int)
        & (df.get("total_attachments", 0) > 0).astype(int)
    )

    # R4: File sharing site visits > 3 in one day
    rules["r4_file_sharing"] = (df.get("file_sharing_visit_count", 0) > 3).astype(int)

    # R5: Multiple unique PCs accessed in a day (>3 — unusual for most users)
    rules["r5_multi_pc"] = (df.get("unique_pcs", 1) > 3).astype(int)

    # Aggregate: mean of all rule flags
    rule_score = rules.mean(axis=1)
    return rule_score.rename("rule_score")


# ---------------------------------------------------------------------------
# Final risk scorer
# ---------------------------------------------------------------------------

def compute_risk_scores(
    feature_matrix: pd.DataFrame,
    if_scores: pd.Series,
    ae_scores: pd.Series,
    lstm_scores: pd.Series,
    gnn_scores: pd.Series,
) -> pd.DataFrame:
    """
    Merge all component scores and compute weighted final risk score.

    Returns a copy of feature_matrix with added score columns:
      if_score, ae_score, lstm_score, gnn_score, rule_score, risk_score, is_alert
    """
    df = feature_matrix.copy()
    df["if_score"] = if_scores.values
    df["ae_score"] = ae_scores.values
    df["lstm_score"] = lstm_scores.values
    df["gnn_score"] = gnn_scores.values
    df["rule_score"] = compute_rule_violations(df).values

    df["risk_score"] = (
        W_IF    * df["if_score"]
        + W_AE  * df["ae_score"]
        + W_LSTM * df["lstm_score"]
        + W_GNN * df["gnn_score"]
        + W_RULES * df["rule_score"]
    ).clip(0.0, 1.0)

    df["is_alert"] = (df["risk_score"] >= RISK_THRESHOLD).astype(int)

    n_alerts = df["is_alert"].sum()
    logger.info(
        f"Risk scoring complete. {n_alerts:,} alerts triggered "
        f"(threshold={RISK_THRESHOLD}, {100*n_alerts/max(len(df),1):.2f}%)"
    )
    return df


def get_alert_type(row: pd.Series) -> str:
    """
    Heuristic alert type classification based on which features are elevated.
    """
    if row.get("file_copy_count", 0) > 5 and row.get("usb_connect_count", 0) > 2:
        return "DATA_EXFILTRATION"
    if row.get("unique_pcs", 1) > 3 and row.get("after_hours_login_count", 0) > 0:
        return "PRIVILEGE_ABUSE"
    if row.get("after_hours_login_count", 0) > 2 and row.get("login_count", 0) > 5:
        return "SUSPICIOUS_LOGIN"
    if row.get("file_sharing_visit_count", 0) > 3 or row.get("external_email_ratio", 0) > 0.7:
        return "DATA_EXFILTRATION_RISK"
    if row.get("file_copy_count", 0) > 10:
        return "MASS_DATA_DOWNLOAD"
    return "BEHAVIORAL_ANOMALY"
