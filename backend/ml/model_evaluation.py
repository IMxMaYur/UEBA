"""
model_evaluation.py
-------------------
Evaluates the full ML pipeline against CERT r4.2 ground-truth red-team labels.
Prints precision, recall, F1-score, ROC-AUC, and a confusion matrix.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_curve,
    average_precision_score,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def evaluate(
    scored_df: pd.DataFrame,
    labels: pd.Series,
    threshold: float = None,
) -> dict:
    """
    Evaluate model performance against binary ground-truth labels.

    Parameters
    ----------
    scored_df  : DataFrame containing 'risk_score' column (from risk_scoring_engine).
    labels     : Binary Series (0=benign, 1=threat), aligned to scored_df.
    threshold  : Decision threshold. Defaults to env RISK_THRESHOLD or 0.65.

    Returns
    -------
    dict with evaluation metrics.
    """
    import os
    if threshold is None:
        threshold = float(os.getenv("RISK_THRESHOLD", "0.65"))

    y_true = labels.values
    y_score = scored_df["risk_score"].values
    y_pred = (y_score >= threshold).astype(int)

    # Guard against single-class
    unique_classes = np.unique(y_true)
    if len(unique_classes) < 2:
        logger.warning("Only one class in labels — ROC-AUC undefined.")
        roc_auc = float("nan")
        avg_precision = float("nan")
    else:
        roc_auc = roc_auc_score(y_true, y_score)
        avg_precision = average_precision_score(y_true, y_score)

    report = classification_report(y_true, y_pred, target_names=["Benign", "Threat"], output_dict=True)
    cm = confusion_matrix(y_true, y_pred)

    metrics = {
        "roc_auc": roc_auc,
        "average_precision": avg_precision,
        "precision": report["Threat"]["precision"],
        "recall": report["Threat"]["recall"],
        "f1_score": report["Threat"]["f1-score"],
        "threshold": threshold,
        "n_alerts": int(y_pred.sum()),
        "n_true_positives": int(cm[1, 1]) if cm.shape == (2, 2) else 0,
        "n_false_positives": int(cm[0, 1]) if cm.shape == (2, 2) else 0,
        "n_false_negatives": int(cm[1, 0]) if cm.shape == (2, 2) else 0,
    }

    logger.info("=" * 55)
    logger.info("  MODEL EVALUATION RESULTS")
    logger.info("=" * 55)
    logger.info(f"  ROC-AUC:           {roc_auc:.4f}")
    logger.info(f"  Avg Precision:     {avg_precision:.4f}")
    logger.info(f"  Precision@{threshold}: {metrics['precision']:.4f}")
    logger.info(f"  Recall@{threshold}:    {metrics['recall']:.4f}")
    logger.info(f"  F1-Score:          {metrics['f1_score']:.4f}")
    logger.info(f"  True Positives:    {metrics['n_true_positives']}")
    logger.info(f"  False Positives:   {metrics['n_false_positives']}")
    logger.info(f"  False Negatives:   {metrics['n_false_negatives']}")
    logger.info("=" * 55)
    return metrics


def find_optimal_threshold(scored_df: pd.DataFrame, labels: pd.Series) -> float:
    """
    Find the threshold that maximises F1-score on the labelled data.
    Returns the optimal threshold value.
    """
    y_true = labels.values
    y_score = scored_df["risk_score"].values
    precision_arr, recall_arr, thresholds = precision_recall_curve(y_true, y_score)
    f1_scores = np.where(
        (precision_arr + recall_arr) > 0,
        2 * precision_arr * recall_arr / (precision_arr + recall_arr),
        0,
    )
    best_idx = np.argmax(f1_scores[:-1])  # thresholds is one shorter
    best_threshold = float(thresholds[best_idx])
    logger.info(f"Optimal threshold for F1: {best_threshold:.4f}  (F1={f1_scores[best_idx]:.4f})")
    return best_threshold
