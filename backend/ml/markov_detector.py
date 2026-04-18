"""
markov_detector.py
------------------
Detects ordered attack sequences using Markov Chain transition scoring.

Instead of just flagging individual feature spikes, this module looks at
the *order* of anomalous activity across consecutive days per user — if
a user follows the exact pattern of a known attack chain, their score spikes.

Attack chains are inspired by the MITRE ATT&CK framework.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attack chain definitions
# Each chain is an ordered list of (feature_column, threshold) tuples.
# A user must exceed the threshold on consecutive days to match the chain.
# ---------------------------------------------------------------------------

ATTACK_CHAINS: Dict[str, List[tuple]] = {
    "DATA_EXFILTRATION": [
        ("http_request_count",     50.0),   # Stage 1: Recon via HTTP
        ("file_sharing_visit_count", 2.0),  # Stage 2: Cloud upload recon
        ("usb_connect_count",       1.0),   # Stage 3: USB inserted
        ("file_copy_count",        10.0),   # Stage 4: Mass file copy
    ],
    "PRIVILEGE_ABUSE": [
        ("login_count",            10.0),   # Stage 1: High login volume
        ("unique_pcs",              3.0),   # Stage 2: Lateral movement
        ("file_copy_count",         5.0),   # Stage 3: File access
        ("external_email_ratio",    0.4),   # Stage 4: External data sending
    ],
    "SABOTAGE": [
        ("after_hours_login_count", 1.0),   # Stage 1: After-hours login
        ("unique_pcs",              3.0),   # Stage 2: Access multiple systems
        ("http_request_count",     30.0),   # Stage 3: Reconnaissance
        ("after_hours_activity_total", 3.0),# Stage 4: After-hours action
    ],
    "MASS_EXFIL": [
        ("http_request_count",    100.0),   # Stage 1: High HTTP volume
        ("file_copy_count",        20.0),   # Stage 2: Mass copy
        ("usb_connect_count",       1.0),   # Stage 3: USB exfil
    ],
}

# Partial match scoring: if N-1 of N stages are matched, partial credit given
PARTIAL_CREDIT = 0.5


def score_markov_sequences(
    feature_matrix: pd.DataFrame,
    window_days: int = 7,
) -> pd.Series:
    """
    For each (user, date) row, compute a Markov sequence attack score ∈ [0, 1].

    The score reflects whether the user's recent history (within `window_days`)
    follows any known attack chain ordering.

    Parameters
    ----------
    feature_matrix : Feature matrix (output of behavior_profiler).
    window_days    : Look-back window in days to evaluate sequences.

    Returns
    -------
    pd.Series of markov_score values, aligned to feature_matrix index.
    """
    logger.info("Scoring Markov attack sequences ...")
    df = feature_matrix.sort_values(["user", "date"]).copy()
    markov_scores = pd.Series(0.0, index=df.index, name="markov_score")

    for user_id, user_df in df.groupby("user"):
        user_df = user_df.sort_values("date").reset_index()
        dates = user_df["date"].tolist()

        for i, row in user_df.iterrows():
            current_date = row["date"]
            # Look-back window
            window_start = current_date - pd.Timedelta(days=window_days)
            history = user_df[user_df["date"] >= window_start].reset_index(drop=True)

            if len(history) < 2:
                continue

            best_score = 0.0

            for chain_name, stages in ATTACK_CHAINS.items():
                matched_stages = 0
                # Check if stages are matched in chronological order
                stage_idx = 0
                for _, hist_row in history.iterrows():
                    if stage_idx >= len(stages):
                        break
                    feat_col, threshold = stages[stage_idx]
                    val = hist_row.get(feat_col, 0)
                    if pd.isna(val):
                        val = 0
                    if float(val) >= threshold:
                        matched_stages += 1
                        stage_idx += 1

                n_stages = len(stages)
                if matched_stages == n_stages:
                    chain_score = 1.0
                elif matched_stages == n_stages - 1:
                    chain_score = PARTIAL_CREDIT
                else:
                    chain_score = matched_stages / n_stages * 0.3

                best_score = max(best_score, chain_score)

            orig_idx = user_df.iloc[i]["index"] if "index" in user_df.columns else i
            if orig_idx in markov_scores.index:
                markov_scores.at[orig_idx] = best_score

    logger.info(
        f"  → Markov scoring complete. "
        f"{(markov_scores > 0.5).sum():,} high-confidence attack sequences detected."
    )
    return markov_scores
