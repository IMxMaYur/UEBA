"""
isolation_forest.py
-------------------
Trains and scores an Isolation Forest model for unsupervised anomaly detection
on per-(user, day) feature vectors from the CERT r4.2 dataset.
"""

import logging
import joblib
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_DIR = Path(__file__).parent.parent / "trained_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

IF_MODEL_PATH = MODEL_DIR / "isolation_forest.pkl"
IF_SCALER_PATH = MODEL_DIR / "if_scaler.pkl"

# All numeric features used as model input
FEATURE_COLS = [
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb",
    "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "total_recipient_count", "external_recipient_count",
    "external_email_ratio", "total_email_size_bytes", "total_attachments",
    "after_hours_email", "suspicious_attachment_count",
    "http_request_count", "file_sharing_visit_count", "after_hours_http",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
    # Z-score features
    "login_count_zscore", "after_hours_login_count_zscore",
    "usb_connect_count_zscore", "file_copy_count_zscore",
    "email_sent_count_zscore", "external_email_ratio_zscore",
    "http_request_count_zscore", "file_sharing_visit_count_zscore",
    "exfil_indicator_zscore", "after_hours_activity_total_zscore",
]


def _get_feature_matrix(df: pd.DataFrame) -> np.ndarray:
    cols = [c for c in FEATURE_COLS if c in df.columns]
    return df[cols].fillna(0).values


def train(
    feature_matrix: pd.DataFrame,
    contamination: float = 0.02,
    n_estimators: int = 200,
    random_state: int = 42,
) -> Tuple[IsolationForest, StandardScaler]:
    """
    Train an Isolation Forest on the full feature matrix.

    Parameters
    ----------
    feature_matrix : Feature matrix from behavior_profiler output.
    contamination  : Expected fraction of anomalies (≈ CERT threat rate).
    """
    logger.info("Training Isolation Forest ...")
    X = _get_feature_matrix(feature_matrix)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    joblib.dump(model, IF_MODEL_PATH)
    joblib.dump(scaler, IF_SCALER_PATH)
    logger.info(f"  → Isolation Forest saved to {IF_MODEL_PATH}")
    return model, scaler


def score(
    feature_matrix: pd.DataFrame,
    model: IsolationForest = None,
    scaler: StandardScaler = None,
) -> pd.Series:
    """
    Return anomaly scores ∈ [0, 1] for each row. Higher = more anomalous.

    Loads persisted model+scaler if not provided.
    """
    if model is None:
        model = joblib.load(IF_MODEL_PATH)
    if scaler is None:
        scaler = joblib.load(IF_SCALER_PATH)

    X = _get_feature_matrix(feature_matrix)
    X_scaled = scaler.transform(X)

    # IsolationForest.decision_function returns negative anomaly scores;
    # lower = more anomalous.  We invert and normalise to [0, 1].
    raw_scores = model.decision_function(X_scaled)
    # Normalise: most negative → 1.0, most positive → 0.0
    min_s, max_s = raw_scores.min(), raw_scores.max()
    if max_s == min_s:
        normalised = np.zeros_like(raw_scores)
    else:
        normalised = 1 - (raw_scores - min_s) / (max_s - min_s)

    return pd.Series(normalised, index=feature_matrix.index, name="if_score")


def load_model() -> Tuple[IsolationForest, StandardScaler]:
    return joblib.load(IF_MODEL_PATH), joblib.load(IF_SCALER_PATH)
