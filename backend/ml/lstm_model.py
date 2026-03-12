"""
lstm_model.py
-------------
PyTorch LSTM model for sequential anomaly detection.
Uses a 30-day sliding window of daily feature vectors per user.
Trained as a next-day predictor; high prediction MSE = sequence anomaly.
"""

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_DIR = Path(__file__).parent.parent / "trained_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

LSTM_MODEL_PATH = MODEL_DIR / "lstm_model.pt"
LSTM_SCALER_PATH = MODEL_DIR / "lstm_scaler.pkl"
LSTM_THRESHOLD_PATH = MODEL_DIR / "lstm_threshold.pkl"

SEQ_LEN = 30  # 30-day sliding window

FEATURE_COLS = [
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb",
    "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "external_email_ratio",
    "http_request_count", "file_sharing_visit_count",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
]


class SequenceDataset(Dataset):
    """Sliding-window dataset: X = window[t-SEQ_LEN:t], y = window[t]."""

    def __init__(self, sequences: np.ndarray, targets: np.ndarray):
        self.X = torch.tensor(sequences, dtype=torch.float32)
        self.y = torch.tensor(targets, dtype=torch.float32)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class LSTMPredictor(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])   # predict from last time step


def _build_sequences(user_df: pd.DataFrame, cols: list) -> Tuple[np.ndarray, np.ndarray]:
    """Build (X, y) sliding windows for a single user."""
    data = user_df[cols].fillna(0).values
    X, y = [], []
    for i in range(SEQ_LEN, len(data)):
        X.append(data[i - SEQ_LEN:i])
        y.append(data[i])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def train(
    feature_matrix: pd.DataFrame,
    benign_labels: pd.Series,
    epochs: int = 30,
    batch_size: int = 128,
    lr: float = 1e-3,
    device: str = None,
) -> Tuple[LSTMPredictor, StandardScaler, float]:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Training LSTM on device={device} ...")

    cols = [c for c in FEATURE_COLS if c in feature_matrix.columns]

    # Fit scaler on benign only
    benign_df = feature_matrix[benign_labels == 0].copy()
    scaler = StandardScaler()
    scaler.fit(benign_df[cols].fillna(0))
    feature_matrix = feature_matrix.copy()
    feature_matrix[cols] = scaler.transform(feature_matrix[cols].fillna(0))

    # Build sequences from benign users only
    benign_users = benign_df["user"].unique()
    all_X, all_y = [], []
    for user in benign_users:
        user_df = benign_df[benign_df["user"] == user].sort_values("date")
        if len(user_df) <= SEQ_LEN:
            continue
        X_u, y_u = _build_sequences(
            feature_matrix[feature_matrix["user"] == user].sort_values("date"), cols
        )
        all_X.append(X_u)
        all_y.append(y_u)

    if not all_X:
        raise ValueError("Not enough data to build LSTM sequences (need >30 days per user).")

    X_all = np.concatenate(all_X)
    y_all = np.concatenate(all_y)
    logger.info(f"  LSTM training sequences: {len(X_all):,}")

    dataset = SequenceDataset(X_all, y_all)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    input_dim = len(cols)
    model = LSTMPredictor(input_dim=input_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for X_batch, y_batch in loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            pred = model(X_batch)
            loss = criterion(pred, y_batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 5 == 0:
            logger.info(f"  Epoch {epoch+1}/{epochs}  loss={total_loss/len(loader):.5f}")

    # Compute benign threshold (95th percentile)
    model.eval()
    all_errors = []
    with torch.no_grad():
        for X_batch, y_batch in loader:
            pred = model(X_batch.to(device)).cpu().numpy()
            y_np = y_batch.numpy()
            errs = np.mean((pred - y_np) ** 2, axis=1)
            all_errors.extend(errs.tolist())
    threshold = float(np.percentile(all_errors, 95))

    torch.save(model.state_dict(), LSTM_MODEL_PATH)
    joblib.dump(scaler, LSTM_SCALER_PATH)
    joblib.dump(threshold, LSTM_THRESHOLD_PATH)
    logger.info(f"  → LSTM saved. Threshold={threshold:.6f}")
    return model, scaler, threshold


def score(
    feature_matrix: pd.DataFrame,
    model: LSTMPredictor = None,
    scaler: StandardScaler = None,
    threshold: float = None,
    device: str = None,
) -> pd.Series:
    """
    Computes per-row LSTM anomaly scores in [0, 1].
    Rows with < SEQ_LEN history get score 0 (insufficient data).
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    cols = [c for c in FEATURE_COLS if c in feature_matrix.columns]

    if scaler is None:
        scaler = joblib.load(LSTM_SCALER_PATH)
    if threshold is None:
        threshold = joblib.load(LSTM_THRESHOLD_PATH)

    input_dim = len(cols)
    if model is None:
        model = LSTMPredictor(input_dim=input_dim).to(device)
        model.load_state_dict(torch.load(LSTM_MODEL_PATH, map_location=device))

    fm = feature_matrix.copy()
    fm[cols] = scaler.transform(fm[cols].fillna(0))

    lstm_scores = pd.Series(0.0, index=feature_matrix.index, name="lstm_score")
    model.eval()

    for user, user_df in fm.groupby("user"):
        user_df = user_df.sort_values("date")
        if len(user_df) <= SEQ_LEN:
            continue
        X, y = _build_sequences(user_df, cols)
        with torch.no_grad():
            X_t = torch.tensor(X).to(device)
            pred = model(X_t).cpu().numpy()
        errors = np.mean((pred - y) ** 2, axis=1)
        max_err = max(threshold * 3, errors.max())
        normalised = np.clip(errors / max_err, 0.0, 1.0)

        # The first SEQ_LEN rows have no score — keep 0
        score_indices = user_df.index[SEQ_LEN:]
        lstm_scores.loc[score_indices] = normalised

    return lstm_scores
