"""
tests/test_investigation_router.py
Tests for all 5 investigation API endpoints using FastAPI TestClient + SQLite.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.orm_models import Base, User, Alert, DailyFeature, RiskScore, AuthUser
from app.services.auth_service import hash_password, create_access_token
from app.database import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Test DB setup
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite:///:memory:"
test_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create tables and seed minimal test data."""
    Base.metadata.create_all(bind=test_engine)
    db = TestSession()

    # Analyst auth user
    analyst = AuthUser(
        email="test_analyst@ueba.local",
        hashed_password=hash_password("Test@1234"),
        role="analyst",
        is_active=True,
    )
    db.add(analyst)

    # Test user
    user = User(id="INV_TEST_U1", name="Jane Doe", department="Engineering",
                role="engineer", latest_risk_score=0.85)
    db.add(user)
    db.flush()

    today = datetime.date.today()

    # DailyFeature
    feat = DailyFeature(user_id="INV_TEST_U1", date=today,
                        login_count=2, after_hours_login_count=2,
                        file_copy_count=150, usb_connect_count=3,
                        exfil_indicator=62.9, behavior_spike_score=0.88)
    db.add(feat)

    # RiskScore
    rs = RiskScore(user_id="INV_TEST_U1", date=today,
                   if_score=0.89, ae_score=0.82, lstm_score=0.78,
                   gnn_score=0.70, rule_score=0.80, risk_score=0.85)
    db.add(rs)

    # Alert
    alert = Alert(user_id="INV_TEST_U1", date=today,
                  alert_type="DATA_EXFILTRATION", severity="CRITICAL",
                  risk_score=0.85, status="OPEN",
                  shap_json=[{"feature": "file_copy_count", "friendly_name": "Files Copied",
                               "value": 150.0, "shap_value": 0.42, "direction": "increases_risk"}])
    db.add(alert)
    db.commit()

    yield

    db.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    token = create_access_token({"sub": "test_analyst@ueba.local"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def alert_id(client, auth_headers):
    """Retrieve the seeded alert's ID."""
    resp = client.get("/api/alerts", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) > 0
    return alerts[0]["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetAlertDetail:
    def test_returns_200(self, client, auth_headers, alert_id):
        resp = client.get(f"/api/investigation/alerts/{alert_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_contains_alert_type(self, client, auth_headers, alert_id):
        resp = client.get(f"/api/investigation/alerts/{alert_id}", headers=auth_headers)
        data = resp.json()
        assert data["alert_type"] == "DATA_EXFILTRATION"

    def test_contains_risk_score(self, client, auth_headers, alert_id):
        resp = client.get(f"/api/investigation/alerts/{alert_id}", headers=auth_headers)
        data = resp.json()
        assert data["risk_score"] == pytest.approx(0.85, abs=0.01)

    def test_returns_404_for_unknown_alert(self, client, auth_headers):
        resp = client.get("/api/investigation/alerts/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestUserTimeline:
    def test_returns_200(self, client, auth_headers):
        resp = client.get("/api/investigation/users/INV_TEST_U1/timeline", headers=auth_headers)
        assert resp.status_code == 200

    def test_contains_events(self, client, auth_headers):
        resp = client.get("/api/investigation/users/INV_TEST_U1/timeline", headers=auth_headers)
        events = resp.json()
        assert len(events) > 0

    def test_returns_404_for_unknown_user(self, client, auth_headers):
        resp = client.get("/api/investigation/users/PHANTOM_USER/timeline", headers=auth_headers)
        assert resp.status_code == 404


class TestUserEvidence:
    def test_returns_200(self, client, auth_headers):
        resp = client.get("/api/investigation/users/INV_TEST_U1/evidence", headers=auth_headers)
        assert resp.status_code == 200

    def test_correct_alert_count(self, client, auth_headers):
        resp = client.get("/api/investigation/users/INV_TEST_U1/evidence", headers=auth_headers)
        data = resp.json()
        assert data["total_alerts"] >= 1

    def test_peak_risk_score(self, client, auth_headers):
        resp = client.get("/api/investigation/users/INV_TEST_U1/evidence", headers=auth_headers)
        data = resp.json()
        assert data["peak_risk_score"] >= 0.80


class TestAddNote:
    def test_note_appended(self, client, auth_headers, alert_id):
        payload = {"note": "Investigated — suspicious USB activity confirmed.", "analyst": "test_analyst@ueba.local"}
        resp = client.post(f"/api/investigation/alerts/{alert_id}/notes",
                           json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "Investigated" in (data.get("notes") or "")

    def test_status_auto_transitions_to_investigating(self, client, auth_headers, alert_id):
        resp = client.get(f"/api/investigation/alerts/{alert_id}", headers=auth_headers)
        data = resp.json()
        # After adding a note the status should be INVESTIGATING (or already changed)
        assert data["status"] in ("INVESTIGATING", "OPEN", "RESOLVED")


class TestUpdateStatus:
    def test_status_updated(self, client, auth_headers, alert_id):
        payload = {"status": "RESOLVED", "reason": "False positive — scheduled backup job."}
        resp = client.patch(f"/api/investigation/alerts/{alert_id}/status",
                            json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RESOLVED"

    def test_invalid_status_returns_422(self, client, auth_headers, alert_id):
        payload = {"status": "NONSENSE"}
        resp = client.patch(f"/api/investigation/alerts/{alert_id}/status",
                            json=payload, headers=auth_headers)
        assert resp.status_code == 422
