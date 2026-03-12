"""
shap_explainer.py
-----------------
Generates SHAP explanations for each alert.
- Uses TreeExplainer for the Isolation Forest (fast, exact).
- Uses KernelExplainer fallback for the Autoencoder (approximate).
- Returns top-5 feature contributions per alert.
"""

import logging
from typing import List, Dict

import numpy as np
import pandas as pd
import shap
import joblib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

FEATURE_COLS = [
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb",
    "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "total_recipient_count", "external_recipient_count",
    "external_email_ratio", "total_email_size_bytes", "total_attachments",
    "after_hours_email", "suspicious_attachment_count",
    "http_request_count", "file_sharing_visit_count", "after_hours_http",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
    "login_count_zscore", "after_hours_login_count_zscore",
    "usb_connect_count_zscore", "file_copy_count_zscore",
    "email_sent_count_zscore", "external_email_ratio_zscore",
    "http_request_count_zscore", "file_sharing_visit_count_zscore",
    "exfil_indicator_zscore", "after_hours_activity_total_zscore",
]

FRIENDLY_NAMES = {
    "login_count": "Login Count",
    "after_hours_login_count": "After-Hours Logins",
    "login_hour_mean": "Avg Login Hour",
    "unique_pcs": "Unique PCs Accessed",
    "usb_connect_count": "USB Connections",
    "after_hours_usb": "After-Hours USB",
    "file_copy_count": "Files Copied to Removable Media",
    "after_hours_file_copy": "After-Hours File Copies",
    "email_sent_count": "Emails Sent",
    "external_email_ratio": "External Email Ratio",
    "suspicious_attachment_count": "Suspicious Attachments (≥3)",
    "http_request_count": "HTTP Requests",
    "file_sharing_visit_count": "File Sharing Site Visits",
    "exfil_indicator": "Exfiltration Composite Score",
    "after_hours_activity_total": "Total After-Hours Activity",
    "behavior_spike_score": "Behavior Spike Score",
}


def _get_X(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in FEATURE_COLS if c in df.columns]
    return df[cols].fillna(0)


def explain_isolation_forest(
    alert_rows: pd.DataFrame,
    background_data: pd.DataFrame,
    if_model=None,
    if_scaler=None,
) -> List[Dict]:
    """
    Use SHAP TreeExplainer on the Isolation Forest to get feature importances
    for each alert row.  Returns a list of top-5 feature dicts.
    """
    from ml import isolation_forest as if_module

    if if_model is None or if_scaler is None:
        if_model, if_scaler = if_module.load_model()

    X_alert = _get_X(alert_rows)
    X_bg = _get_X(background_data)

    X_alert_scaled = if_scaler.transform(X_alert)
    X_bg_scaled = if_scaler.transform(X_bg)
    cols = X_alert.columns.tolist()

    try:
        explainer = shap.TreeExplainer(if_model, data=X_bg_scaled[:200])
        shap_values = explainer.shap_values(X_alert_scaled)
    except Exception as e:
        logger.warning(f"TreeExplainer failed ({e}), falling back to KernelExplainer.")
        explainer = shap.KernelExplainer(
            lambda x: if_model.decision_function(x), X_bg_scaled[:50]
        )
        shap_values = explainer.shap_values(X_alert_scaled, nsamples=50)

    results = []
    for i in range(len(alert_rows)):
        sv = shap_values[i] if hasattr(shap_values[0], "__len__") else shap_values
        feat_importances = sorted(
            zip(cols, sv), key=lambda x: abs(x[1]), reverse=True
        )[:5]
        results.append([
            {
                "feature": feat,
                "friendly_name": FRIENDLY_NAMES.get(feat, feat),
                "value": float(alert_rows.iloc[i][feat]) if feat in alert_rows.columns else 0.0,
                "shap_value": float(sv_val),
                "direction": "increases_risk" if sv_val > 0 else "decreases_risk",
            }
            for feat, sv_val in feat_importances
        ])
    return results


def explain_row(
    alert_row: pd.Series,
    background_df: pd.DataFrame,
    if_model=None,
    if_scaler=None,
) -> List[Dict]:
    """Convenience wrapper for a single alert row."""
    return explain_isolation_forest(
        alert_rows=pd.DataFrame([alert_row]),
        background_data=background_df,
        if_model=if_model,
        if_scaler=if_scaler,
    )[0]
