"""
autoencoder.py
--------------
PyTorch Autoencoder trained ONLY on benign (non-threat) user-day records.
Reconstruction error is used as an anomaly score: high error = anomalous.

Architecture: [N → 64 → 32 → 16 → 32 → 64 → N]
"""

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_DIR = Path(__file__).parent.parent / "trained_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

AE_MODEL_PATH = MODEL_DIR / "autoencoder.pt"
AE_SCALER_PATH = MODEL_DIR / "ae_scaler.pkl"
AE_THRESHOLD_PATH = MODEL_DIR / "ae_threshold.pkl"

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


class AutoencoderModel(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


def _get_X(df: pd.DataFrame, scaler: StandardScaler = None, fit: bool = False):
    cols = [c for c in FEATURE_COLS if c in df.columns]
    X = df[cols].fillna(0).values.astype(np.float32)
    if fit:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
        return X, scaler
    else:
        return scaler.transform(X)


def train(
    feature_matrix: pd.DataFrame,
    benign_labels: pd.Series,
    epochs: int = 50,
    batch_size: int = 256,
    lr: float = 1e-3,
    device: str = None,
) -> Tuple[AutoencoderModel, StandardScaler, float]:
    """
    Train autoencoder on benign data only.

    Parameters
    ----------
    feature_matrix : Full feature matrix (all users).
    benign_labels  : Boolean / 0-1 Series; True/1 = benign row.
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Training Autoencoder on device={device} ...")

    benign_df = feature_matrix[benign_labels == 0].copy()
    logger.info(f"  Benign training rows: {len(benign_df):,}")

    X_train, scaler = _get_X(benign_df, fit=True)
    tensor_data = TensorDataset(torch.tensor(X_train))
    loader = DataLoader(tensor_data, batch_size=batch_size, shuffle=True)

    input_dim = X_train.shape[1]
    model = AutoencoderModel(input_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for (batch,) in loader:
            batch = batch.to(device)
            recon = model(batch)
            loss = criterion(recon, batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 10 == 0:
            logger.info(f"  Epoch {epoch + 1}/{epochs}  loss={total_loss / len(loader):.5f}")

    # Compute threshold = 95th percentile of benign reconstruction errors
    model.eval()
    with torch.no_grad():
        X_t = torch.tensor(X_train).to(device)
        recon = model(X_t).cpu().numpy()
    errors = np.mean((X_train - recon) ** 2, axis=1)
    threshold = float(np.percentile(errors, 95))
    logger.info(f"  AE threshold (95th pct benign error): {threshold:.6f}")

    torch.save(model.state_dict(), AE_MODEL_PATH)
    joblib.dump(scaler, AE_SCALER_PATH)
    joblib.dump(threshold, AE_THRESHOLD_PATH)
    logger.info(f"  → Autoencoder saved to {AE_MODEL_PATH}")
    return model, scaler, threshold


def score(
    feature_matrix: pd.DataFrame,
    model: AutoencoderModel = None,
    scaler: StandardScaler = None,
    threshold: float = None,
    device: str = None,
) -> pd.Series:
    """Return AE anomaly scores ∈ [0, 1]."""
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    if scaler is None:
        scaler = joblib.load(AE_SCALER_PATH)
    if threshold is None:
        threshold = joblib.load(AE_THRESHOLD_PATH)
    if model is None:
        cols = [c for c in FEATURE_COLS if c in feature_matrix.columns]
        input_dim = len(cols)
        model = AutoencoderModel(input_dim).to(device)
        model.load_state_dict(torch.load(AE_MODEL_PATH, map_location=device))

    model.eval()
    X = _get_X(feature_matrix, scaler=scaler).astype(np.float32)
    with torch.no_grad():
        X_t = torch.tensor(X).to(device)
        recon = model(X_t).cpu().numpy()

    errors = np.mean((X - recon) ** 2, axis=1)
    # Normalise: clip at 3× threshold then scale to [0, 1]
    max_err = max(threshold * 3, errors.max())
    normalised = np.clip(errors / max_err, 0.0, 1.0)
    return pd.Series(normalised, index=feature_matrix.index, name="ae_score")
