"""
behavior_profiler.py
--------------------
Builds a 30-day rolling Gaussian baseline per user per feature and computes
Z-score deviation metrics.  These Z-scores are appended to the feature matrix
as additional columns and feed into the anomaly detection models.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Features to compute rolling Z-scores for
ZSCORE_FEATURES = [
    "login_count",
    "after_hours_login_count",
    "usb_connect_count",
    "file_copy_count",
    "email_sent_count",
    "external_email_ratio",
    "http_request_count",
    "file_sharing_visit_count",
    "exfil_indicator",
    "after_hours_activity_total",
]

ROLLING_WINDOW = 30   # days


def _rolling_zscore(user_series: pd.Series, window: int) -> pd.Series:
    """
    For a single user's time series (already sorted by date):
    Compute rolling Z-score = (current - rolling_mean) / rolling_std
    Uses min_periods=3 so we get values after just 3 observations.
    """
    roll = user_series.rolling(window=window, min_periods=3)
    mean = roll.mean()
    std = roll.std().replace(0, np.nan)   # avoid divide-by-zero
    z = (user_series - mean) / std
    return z.fillna(0.0)


def compute_zscore_features(feature_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Add Z-score deviation columns for each feature in ZSCORE_FEATURES.

    New columns are named  <feature>_zscore  (e.g. login_count_zscore).

    Parameters
    ----------
    feature_matrix : pd.DataFrame
        Output of feature_engineering.build_feature_matrix().
        Must have columns: user, date, and all ZSCORE_FEATURES.

    Returns
    -------
    pd.DataFrame with original columns + Z-score columns appended.
    """
    logger.info("Computing 30-day rolling Z-scores ...")
    df = feature_matrix.sort_values(["user", "date"]).copy()

    for feat in ZSCORE_FEATURES:
        if feat not in df.columns:
            logger.warning(f"  Feature '{feat}' not found in matrix — skipping Z-score.")
            continue
        zscore_col = f"{feat}_zscore"
        df[zscore_col] = (
            df.groupby("user")[feat]
            .transform(lambda s: _rolling_zscore(s, ROLLING_WINDOW))
        )

    # Composite behaviour spike score: mean of absolute Z-scores
    zscore_cols = [f"{f}_zscore" for f in ZSCORE_FEATURES if f in df.columns]
    df["behavior_spike_score"] = df[zscore_cols].abs().mean(axis=1)

    logger.info(f"  → Added {len(zscore_cols)} Z-score columns + behavior_spike_score.")
    return df


def get_user_baseline(
    feature_matrix: pd.DataFrame,
    user_id: str,
) -> dict:
    """
    Return a dict of {feature: (mean, std)} over the full history for a
    specific user.  Used for the frontend's User Behavior page to show
    'normal range' bands.
    """
    user_df = feature_matrix[feature_matrix["user"] == user_id]
    baseline = {}
    for feat in ZSCORE_FEATURES:
        if feat in user_df.columns:
            baseline[feat] = {
                "mean": float(user_df[feat].mean()),
                "std": float(user_df[feat].std()),
                "min": float(user_df[feat].min()),
                "max": float(user_df[feat].max()),
            }
    return baseline
