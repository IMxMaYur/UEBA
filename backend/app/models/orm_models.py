"""
SQLAlchemy ORM models for the UEBA platform.
Tables: users, daily_features, risk_scores, alerts, auth_users, playbook_actions
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime,
    Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)   # CERT user ID e.g. "ACM2278"
    name = Column(String, nullable=True)
    department = Column(String, nullable=True)
    role = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    latest_risk_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # OCEAN personality traits (scores 10–50 from CERT psychometric dataset)
    ocean_o = Column(Integer, nullable=True)   # Openness to Experience
    ocean_c = Column(Integer, nullable=True)   # Conscientiousness
    ocean_e = Column(Integer, nullable=True)   # Extraversion
    ocean_a = Column(Integer, nullable=True)   # Agreeableness
    ocean_n = Column(Integer, nullable=True)   # Neuroticism

    risk_scores    = relationship("RiskScore",    back_populates="user", cascade="all, delete-orphan")
    alerts         = relationship("Alert",         back_populates="user", cascade="all, delete-orphan")
    daily_features = relationship("DailyFeature",  back_populates="user", cascade="all, delete-orphan")
    playbook_actions = relationship("PlaybookAction", back_populates="user", cascade="all, delete-orphan")



class DailyFeature(Base):  # noqa
    __tablename__ = "daily_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Login
    login_count = Column(Float, default=0)
    after_hours_login_count = Column(Float, default=0)
    login_hour_mean = Column(Float, default=0)
    unique_pcs = Column(Float, default=0)
    # Device
    usb_connect_count = Column(Float, default=0)
    after_hours_usb = Column(Float, default=0)
    # File
    file_copy_count = Column(Float, default=0)
    after_hours_file_copy = Column(Float, default=0)
    # Email
    email_sent_count = Column(Float, default=0)
    external_email_ratio = Column(Float, default=0)
    suspicious_attachment_count = Column(Float, default=0)
    total_email_size_bytes = Column(Float, default=0)
    # HTTP
    http_request_count = Column(Float, default=0)
    file_sharing_visit_count = Column(Float, default=0)
    # Derived
    exfil_indicator = Column(Float, default=0)
    after_hours_activity_total = Column(Float, default=0)
    behavior_spike_score = Column(Float, default=0)
    # Peer-group & advanced analytics
    peer_risk_score = Column(Float, default=0)          # Anomaly vs. dept peers
    dlp_keyword_hit_count = Column(Float, default=0)    # DLP sensitive content hits
    email_sentiment_score = Column(Float, default=0.0)  # −1 (negative) to +1 (positive)
    # Feedback loop
    is_false_positive = Column(Boolean, default=False)  # Analyst-marked false positive

    user = relationship("User", back_populates="daily_features")



class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    if_score = Column(Float, default=0)
    ae_score = Column(Float, default=0)
    lstm_score = Column(Float, default=0)
    gnn_score = Column(Float, default=0)
    rule_score = Column(Float, default=0)
    risk_score = Column(Float, default=0)

    user = relationship("User", back_populates="risk_scores")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    alert_type = Column(String, nullable=False)
    severity = Column(String, default="MEDIUM")   # LOW / MEDIUM / HIGH / CRITICAL
    risk_score = Column(Float, default=0)
    shap_json = Column(JSON, nullable=True)        # top-5 SHAP features
    status = Column(String, default="OPEN")        # OPEN / INVESTIGATING / RESOLVED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)
    narrative = Column(Text, nullable=True)        # AI-generated human-readable explanation
    geo_details = Column(JSON, nullable=True)      # Impossible travel geo context

    user = relationship("User", back_populates="alerts")
    playbook_actions = relationship("PlaybookAction", back_populates="alert", cascade="all, delete-orphan")


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="analyst")       # analyst / admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class PlaybookAction(Base):
    """Records automated SOAR response actions taken for each alert."""
    __tablename__ = "playbook_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tier = Column(Integer, nullable=False)         # 1, 2, or 3
    action_name = Column(String, nullable=False)   # MFA_STEPUP, SESSION_REVOCATION, etc.
    description = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow)
    risk_score_at_trigger = Column(Float, nullable=True)

    alert = relationship("Alert", back_populates="playbook_actions")
    user  = relationship("User",  back_populates="playbook_actions")


# ═══════════════════════════════════════════════════════════════════════════
# Live Monitoring Models
# ═══════════════════════════════════════════════════════════════════════════

class ActivityEvent(Base):
    """Stores every telemetry event received from the endpoint agent."""
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, nullable=False, index=True)
    hostname = Column(String, nullable=True)
    event_type = Column(String, nullable=False, index=True)
    # USB_INSERTED, USB_REMOVED, FILE_CREATED, FILE_DELETED, FILE_MOVED,
    # FILE_MODIFIED, RESTRICTED_WEBSITE, BLOCKED_PROCESS, LOGIN, LOGOUT, HEARTBEAT
    details = Column(JSON, nullable=True)
    is_violation = Column(Boolean, default=False)
    warning_level = Column(Integer, nullable=True)  # 1, 2, 3 if violation
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Policy(Base):
    """Company-defined security policies (restricted sites, blocked processes, etc.)."""
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_type = Column(String, nullable=False)
    # RESTRICTED_WEBSITE, RESTRICTED_KEYWORD, BLOCKED_PROCESS, MONITORED_FOLDER
    value = Column(String, nullable=False)           # e.g., "facebook.com"
    description = Column(String, nullable=True)      # e.g., "Social media not allowed"
    severity = Column(String, default="MEDIUM")      # LOW, MEDIUM, HIGH
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class EmployeeSession(Base):
    """Tracks currently connected employee agents (online/offline/idle)."""
    __tablename__ = "employee_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, nullable=False, unique=True, index=True)
    hostname = Column(String, nullable=True)
    os_info = Column(String, nullable=True)
    status = Column(String, default="ONLINE")        # ONLINE, OFFLINE, IDLE, RESTRICTED
    warning_count = Column(Integer, default=0)
    is_restricted = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow)
    connected_at = Column(DateTime, default=datetime.datetime.utcnow)
