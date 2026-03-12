"""
gnn_model.py
------------
Graph Neural Network using PyTorch Geometric.
Constructs a heterogeneous user–device–file access graph from CERT r4.2
logs and uses GraphSAGE for node-level anomaly scoring.

Novel contribution: detects abnormal cross-entity access patterns
(e.g., a user suddenly accessing many new devices or files).
"""

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import joblib

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_DIR = Path(__file__).parent.parent / "trained_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

GNN_MODEL_PATH = MODEL_DIR / "gnn_model.pt"
GNN_THRESHOLD_PATH = MODEL_DIR / "gnn_threshold.pkl"
GNN_META_PATH = MODEL_DIR / "gnn_meta.pkl"

try:
    from torch_geometric.data import Data
    from torch_geometric.nn import SAGEConv
    PYGEOMETRIC_AVAILABLE = True
except ImportError:
    PYGEOMETRIC_AVAILABLE = False
    logger.warning("torch_geometric not installed. GNN model will be disabled.")


class GraphSAGEAnomalyDetector(nn.Module):
    """
    2-layer GraphSAGE encoder followed by a reconstruction decoder.
    Trained to reconstruct node features; high reconstruction error = anomaly.
    """

    def __init__(self, in_channels: int, hidden_channels: int = 64):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, 32)
        self.decoder = nn.Sequential(
            nn.Linear(32, hidden_channels),
            nn.ReLU(),
            nn.Linear(hidden_channels, in_channels),
        )
        self.relu = nn.ReLU()

    def forward(self, x, edge_index):
        h = self.relu(self.conv1(x, edge_index))
        h = self.relu(self.conv2(h, edge_index))
        return self.decoder(h)


def _build_graph(
    logon: pd.DataFrame,
    device: pd.DataFrame,
    file_df: pd.DataFrame,
    feature_matrix: pd.DataFrame,
) -> Tuple:
    """
    Build a homogeneous user-centric graph.

    Nodes = unique users. Edges = user-pair co-access to same PC or device.
    Node features = aggregated behavioral features from feature_matrix.

    Returns (Data, user_index_map, node_features)
    """
    users = feature_matrix["user"].unique().tolist()
    user_idx = {u: i for i, u in enumerate(users)}

    # Aggregate features per user (mean over all days)
    feat_cols = [c for c in feature_matrix.columns
                 if c not in ("user", "date") and pd.api.types.is_numeric_dtype(feature_matrix[c])]
    user_feats = feature_matrix.groupby("user")[feat_cols].mean().reindex(users).fillna(0)
    node_features = torch.tensor(user_feats.values, dtype=torch.float32)

    # Edges: users who share the same PC on the same day (co-logon)
    logon["date_only"] = logon["timestamp"].dt.date
    co_access = logon.groupby(["pc", "date_only"])["user"].apply(list).reset_index()

    src_list, dst_list = [], []
    for _, row in co_access.iterrows():
        us = [u for u in row["user"] if u in user_idx]
        for i in range(len(us)):
            for j in range(i + 1, len(us)):
                src_list.append(user_idx[us[i]])
                dst_list.append(user_idx[us[j]])
                src_list.append(user_idx[us[j]])
                dst_list.append(user_idx[us[i]])

    # Edges from shared USB devices (device.csv)
    dev_df = device.copy()
    if "timestamp" in dev_df.columns:
        dev_df["date_only"] = dev_df["timestamp"].dt.date
        co_dev = dev_df.groupby(["pc", "date_only"])["user"].apply(list).reset_index()
        for _, row in co_dev.iterrows():
            us = [u for u in row["user"] if u in user_idx]
            for i in range(len(us)):
                for j in range(i + 1, len(us)):
                    src_list.append(user_idx[us[i]])
                    dst_list.append(user_idx[us[j]])

    if not src_list:
        # Fallback: no edges → self-loops
        src_list = list(range(len(users)))
        dst_list = list(range(len(users)))

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
    graph_data = Data(x=node_features, edge_index=edge_index)
    return graph_data, user_idx, feat_cols


def train(
    feature_matrix: pd.DataFrame,
    logon: pd.DataFrame,
    device: pd.DataFrame,
    file_df: pd.DataFrame,
    benign_labels: pd.Series,
    epochs: int = 50,
    lr: float = 1e-3,
    torch_device: str = None,
) -> Tuple:
    if not PYGEOMETRIC_AVAILABLE:
        logger.warning("Skipping GNN training — torch_geometric not available.")
        return None, None, None

    torch_device = torch_device or ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Building graph and training GNN on device={torch_device} ...")

    graph_data, user_idx, feat_cols = _build_graph(logon, device, file_df, feature_matrix)
    graph_data = graph_data.to(torch_device)

    in_channels = graph_data.x.shape[1]
    model = GraphSAGEAnomalyDetector(in_channels=in_channels).to(torch_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    # Train on all nodes (unsupervised reconstruction)
    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        recon = model(graph_data.x, graph_data.edge_index)
        loss = criterion(recon, graph_data.x)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 10 == 0:
            logger.info(f"  Epoch {epoch+1}/{epochs}  loss={loss.item():.5f}")

    # Compute benign node errors for threshold
    benign_users = set(feature_matrix[benign_labels == 0]["user"].unique())
    benign_indices = [user_idx[u] for u in benign_users if u in user_idx]

    model.eval()
    with torch.no_grad():
        recon = model(graph_data.x, graph_data.edge_index).cpu().numpy()
    x_np = graph_data.x.cpu().numpy()
    errors = np.mean((x_np - recon) ** 2, axis=1)
    benign_errors = errors[benign_indices]
    threshold = float(np.percentile(benign_errors, 95))

    torch.save(model.state_dict(), GNN_MODEL_PATH)
    joblib.dump(threshold, GNN_THRESHOLD_PATH)
    joblib.dump({"user_idx": user_idx, "feat_cols": feat_cols, "in_channels": in_channels}, GNN_META_PATH)
    logger.info(f"  → GNN saved. Threshold={threshold:.6f}")
    return model, user_idx, threshold


def score(
    feature_matrix: pd.DataFrame,
    logon: pd.DataFrame,
    device: pd.DataFrame,
    file_df: pd.DataFrame,
    model=None,
    torch_device: str = None,
) -> pd.Series:
    """Return per-user GNN anomaly scores (mean over all days for that user)."""
    gnn_scores = pd.Series(0.0, index=feature_matrix.index, name="gnn_score")

    if not PYGEOMETRIC_AVAILABLE:
        return gnn_scores

    torch_device = torch_device or ("cuda" if torch.cuda.is_available() else "cpu")
    meta = joblib.load(GNN_META_PATH)
    user_idx = meta["user_idx"]
    threshold = joblib.load(GNN_THRESHOLD_PATH)

    graph_data, _, _ = _build_graph(logon, device, file_df, feature_matrix)
    graph_data = graph_data.to(torch_device)

    if model is None:
        model = GraphSAGEAnomalyDetector(in_channels=meta["in_channels"]).to(torch_device)
        model.load_state_dict(torch.load(GNN_MODEL_PATH, map_location=torch_device))

    model.eval()
    with torch.no_grad():
        recon = model(graph_data.x, graph_data.edge_index).cpu().numpy()
    x_np = graph_data.x.cpu().numpy()
    errors = np.mean((x_np - recon) ** 2, axis=1)
    max_err = max(threshold * 3, errors.max())
    normalised = np.clip(errors / max_err, 0.0, 1.0)

    # Map node scores back to each row of feature_matrix
    user_score_map = {user: normalised[idx] for user, idx in user_idx.items()}
    gnn_scores = feature_matrix["user"].map(user_score_map).fillna(0.0)
    gnn_scores.name = "gnn_score"
    gnn_scores.index = feature_matrix.index
    return gnn_scores
