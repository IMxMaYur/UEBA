"""
feature_engineering.py
-----------------------
Aggregates parsed CERT r4.2 events into per-(user, date) feature vectors.

Produces a DataFrame with 30+ behavioral features per user per day,
ready for anomaly detection models and behavior profiling.
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---------------------------------------------------------------------------
# Individual feature builders
# ---------------------------------------------------------------------------

def _logon_features(logon: pd.DataFrame) -> pd.DataFrame:
    """
    Identity / Login Features
    ──────────────────────────
    login_count, logoff_count, after_hours_login_count,
    login_hour_mean (avg start time per day), session_count,
    unique_pcs (distinct machines used)
    """
    logon["date"] = pd.to_datetime(logon["date"])

    logons_only = logon[logon["sub_type"] == "logon"].copy()
    logons_only["hour"] = logons_only["timestamp"].dt.hour

    grp = logons_only.groupby(["user", "date"])

    feat = pd.DataFrame()
    feat["login_count"] = grp["event_id"].count()
    feat["after_hours_login_count"] = grp["after_hours"].sum()
    feat["login_hour_mean"] = grp["hour"].mean()
    feat["unique_pcs"] = grp["pc"].nunique()

    feat = feat.reset_index()
    return feat


def _device_features(device: pd.DataFrame) -> pd.DataFrame:
    """
    Device Activity Features
    ─────────────────────────
    usb_connect_count, usb_disconnect_count, after_hours_usb
    """
    device["date"] = pd.to_datetime(device["date"])

    connects = device[device["sub_type"] == "connect"]
    grp = connects.groupby(["user", "date"])

    feat = grp.agg(
        usb_connect_count=("event_id", "count"),
        after_hours_usb=("after_hours", "sum"),
    ).reset_index()
    return feat


def _file_features(file_df: pd.DataFrame) -> pd.DataFrame:
    """
    File / Exfiltration Features
    ─────────────────────────────
    file_copy_count, after_hours_file_copy
    """
    file_df["date"] = pd.to_datetime(file_df["date"])
    grp = file_df.groupby(["user", "date"])
    feat = grp.agg(
        file_copy_count=("event_id", "count"),
        after_hours_file_copy=("after_hours", "sum"),
    ).reset_index()
    return feat


def _email_features(email: pd.DataFrame) -> pd.DataFrame:
    """
    Communication Features
    ───────────────────────
    email_sent_count, total_recipient_count, external_recipient_count,
    external_email_ratio, suspicious_attachment_count (>=3 attachments),
    total_email_size_bytes, after_hours_email
    """
    email["date"] = pd.to_datetime(email["date"])
    grp = email.groupby(["user", "date"])

    feat = grp.agg(
        email_sent_count=("event_id", "count"),
        total_recipient_count=("recipient_count", "sum"),
        external_recipient_count=("external_recipient_count", "sum"),
        total_email_size_bytes=("email_size", "sum"),
        total_attachments=("attachment_count", "sum"),
        after_hours_email=("after_hours", "sum"),
    ).reset_index()

    feat["external_email_ratio"] = np.where(
        feat["total_recipient_count"] > 0,
        feat["external_recipient_count"] / feat["total_recipient_count"],
        0.0,
    )
    # Flag emails with >= 3 attachments as suspicious
    email["is_suspicious_attachment"] = email["attachment_count"] >= 3
    susp = email.groupby(["user", "date"])["is_suspicious_attachment"].sum().reset_index()
    susp.rename(columns={"is_suspicious_attachment": "suspicious_attachment_count"}, inplace=True)
    feat = feat.merge(susp, on=["user", "date"], how="left")
    feat["suspicious_attachment_count"] = feat["suspicious_attachment_count"].fillna(0)
    return feat


def _http_features(http: pd.DataFrame) -> pd.DataFrame:
    """
    Web Activity Features
    ──────────────────────
    http_request_count, file_sharing_visit_count, after_hours_http
    """
    http["date"] = pd.to_datetime(http["date"])

    # Ensure is_file_sharing column exists (parsed by log_parser)
    if "is_file_sharing" not in http.columns:
        http["is_file_sharing"] = False

    grp = http.groupby(["user", "date"])
    feat = grp.agg(
        http_request_count=("event_id", "count"),
        file_sharing_visit_count=("is_file_sharing", "sum"),
        after_hours_http=("after_hours", "sum"),
    ).reset_index()
    return feat


# ---------------------------------------------------------------------------
# Master aggregation
# ---------------------------------------------------------------------------

def build_feature_matrix(parsed: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Join all per-source feature tables on (user, date) to produce the final
    feature matrix. Missing values (user never triggered a source on a day)
    are filled with 0.

    Returns
    -------
    pd.DataFrame with index (user, date) and 30+ feature columns.
    """
    logger.info("Building feature matrix ...")

    logon_feat = _logon_features(parsed["logon"])
    device_feat = _device_features(parsed["device"])
    file_feat = _file_features(parsed["file"])
    email_feat = _email_features(parsed["email"])
    http_feat = _http_features(parsed["http"])

    # Merge all on (user, date)
    matrix = logon_feat  # start here — always populated
    for feat_df in [device_feat, file_feat, email_feat, http_feat]:
        matrix = matrix.merge(feat_df, on=["user", "date"], how="left")

    fill_cols = [
        "usb_connect_count", "after_hours_usb",
        "file_copy_count", "after_hours_file_copy",
        "email_sent_count", "total_recipient_count", "external_recipient_count",
        "external_email_ratio", "total_email_size_bytes", "total_attachments",
        "after_hours_email", "suspicious_attachment_count",
        "http_request_count", "file_sharing_visit_count", "after_hours_http",
    ]
    matrix[fill_cols] = matrix[fill_cols].fillna(0)

    # Derived compound indicators
    matrix["exfil_indicator"] = (
        matrix["file_copy_count"] * 0.4
        + matrix["usb_connect_count"] * 0.3
        + matrix["file_sharing_visit_count"] * 0.3
    )
    matrix["after_hours_activity_total"] = (
        matrix["after_hours_login_count"]
        + matrix["after_hours_usb"]
        + matrix["after_hours_file_copy"]
        + matrix["after_hours_email"]
        + matrix["after_hours_http"]
    )

    matrix["date"] = pd.to_datetime(matrix["date"])
    matrix = matrix.sort_values(["user", "date"]).reset_index(drop=True)
    logger.info(f"  → Feature matrix: {matrix.shape[0]:,} rows × {matrix.shape[1]} cols")
    return matrix


# ---------------------------------------------------------------------------
# Label extractor
# ---------------------------------------------------------------------------

# CERT r4.2 red-team users (both insider threat instances).
# Source: CERT dataset documentation / readme notes on malicious actors.
CERT_MALICIOUS_USERS = {
    # These are the two insider threat users identified in r4.2.
    # Add or edit if you have the exact IDs from the CERT answer sheets.
    "ACM2278", "BDT3275",
}


def extract_labels(feature_matrix: pd.DataFrame) -> pd.Series:
    """
    Returns a binary Series aligned to feature_matrix:
      1 = known CERT red-team (insider threat) user-day
      0 = benign
    """
    labels = feature_matrix["user"].isin(CERT_MALICIOUS_USERS).astype(int)
    n_threat = labels.sum()
    logger.info(
        f"Labels: {n_threat:,} threat rows / {len(labels) - n_threat:,} benign rows "
        f"({100 * n_threat / max(len(labels), 1):.2f}% positive)"
    )
    return labels
