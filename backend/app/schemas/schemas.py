"""
Pydantic schemas (request/response models) for the UEBA API.
"""
from __future__ import annotations
import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr


# ── Auth ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthUserOut(BaseModel):
    id: int
    email: str
    role: str
    class Config: from_attributes = True


# ── Users ────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    name: Optional[str]
    department: Optional[str]
    role: Optional[str]
    is_active: bool
    latest_risk_score: float
    class Config: from_attributes = True


# ── Daily Features ────────────────────────────────────────────────────────────

class DailyFeatureOut(BaseModel):
    date: datetime.date
    login_count: float
    after_hours_login_count: float
    usb_connect_count: float
    file_copy_count: float
    email_sent_count: float
    external_email_ratio: float
    http_request_count: float
    file_sharing_visit_count: float
    exfil_indicator: float
    behavior_spike_score: float
    class Config: from_attributes = True


# ── Risk Scores ────────────────────────────────────────────────────────────────

class RiskScoreOut(BaseModel):
    date: datetime.date
    if_score: float
    ae_score: float
    lstm_score: float
    gnn_score: float
    rule_score: float
    risk_score: float
    class Config: from_attributes = True


# ── Alerts ────────────────────────────────────────────────────────────────────

class ShapFeature(BaseModel):
    feature: str
    friendly_name: str
    value: float
    shap_value: float
    direction: str

class AlertOut(BaseModel):
    id: int
    user_id: str
    date: datetime.date
    alert_type: str
    severity: str
    risk_score: float
    shap_json: Optional[List[ShapFeature]]
    status: str
    created_at: datetime.datetime
    notes: Optional[str]
    class Config: from_attributes = True

class AlertUpdateRequest(BaseModel):
    status: Optional[str]
    notes: Optional[str]


# ── Dashboard Overview ─────────────────────────────────────────────────────────

class OverviewStats(BaseModel):
    total_users: int
    high_risk_users: int
    open_alerts: int
    critical_alerts: int
    alerts_today: int
    avg_risk_score: float


# ── User Behavior ─────────────────────────────────────────────────────────────

class UserBehaviorResponse(BaseModel):
    user: UserOut
    features_timeline: List[DailyFeatureOut]
    risk_timeline: List[RiskScoreOut]
    alerts: List[AlertOut]
    baseline: Optional[dict]


# ── Investigation ─────────────────────────────────────────────────────────────

class InvestigationNote(BaseModel):
    analyst_email: str
    note: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class AlertDetailOut(BaseModel):
    """Full alert detail for forensic investigation view."""
    id: int
    user_id: str
    date: datetime.date
    alert_type: str
    severity: str
    risk_score: float
    status: str
    shap_json: Optional[List[ShapFeature]]
    notes: Optional[str]
    created_at: datetime.datetime
    # Linked data
    user: Optional[UserOut]
    daily_features: Optional[DailyFeatureOut]
    risk_breakdown: Optional[RiskScoreOut]

    class Config:
        from_attributes = True


class TimelineEvent(BaseModel):
    """Generic chronological event in a user's activity timeline."""
    event_date: datetime.date
    event_type: str          # "LOGIN" | "ALERT" | "FILE_COPY" | "USB" | "EMAIL"
    description: str
    severity: Optional[str]  # populated for alerts
    risk_score: Optional[float]


class EvidenceSummary(BaseModel):
    """Aggregated evidence for an investigated user."""
    user_id: str
    total_alerts: int
    open_alerts: int
    peak_risk_score: float
    peak_risk_date: Optional[datetime.date]
    avg_risk_score_30d: float
    top_risk_factors: List[str]
    alert_type_breakdown: dict
    latest_features: Optional[DailyFeatureOut]


# ── Stats / Trends ─────────────────────────────────────────────────────────────

class DailyTrend(BaseModel):
    """One data point in the alert trend time series."""
    date: datetime.date
    alert_count: int
    avg_risk_score: float


class LeaderboardEntry(BaseModel):
    """One row in the user risk leaderboard."""
    user_id: str
    name: Optional[str]
    department: Optional[str]
    risk_score: float
    open_alerts: int
    total_alerts: int


class ModelMetrics(BaseModel):
    """Evaluation metrics from the last ML pipeline run."""
    roc_auc: float
    average_precision: float
    precision: float
    recall: float
    f1_score: float
    threshold: float
    n_alerts: int
    n_true_positives: int
    n_false_positives: int
    n_false_negatives: int
    last_trained: Optional[str]   # ISO datetime string


# ── Bulk Alert Management ──────────────────────────────────────────────────────

class BulkAlertUpdate(BaseModel):
    """Request body for bulk alert status update."""
    alert_ids: List[int]
    status: str       # OPEN | INVESTIGATING | RESOLVED | FALSE_POSITIVE
    notes: Optional[str] = None


class AlertSummaryItem(BaseModel):
    """One row of the alert summary breakdown."""
    alert_type: str
    severity: str
    status: str
    count: int


# ── User Update ────────────────────────────────────────────────────────────────

class UserUpdateRequest(BaseModel):
    """Fields that an analyst can update on a user record."""
    name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
