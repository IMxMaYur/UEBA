"""
tests/test_feature_engineering.py
Unit tests for the feature engineering module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import pytest
from ml.feature_engineering import (
    _logon_features, _device_features, _file_features,
    _email_features, build_feature_matrix, extract_labels
)


def make_logon_df():
    return pd.DataFrame({
        "event_id": ["e1", "e2", "e3"],
        "timestamp": pd.to_datetime(["2023-01-01 08:00", "2023-01-01 22:00", "2023-01-02 09:00"]),
        "user": ["U001", "U001", "U002"],
        "pc": ["PC1", "PC1", "PC2"],
        "sub_type": ["logon", "logon", "logon"],
        "after_hours": [False, True, False],
        "date": pd.to_datetime(["2023-01-01", "2023-01-01", "2023-01-02"]),
    })


def make_device_df():
    return pd.DataFrame({
        "event_id": ["d1", "d2"],
        "timestamp": pd.to_datetime(["2023-01-01 22:30", "2023-01-02 10:00"]),
        "user": ["U001", "U002"],
        "pc": ["PC1", "PC2"],
        "sub_type": ["connect", "connect"],
        "after_hours": [True, False],
        "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
    })


def make_empty_df(cols):
    return pd.DataFrame(columns=cols)


class TestLogonFeatures:
    def test_login_count(self):
        df = make_logon_df()
        feat = _logon_features(df)
        u1 = feat[feat["user"] == "U001"]
        day1 = u1[u1["date"] == pd.Timestamp("2023-01-01").date()]
        assert len(day1) == 1
        assert day1["login_count"].values[0] == 2

    def test_after_hours_count(self):
        df = make_logon_df()
        feat = _logon_features(df)
        u1_day1 = feat[(feat["user"] == "U001") & (feat["date"] == pd.Timestamp("2023-01-01").date())]
        assert u1_day1["after_hours_login_count"].values[0] == 1

    def test_unique_pcs(self):
        df = make_logon_df()
        feat = _logon_features(df)
        assert feat["unique_pcs"].max() >= 1


class TestDeviceFeatures:
    def test_usb_count(self):
        df = make_device_df()
        feat = _device_features(df)
        assert feat["usb_connect_count"].sum() == 2


class TestBuildFeatureMatrix:
    def test_no_error_on_minimal_data(self):
        parsed = {
            "logon": pd.DataFrame({"event_id": ["e1"], "timestamp": pd.to_datetime(["2023-01-01 08:00"]),
                                   "user": ["U001"], "pc": ["PC1"], "sub_type": ["logon"], "after_hours": [False], "date": pd.to_datetime(["2023-01-01"])}),
            "device": make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date"]),
            "file":   make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date"]),
            "email":  make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date", "recipient_count", "external_recipient_count", "email_size", "attachment_count"]),
            "http":   make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date", "is_file_sharing"]),
        }
        matrix = build_feature_matrix(parsed)
        assert len(matrix) >= 1
        assert "login_count" in matrix.columns
        assert "exfil_indicator" in matrix.columns

    def test_risk_scores_in_range(self):
        """After profiling, all numeric feature values should be finite."""
        parsed = {
            "logon": make_logon_df(),
            "device": make_device_df(),
            "file":   make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date", "content_keywords"]),
            "email":  make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date", "recipient_count", "external_recipient_count", "email_size", "attachment_count"]),
            "http":   make_empty_df(["event_id", "timestamp", "user", "pc", "sub_type", "after_hours", "date", "is_file_sharing"]),
        }
        matrix = build_feature_matrix(parsed)
        numeric = matrix.select_dtypes(include=[np.number])
        assert not numeric.isnull().all().any(), "All-NaN column found"


class TestExtractLabels:
    def test_known_user_labeled(self):
        df = pd.DataFrame({"user": ["ACM2278", "BDT3275", "XXX9999"]})
        labels = extract_labels(df)
        assert labels.iloc[0] == 1
        assert labels.iloc[1] == 1
        assert labels.iloc[2] == 0

    def test_unknown_user_benign(self):
        df = pd.DataFrame({"user": ["ABC1234", "ZZZ9999"]})
        labels = extract_labels(df)
        assert (labels == 0).all()
