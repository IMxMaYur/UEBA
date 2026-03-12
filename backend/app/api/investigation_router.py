"""
investigation_router.py
------------------------
Forensic investigation endpoints for the UEBA Security Analytics Platform.

Provides drill-down capabilities for analysts investigating suspicious alerts,
including full alert detail, user activity timelines, evidence aggregation,
and note-taking / status management.

Prefix: /api/investigation
"""

import datetime
import logging
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import Alert, User, DailyFeature, RiskScore
from app.schemas.schemas import (
    AlertDetailOut,
    AlertOut,
    DailyFeatureOut,
    EvidenceSummary,
    RiskScoreOut,
    TimelineEvent,
    UserOut,
)
from app.services.dependencies import get_current_auth_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigation", tags=["investigation"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _severity_rank(s: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(s.upper(), 0)


# ---------------------------------------------------------------------------
# GET /alerts/{alert_id}  – Full alert detail for investigation panel
# ---------------------------------------------------------------------------

@router.get("/alerts/{alert_id}", response_model=AlertDetailOut)
def get_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Return a fully enriched alert record including:
    - User profile
    - Daily behavioral features for the alert date
    - Per-model risk score breakdown for the alert date
    """
    alert: Optional[Alert] = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    # Linked user
    user: Optional[User] = db.query(User).filter(User.id == alert.user_id).first()

    # Daily features for the exact alert date
    daily: Optional[DailyFeature] = (
        db.query(DailyFeature)
        .filter(
            DailyFeature.user_id == alert.user_id,
            DailyFeature.date == alert.date,
        )
        .first()
    )

    # Risk score breakdown for the alert date
    risk: Optional[RiskScore] = (
        db.query(RiskScore)
        .filter(
            RiskScore.user_id == alert.user_id,
            RiskScore.date == alert.date,
        )
        .first()
    )

    return AlertDetailOut(
        id=alert.id,
        user_id=alert.user_id,
        date=alert.date,
        alert_type=alert.alert_type,
        severity=alert.severity,
        risk_score=alert.risk_score,
        status=alert.status,
        shap_json=alert.shap_json,
        notes=alert.notes,
        created_at=alert.created_at,
        user=UserOut.model_validate(user) if user else None,
        daily_features=DailyFeatureOut.model_validate(daily) if daily else None,
        risk_breakdown=RiskScoreOut.model_validate(risk) if risk else None,
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}/timeline  – Chronological activity timeline
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/timeline", response_model=List[TimelineEvent])
def get_user_timeline(
    user_id: str,
    days: int = Query(60, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Return a chronological list of notable events for a user:
    - Login activity (aggregated daily)
    - USB device usage
    - File copy spikes
    - Email anomalies
    - All alerts
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    since = datetime.date.today() - datetime.timedelta(days=days)

    events: List[TimelineEvent] = []

    # ── Daily feature events ────────────────────────────────────────────────
    features = (
        db.query(DailyFeature)
        .filter(DailyFeature.user_id == user_id, DailyFeature.date >= since)
        .order_by(DailyFeature.date)
        .all()
    )
    for f in features:
        if f.login_count > 0:
            events.append(TimelineEvent(
                event_date=f.date,
                event_type="LOGIN",
                description=(
                    f"{int(f.login_count)} login(s) | "
                    f"{int(f.after_hours_login_count)} after-hours | "
                    f"{int(f.unique_pcs)} unique PC(s)"
                ),
                severity=None,
                risk_score=None,
            ))
        if f.usb_connect_count > 0:
            events.append(TimelineEvent(
                event_date=f.date,
                event_type="USB",
                description=f"USB device connected {int(f.usb_connect_count)} time(s)",
                severity="MEDIUM" if f.usb_connect_count >= 2 else None,
                risk_score=None,
            ))
        if f.file_copy_count >= 50:
            events.append(TimelineEvent(
                event_date=f.date,
                event_type="FILE_COPY",
                description=(
                    f"High file copy volume: {int(f.file_copy_count)} files | "
                    f"exfil_indicator={f.exfil_indicator:.2f}"
                ),
                severity="HIGH" if f.file_copy_count >= 200 else "MEDIUM",
                risk_score=None,
            ))
        if f.external_email_ratio >= 0.5 and f.email_sent_count > 0:
            events.append(TimelineEvent(
                event_date=f.date,
                event_type="EMAIL",
                description=(
                    f"High external email ratio: {f.external_email_ratio:.0%} "
                    f"({int(f.email_sent_count)} emails sent, "
                    f"{int(f.suspicious_attachment_count)} suspicious attachments)"
                ),
                severity="MEDIUM",
                risk_score=None,
            ))

    # ── Alert events ────────────────────────────────────────────────────────
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == user_id, Alert.date >= since)
        .order_by(Alert.date)
        .all()
    )
    for a in alerts:
        events.append(TimelineEvent(
            event_date=a.date,
            event_type="ALERT",
            description=f"[{a.status}] {a.alert_type} — risk_score={a.risk_score:.3f}",
            severity=a.severity,
            risk_score=a.risk_score,
        ))

    # Sort chronologically; alerts last within same day (highest severity impact)
    events.sort(key=lambda e: (e.event_date, 0 if e.event_type != "ALERT" else 1))
    return events


# ---------------------------------------------------------------------------
# GET /users/{user_id}/evidence  – Aggregated risk evidence summary
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/evidence", response_model=EvidenceSummary)
def get_user_evidence(
    user_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Return an aggregated evidence snapshot for the investigated user:
    - Alert counts and status breakdown
    - Peak risk score and date
    - 30-day average risk score
    - Top contributing risk factors (from SHAP if available)
    - Alert type distribution
    - Latest behavioral features
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    all_alerts: List[Alert] = (
        db.query(Alert)
        .filter(Alert.user_id == user_id)
        .order_by(Alert.risk_score.desc())
        .all()
    )

    open_alerts = [a for a in all_alerts if a.status == "OPEN"]

    # Peak risk
    peak_alert = all_alerts[0] if all_alerts else None
    peak_risk_score = peak_alert.risk_score if peak_alert else 0.0
    peak_risk_date  = peak_alert.date if peak_alert else None

    # 30-day average from risk_scores table
    since_30d = datetime.date.today() - datetime.timedelta(days=30)
    risk_30d = (
        db.query(RiskScore)
        .filter(RiskScore.user_id == user_id, RiskScore.date >= since_30d)
        .all()
    )
    avg_30d = (
        sum(r.risk_score for r in risk_30d) / len(risk_30d) if risk_30d else 0.0
    )

    # Top risk factors — extract from SHAP JSON where available
    shap_counter: Counter = Counter()
    for a in all_alerts:
        if a.shap_json and isinstance(a.shap_json, list):
            for entry in a.shap_json:
                feature = entry.get("feature") or entry.get("friendly_name", "")
                if feature:
                    shap_counter[feature] += 1
    top_risk_factors = [f for f, _ in shap_counter.most_common(5)]

    # Fallback: infer risk factors from latest features
    if not top_risk_factors:
        latest_feat: Optional[DailyFeature] = (
            db.query(DailyFeature)
            .filter(DailyFeature.user_id == user_id)
            .order_by(DailyFeature.date.desc())
            .first()
        )
        if latest_feat:
            factor_map = {
                "after_hours_login_count": "After-hours logins",
                "usb_connect_count":       "USB device usage",
                "file_copy_count":         "High file copy volume",
                "external_email_ratio":    "External email ratio",
                "file_sharing_visit_count":"File sharing site visits",
                "unique_pcs":              "Multiple PC access",
            }
            for attr, label in factor_map.items():
                val = getattr(latest_feat, attr, 0) or 0
                if val > 0:
                    top_risk_factors.append(label)
                if len(top_risk_factors) >= 5:
                    break

    # Alert type distribution
    type_breakdown = {}
    for a in all_alerts:
        type_breakdown[a.alert_type] = type_breakdown.get(a.alert_type, 0) + 1

    # Latest features
    latest_features_orm: Optional[DailyFeature] = (
        db.query(DailyFeature)
        .filter(DailyFeature.user_id == user_id)
        .order_by(DailyFeature.date.desc())
        .first()
    )
    latest_features_out = (
        DailyFeatureOut.model_validate(latest_features_orm)
        if latest_features_orm
        else None
    )

    return EvidenceSummary(
        user_id=user_id,
        total_alerts=len(all_alerts),
        open_alerts=len(open_alerts),
        peak_risk_score=round(peak_risk_score, 4),
        peak_risk_date=peak_risk_date,
        avg_risk_score_30d=round(avg_30d, 4),
        top_risk_factors=top_risk_factors,
        alert_type_breakdown=type_breakdown,
        latest_features=latest_features_out,
    )


# ---------------------------------------------------------------------------
# POST /alerts/{alert_id}/notes  – Append analyst note
# ---------------------------------------------------------------------------

@router.post("/alerts/{alert_id}/notes", response_model=AlertOut)
def add_investigation_note(
    alert_id: int,
    note: str = Body(..., embed=True, description="Analyst note text to append"),
    analyst: str = Body("analyst", embed=True, description="Analyst identifier or email"),
    db: Session = Depends(get_db),
    auth_user=Depends(get_current_auth_user),
):
    """
    Append a timestamped analyst note to an alert's notes field.
    Notes are stored as newline-separated entries with timestamp and analyst prefix.
    """
    alert: Optional[Alert] = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    analyst_id = getattr(auth_user, "email", analyst)
    timestamp  = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    new_note   = f"[{timestamp}] {analyst_id}: {note.strip()}"

    alert.notes = (alert.notes + "\n" + new_note) if alert.notes else new_note
    # Automatically move to INVESTIGATING if still OPEN
    if alert.status == "OPEN":
        alert.status = "INVESTIGATING"

    db.commit()
    db.refresh(alert)
    logger.info(f"Note added to alert {alert_id} by {analyst_id}")
    return alert


# ---------------------------------------------------------------------------
# PATCH /alerts/{alert_id}/status  – Update alert status
# ---------------------------------------------------------------------------

VALID_STATUSES = {"OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"}


@router.patch("/alerts/{alert_id}/status", response_model=AlertOut)
def update_alert_status(
    alert_id: int,
    status: str = Body(..., embed=True, description="OPEN|INVESTIGATING|RESOLVED|FALSE_POSITIVE"),
    reason: Optional[str] = Body(None, embed=True, description="Optional reason for status change"),
    db: Session = Depends(get_db),
    auth_user=Depends(get_current_auth_user),
):
    """
    Update the investigation status of an alert.
    Optionally records the reason as an appended note.
    """
    status_upper = status.upper()
    if status_upper not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}",
        )

    alert: Optional[Alert] = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    old_status = alert.status
    alert.status = status_upper

    # Append status change as a note
    analyst_id = getattr(auth_user, "email", "system")
    timestamp  = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    change_note = f"[{timestamp}] {analyst_id}: Status changed {old_status} → {status_upper}"
    if reason:
        change_note += f" — Reason: {reason.strip()}"
    alert.notes = (alert.notes + "\n" + change_note) if alert.notes else change_note

    db.commit()
    db.refresh(alert)
    logger.info(f"Alert {alert_id} status updated: {old_status} → {status_upper}")
    return alert
