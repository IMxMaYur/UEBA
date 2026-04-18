"""
feature_engineering.py
-----------------------
Aggregates parsed CERT r4.2 events into per-(user, date) feature vectors.

Produces a DataFrame with 30+ behavioral features per user per day,
ready for anomaly detection models and behavior profiling.
"""

import logging
from pathlib import Path
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

    # --- DLP: scan email content for sensitive data patterns ---
    if "content" in email.columns:
        import re
        DLP_PATTERNS = [
            r"password", r"credential", r"passwd", r"secret",
            r"confidential", r"proprietary", r"restricted",
            r"resign", r"quit", r"leaving",
            r"\b(?:\d{4}[\s-]?){3}\d{4}\b",     # credit card
            r"\b\d{3}-\d{2}-\d{4}\b",             # SSN
            r"\b[A-Za-z0-9+/]{20,}={0,2}\b",     # base64 blob (potential exfil)
        ]
        dlp_regex = re.compile("|".join(DLP_PATTERNS), re.IGNORECASE)

        def _dlp_hit(text):
            if not isinstance(text, str):
                return 0
            return 1 if dlp_regex.search(text[:3000]) else 0

        email["_dlp_hit"] = email["content"].apply(_dlp_hit)
        dlp_grp = email.groupby(["user", "date"])["_dlp_hit"].sum().reset_index()
        dlp_grp.rename(columns={"_dlp_hit": "dlp_keyword_hit_count"}, inplace=True)
        feat = feat.merge(dlp_grp, on=["user", "date"], how="left")
    else:
        feat["dlp_keyword_hit_count"] = 0

    feat["dlp_keyword_hit_count"] = feat["dlp_keyword_hit_count"].fillna(0)
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
# Label extractor — loads ground truth from Dataset/answers/insiders.csv
# ---------------------------------------------------------------------------

def _find_insiders_csv() -> Path:
    """Search for insiders.csv relative to this file's location."""
    candidates = [
        Path(__file__).resolve().parents[3] / "Dataset" / "answers" / "insiders.csv",
        Path(__file__).resolve().parents[2] / "Dataset" / "answers" / "insiders.csv",
        Path(__file__).resolve().parents[1] / "Dataset" / "answers" / "insiders.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_insider_windows() -> pd.DataFrame:
    """
    Load all confirmed insider threat users with their malicious date windows.

    Returns a DataFrame with columns: [user, scenario, start, end]
    where start/end are pd.Timestamp and scenario is the CERT scenario int (1-5).
    Returns empty DataFrame if file not found.
    """
    csv_path = _find_insiders_csv()
    if csv_path is None:
        logger.warning("insiders.csv not found — labels will be empty (unsupervised only).")
        return pd.DataFrame(columns=["user", "scenario", "start", "end"])

    df = pd.read_csv(csv_path)
    df["user"]     = df["user"].str.strip()
    df["scenario"] = pd.to_numeric(df["scenario"], errors="coerce").fillna(0).astype(int)
    df["start"]    = pd.to_datetime(df["start"], errors="coerce", dayfirst=False)
    df["end"]      = pd.to_datetime(df["end"],   errors="coerce", dayfirst=False)
    df = df.dropna(subset=["user", "start", "end"])
    logger.info(f"Loaded {len(df)} insider windows for {df['user'].nunique()} unique users from {csv_path.name}")
    return df[["user", "scenario", "start", "end"]]


# Cache windows at import time
_INSIDER_WINDOWS: pd.DataFrame = load_insider_windows()
CERT_MALICIOUS_USERS: set = set(_INSIDER_WINDOWS["user"].tolist())


def extract_labels(feature_matrix: pd.DataFrame) -> pd.Series:
    """
    Date-aware ground truth labels.

    A (user, date) row is labelled 1 (malicious) ONLY if:
      - The user appears in insiders.csv, AND
      - The row's date falls within [start, end] of at least one of their
        known malicious windows.

    This prevents poisoning the model with benign behaviour that the insider
    exhibited BEFORE or AFTER their malicious period.
    """
    if _INSIDER_WINDOWS.empty:
        logger.warning("No insider windows loaded — all labels set to 0 (unsupervised mode).")
        return pd.Series(0, index=feature_matrix.index, name="label")

    fm = feature_matrix.copy()
    fm["date"] = pd.to_datetime(fm["date"])
    fm["_label"] = 0

    for _, win in _INSIDER_WINDOWS.iterrows():
        mask = (
            (fm["user"] == win["user"])
            & (fm["date"] >= win["start"])
            & (fm["date"] <= win["end"])
        )
        fm.loc[mask, "_label"] = 1

    labels = fm["_label"].rename("label")
    n_threat = int(labels.sum())
    n_benign = len(labels) - n_threat
    logger.info(
        f"Date-aware labels: {n_threat:,} threat user-days / {n_benign:,} benign user-days "
        f"({100 * n_threat / max(len(labels), 1):.2f}% positive)"
    )
    if n_threat == 0:
        logger.warning(
            "⚠  Zero malicious user-days found! This usually means the date range you "
            "are loading (via date filter or sampling) does not overlap with any known "
            "insider's malicious window. Try loading more data or a wider date range."
        )
    return labels
