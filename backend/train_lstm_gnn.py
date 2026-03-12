"""
train_lstm_gnn.py
-----------------
Standalone script to train ONLY the LSTM and GNN models and save them to
trained_models/.  Run this after the Isolation Forest and Autoencoder are
already saved (i.e., after a previous pipeline run).

Usage:
    python train_lstm_gnn.py               # uses default HTTP sample (10%)
    python train_lstm_gnn.py --mode=test   # tiny sample, fast (~5 min)
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ml import data_loader, log_parser, feature_engineering, behavior_profiler
from ml import lstm_model as lstm_module
from ml import gnn_model as gnn_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run(mode: str = "full", http_sample: float = None):
    logger.info(f"=== LSTM + GNN Training  [mode={mode}] ===")

    if mode == "test":
        http_sample = http_sample or 0.02
        email_sample = 0.05
    else:
        http_sample = http_sample or 0.10
        email_sample = 1.0

    # 1. Load raw data
    logger.info("Loading raw data ...")
    raw = data_loader.load_all(
        http_sample_rate=http_sample,
        email_sample_rate=email_sample,
    )

    # 2. Parse & normalise
    logger.info("Parsing logs ...")
    parsed = log_parser.parse_all(raw)

    # 3. Feature engineering
    logger.info("Building feature matrix ...")
    feature_matrix = feature_engineering.build_feature_matrix(parsed)

    # 4. Behaviour profiling (Z-scores)
    feature_matrix = behavior_profiler.compute_zscore_features(feature_matrix)

    # 5. Ground-truth labels (benign = 0, threat = 1)
    labels = feature_engineering.extract_labels(feature_matrix)

    # 6. Train & save LSTM
    logger.info("Training LSTM ...")
    lstm_model, lstm_scaler, lstm_threshold = lstm_module.train(feature_matrix, labels)
    logger.info("  LSTM model saved to trained_models/lstm_model.pt")

    # 7. Train & save GNN
    logger.info("Training GNN ...")
    gnn_model_obj, _, _ = gnn_module.train(
        feature_matrix,
        logon=parsed["logon"],
        device=parsed["device"],
        file_df=parsed["file"],
        benign_labels=labels,
    )
    if gnn_model_obj is not None:
        logger.info("  GNN model saved to trained_models/gnn_model.pt")
    else:
        logger.warning("  GNN skipped (torch_geometric not available).")

    logger.info("=== LSTM + GNN Training Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and save LSTM + GNN models")
    parser.add_argument("--mode", choices=["full", "test"], default="test",
                        help="'test' uses a small data sample for speed")
    parser.add_argument("--sample", type=float, default=None,
                        help="HTTP sample rate override (0.0–1.0)")
    args = parser.parse_args()
    run(mode=args.mode, http_sample=args.sample)
