"""
SQLAlchemy ORM models for the UEBA platform.
Tables: users, daily_features, risk_scores, alerts, auth_users
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

    risk_scores = relationship("RiskScore", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")


class DailyFeature(Base):
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

    user = relationship("User", back_populates="alerts")


class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="analyst")       # analyst / admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
