"""
sentiment_analyzer.py
---------------------
Lightweight email sentiment analysis using TextBlob.

Computes per-(user, date) average email sentiment score (−1.0 to +1.0).
A sharp drop into negative territory (e.g., score < −0.3) is a known
precursor to insider threat incidents (disgruntlement signal).

No external API required — runs fully offline.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _get_polarity(text: str) -> float:
    """Return sentiment polarity using TextBlob (−1 to +1). Falls back to 0."""
    if not text or not isinstance(text, str) or len(text.strip()) < 5:
        return 0.0
    try:
        from textblob import TextBlob
        return TextBlob(text[:2000]).sentiment.polarity  # cap at 2000 chars for speed
    except ImportError:
        # TextBlob not installed — fall back to keyword-based scoring
        return _keyword_sentiment(text)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Keyword-based fallback (no dependencies)
# ---------------------------------------------------------------------------

_NEGATIVE_KEYWORDS = [
    "hate", "unfair", "resign", "quit", "fired", "frustrated", "angry",
    "lawsuit", "discrimination", "threat", "revenge", "steal", "leak",
    "destroy", "corrupt", "sabotage", "expose", "betrayal", "furious",
    "termination", "layoff", "screwed", "terrible", "worst", "horrible"
]
_POSITIVE_KEYWORDS = [
    "great", "excellent", "happy", "love", "wonderful", "amazing",
    "promoted", "bonus", "congratulations", "proud", "excited", "thank"
]


def _keyword_sentiment(text: str) -> float:
    text_lower = text.lower()
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)
    total = neg + pos
    if total == 0:
        return 0.0
    return (pos - neg) / total


def compute_email_sentiment(
    email_df: pd.DataFrame,
    content_col: str = "content",
    sample_n: Optional[int] = 3,
) -> pd.DataFrame:
    """
    Compute per-(user, date) mean email sentiment score.

    Parameters
    ----------
    email_df    : Parsed email DataFrame (must have 'user', 'date', content_col).
    content_col : Name of the raw email body column (default 'content').
    sample_n    : Sample at most N emails per user per day for speed.

    Returns
    -------
    DataFrame with columns [user, date, email_sentiment_score].
    """
    logger.info("Computing email sentiment scores ...")

    if content_col not in email_df.columns:
        logger.warning(f"  '{content_col}' column not found — sentiment will be 0.")
        return pd.DataFrame(columns=["user", "date", "email_sentiment_score"])

    df = email_df[["user", "date", content_col]].copy()
    df["date"] = pd.to_datetime(df["date"])

    # Sample per group to avoid scoring millions of rows
    if sample_n:
        df = (
            df.groupby(["user", "date"])
            .apply(lambda g: g.sample(min(len(g), sample_n), random_state=42))
            .reset_index(drop=True)
        )

    df["_polarity"] = df[content_col].apply(_get_polarity)

    result = (
        df.groupby(["user", "date"])["_polarity"]
        .mean()
        .reset_index()
        .rename(columns={"_polarity": "email_sentiment_score"})
    )

    # Clip to valid range
    result["email_sentiment_score"] = result["email_sentiment_score"].clip(-1.0, 1.0).fillna(0.0)

    negative_users = (result["email_sentiment_score"] < -0.3).sum()
    logger.info(
        f"  → Sentiment done. {len(result):,} user-days scored. "
        f"{negative_users:,} with negative tone (< −0.3)."
    )
    return result
