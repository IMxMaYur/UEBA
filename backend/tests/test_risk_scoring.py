"""
tests/test_risk_scoring.py
Unit tests for risk_scoring_engine.py – weights, rules, alert threshold.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest

from ml.risk_scoring_engine import (
    compute_risk_scores,
    compute_rule_violations,
    get_alert_type,
    RISK_THRESHOLD,
    W_IF, W_AE, W_LSTM, W_GNN, W_RULES,
)


# ---------------------------------------------------------------------------
# Weight integrity
# ---------------------------------------------------------------------------

def test_weights_sum_to_one():
    """The five model weights must exactly sum to 1.0."""
    total = W_IF + W_AE + W_LSTM + W_GNN + W_RULES
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


# ---------------------------------------------------------------------------
# Rule violations
# ---------------------------------------------------------------------------

def _make_df(**kwargs) -> pd.DataFrame:
    """Create a single-row feature DataFrame with given field values."""
    defaults = {
        "user": "TEST001",
        "after_hours_login_count": 0,
        "usb_connect_count": 0,
        "file_copy_count": 0,
        "external_email_ratio": 0.0,
        "total_attachments": 0,
        "file_sharing_visit_count": 0,
        "unique_pcs": 1,
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def test_rule_r1_after_hours_usb():
    """R1 fires when after-hours login AND USB both present."""
    df = _make_df(after_hours_login_count=1, usb_connect_count=1)
    scores = compute_rule_violations(df)
    assert scores.iloc[0] > 0, "R1 should fire"


def test_rule_r1_no_trigger_without_both():
    """R1 does NOT fire if only one condition is met."""
    df_login_only = _make_df(after_hours_login_count=1, usb_connect_count=0)
    assert compute_rule_violations(df_login_only).iloc[0] == 0.0

    df_usb_only = _make_df(after_hours_login_count=0, usb_connect_count=1)
    assert compute_rule_violations(df_usb_only).iloc[0] == 0.0


def test_rule_r3_external_email():
    """R3 fires when external email ratio > 0.5 AND attachments > 0."""
    df = _make_df(external_email_ratio=0.8, total_attachments=2)
    scores = compute_rule_violations(df)
    assert scores.iloc[0] > 0, "R3 should fire"


def test_rule_r4_file_sharing():
    """R4 fires when file sharing visits > 3."""
    df = _make_df(file_sharing_visit_count=4)
    scores = compute_rule_violations(df)
    assert scores.iloc[0] > 0, "R4 should fire"


def test_rule_r5_multi_pc():
    """R5 fires when unique_pcs > 3."""
    df = _make_df(unique_pcs=4)
    scores = compute_rule_violations(df)
    assert scores.iloc[0] > 0, "R5 should fire"


def test_no_rules_fire_for_normal_user():
    """A benign user with all normal values gets rule_score == 0."""
    df = _make_df()
    scores = compute_rule_violations(df)
    assert scores.iloc[0] == 0.0, "Normal user should have no rule violations"


# ---------------------------------------------------------------------------
# Risk score formula & alert threshold
# ---------------------------------------------------------------------------

def _score(if_s, ae_s, lstm_s, gnn_s):
    """Helper: run compute_risk_scores on a minimal feature row."""
    df = _make_df()
    result = compute_risk_scores(
        df,
        if_scores=pd.Series([if_s]),
        ae_scores=pd.Series([ae_s]),
        lstm_scores=pd.Series([lstm_s]),
        gnn_scores=pd.Series([gnn_s]),
    )
    return result.iloc[0]


def test_risk_score_in_unit_interval():
    """risk_score must be clipped to [0, 1]."""
    row = _score(1.0, 1.0, 1.0, 1.0)
    assert 0.0 <= row["risk_score"] <= 1.0


def test_risk_score_zero_for_all_zeros():
    """All-zero inputs should yield risk_score == 0 (rule score also 0 for normal user)."""
    row = _score(0.0, 0.0, 0.0, 0.0)
    assert row["risk_score"] == pytest.approx(0.0, abs=0.01)


def test_alert_triggered_above_threshold():
    """is_alert must be 1 when risk_score >= RISK_THRESHOLD."""
    row = _score(1.0, 1.0, 1.0, 1.0)
    assert row["is_alert"] == 1


def test_no_alert_below_threshold():
    """is_alert must be 0 when risk_score < RISK_THRESHOLD."""
    row = _score(0.1, 0.1, 0.1, 0.1)
    assert row["is_alert"] == 0


# ---------------------------------------------------------------------------
# Alert type classification
# ---------------------------------------------------------------------------

def test_alert_type_data_exfiltration():
    row = pd.Series({"file_copy_count": 10, "usb_connect_count": 3,
                     "after_hours_login_count": 0, "unique_pcs": 1,
                     "login_count": 1, "file_sharing_visit_count": 0,
                     "external_email_ratio": 0.1})
    assert get_alert_type(row) == "DATA_EXFILTRATION"


def test_alert_type_privilege_abuse():
    row = pd.Series({"unique_pcs": 4, "after_hours_login_count": 1,
                     "file_copy_count": 1, "usb_connect_count": 0,
                     "login_count": 2, "file_sharing_visit_count": 0,
                     "external_email_ratio": 0.1})
    assert get_alert_type(row) == "PRIVILEGE_ABUSE"


def test_alert_type_suspicious_login():
    row = pd.Series({"after_hours_login_count": 3, "login_count": 6,
                     "file_copy_count": 0, "usb_connect_count": 0,
                     "unique_pcs": 1, "file_sharing_visit_count": 0,
                     "external_email_ratio": 0.1})
    assert get_alert_type(row) == "SUSPICIOUS_LOGIN"
