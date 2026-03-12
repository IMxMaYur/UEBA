"""
tests/test_data_ingestion.py
Unit tests for data_ingestion_service.py – upsert logic and alert creation.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use in-memory SQLite for isolation (no PostgreSQL required)
from app.models.orm_models import Base, User, DailyFeature, RiskScore, Alert
from app.services.data_ingestion_service import ingest_scored_data


@pytest.fixture(scope="module")
def db_session():
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_scored_row(user_id="U001", date="2024-01-15", risk_score=0.80):
    return {
        "user": user_id,
        "date": pd.Timestamp(date),
        "login_count": 3.0,
        "after_hours_login_count": 1.0,
        "login_hour_mean": 22.0,
        "unique_pcs": 2.0,
        "usb_connect_count": 1.0,
        "after_hours_usb": 1.0,
        "file_copy_count": 50.0,
        "after_hours_file_copy": 48.0,
        "email_sent_count": 2.0,
        "external_email_ratio": 0.6,
        "suspicious_attachment_count": 0.0,
        "total_email_size_bytes": 500000.0,
        "http_request_count": 80.0,
        "file_sharing_visit_count": 2.0,
        "exfil_indicator": 22.6,
        "after_hours_activity_total": 51.0,
        "behavior_spike_score": 0.75,
        "if_score": 0.85,
        "ae_score": 0.80,
        "lstm_score": 0.70,
        "gnn_score": 0.65,
        "rule_score": 0.40,
        "risk_score": risk_score,
        "is_alert": 1 if risk_score >= 0.65 else 0,
    }


class TestIngestScoredData:
    def test_creates_user_on_first_ingest(self, db_session):
        df = pd.DataFrame([_make_scored_row("INGEST_U001")])
        ingest_scored_data(df, db=db_session)
        user = db_session.query(User).filter(User.id == "INGEST_U001").first()
        assert user is not None
        assert user.latest_risk_score == pytest.approx(0.80, abs=0.01)

    def test_creates_daily_feature(self, db_session):
        df = pd.DataFrame([_make_scored_row("INGEST_U002")])
        ingest_scored_data(df, db=db_session)
        feat = db_session.query(DailyFeature).filter(DailyFeature.user_id == "INGEST_U002").first()
        assert feat is not None
        assert feat.file_copy_count == pytest.approx(50.0)

    def test_creates_risk_score(self, db_session):
        df = pd.DataFrame([_make_scored_row("INGEST_U003")])
        ingest_scored_data(df, db=db_session)
        rs = db_session.query(RiskScore).filter(RiskScore.user_id == "INGEST_U003").first()
        assert rs is not None
        assert rs.risk_score == pytest.approx(0.80, abs=0.01)

    def test_creates_alert_above_threshold(self, db_session):
        df = pd.DataFrame([_make_scored_row("INGEST_U004", risk_score=0.90)])
        ingest_scored_data(df, db=db_session)
        alert = db_session.query(Alert).filter(Alert.user_id == "INGEST_U004").first()
        assert alert is not None
        assert alert.status == "OPEN"

    def test_no_alert_below_threshold(self, db_session):
        df = pd.DataFrame([_make_scored_row("INGEST_U005", risk_score=0.30)])
        ingest_scored_data(df, db=db_session)
        alert = db_session.query(Alert).filter(Alert.user_id == "INGEST_U005").first()
        assert alert is None

    def test_upsert_does_not_duplicate_daily_feature(self, db_session):
        row = _make_scored_row("INGEST_U006")
        df = pd.DataFrame([row])
        ingest_scored_data(df, db=db_session)
        ingest_scored_data(df, db=db_session)  # run twice
        count = db_session.query(DailyFeature).filter(DailyFeature.user_id == "INGEST_U006").count()
        assert count == 1, "Upsert must not duplicate DailyFeature rows"

    def test_upsert_does_not_duplicate_alert(self, db_session):
        row = _make_scored_row("INGEST_U007", risk_score=0.90)
        df = pd.DataFrame([row])
        ingest_scored_data(df, db=db_session)
        ingest_scored_data(df, db=db_session)  # run twice
        count = db_session.query(Alert).filter(Alert.user_id == "INGEST_U007").count()
        assert count == 1, "Upsert must not duplicate Alert rows"

    def test_shap_map_stored_in_alert(self, db_session):
        dummy_shap = [{"feature": "file_copy_count", "friendly_name": "Files Copied",
                       "value": 50.0, "shap_value": 0.42, "direction": "increases_risk"}]
        row = _make_scored_row("INGEST_U008", risk_score=0.90)
        df = pd.DataFrame([row])
        shap_map = {("INGEST_U008", datetime.date(2024, 1, 15)): dummy_shap}
        ingest_scored_data(df, shap_map=shap_map, db=db_session)
        alert = db_session.query(Alert).filter(Alert.user_id == "INGEST_U008").first()
        assert alert is not None
        assert alert.shap_json is not None
        assert alert.shap_json[0]["feature"] == "file_copy_count"
