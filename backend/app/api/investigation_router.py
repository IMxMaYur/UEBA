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

VALID_STATUSES = {"OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE", "CONFIRMED_THREAT", "BENIGN_MISTAKE"}


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

    # ── False-Positive Feedback Loop ──────────────────────────────────────
    # Tag the feature vector row so next pipeline retraining excludes it.
    if status_upper == "FALSE_POSITIVE":
        daily = (
            db.query(DailyFeature)
            .filter(
                DailyFeature.user_id == alert.user_id,
                DailyFeature.date == alert.date,
            )
            .first()
        )
        if daily:
            daily.is_false_positive = True
            logger.info(
                f"Feedback loop: marked DailyFeature (user={alert.user_id}, "
                f"date={alert.date}) as false positive for future retraining."
            )

    db.commit()
    db.refresh(alert)
    logger.info(f"Alert {alert_id} status updated: {old_status} → {status_upper}")
    return alert



# ---------------------------------------------------------------------------
# GET /alerts/{alert_id}/report.pdf  – Export PDF forensic incident report
# ---------------------------------------------------------------------------

@router.get("/alerts/{alert_id}/report.pdf")
def export_pdf_report(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Generate a professional PDF incident report for an alert.
    Includes: alert metadata, user profile, SHAP explanation,
    AI narrative, model scores, and analyst notes.
    """
    from fastapi.responses import Response
    import io

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    user = db.query(User).filter(User.id == alert.user_id).first()
    risk_score_row = (
        db.query(RiskScore)
        .filter(RiskScore.user_id == alert.user_id, RiskScore.date == alert.date)
        .first()
    )

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PDF generation unavailable. Install reportlab: pip install reportlab"
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Title'],
                                  fontSize=20, textColor=colors.HexColor('#1e3a5f'),
                                  spaceAfter=6, fontName='Helvetica-Bold')
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'],
                               fontSize=13, textColor=colors.HexColor('#2563eb'),
                               spaceBefore=14, spaceAfter=4, fontName='Helvetica-Bold')
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'],
                                 fontSize=10, leading=14, textColor=colors.HexColor('#374151'))
    label_style = ParagraphStyle('LabelStyle', parent=styles['Normal'],
                                  fontSize=9, textColor=colors.HexColor('#6b7280'),
                                  fontName='Helvetica')
    critical_style = ParagraphStyle('CriticalStyle', parent=styles['Normal'],
                                     fontSize=10, textColor=colors.HexColor('#dc2626'),
                                     fontName='Helvetica-Bold')

    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    sev = alert.severity.upper()
    sev_color = ({'CRITICAL': '#dc2626', 'HIGH': '#d97706', 'MEDIUM': '#3b82f6', 'LOW': '#10b981'}
                 .get(sev, '#374151'))

    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("UEBA INSIDER THREAT DETECTION PLATFORM", title_style))
    story.append(Paragraph("Forensic Incident Report  ·  CONFIDENTIAL", label_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#2563eb')))
    story.append(Spacer(1, 12))

    # ── Alert ID badge  ───────────────────────────────────────────────────────
    badge_data = [[
        f"ALERT #{alert.id}",
        f"TYPE: {alert.alert_type.replace('_', ' ')}",
        f"SEVERITY: {sev}",
        f"STATUS: {alert.status}",
    ]]
    badge_table = Table(badge_data, colWidths=[3.5*cm, 5.5*cm, 4*cm, 4*cm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, 0), 8),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 16))

    # ── Alert Summary ─────────────────────────────────────────────────────────
    story.append(Paragraph("ALERT SUMMARY", h2_style))
    summary_data = [
        ["Report Generated", now_str],
        ["Alert Date", str(alert.date)],
        ["User ID", alert.user_id],
        ["User Name", (user.name or "—") if user else "—"],
        ["Department", (user.department or "—") if user else "—"],
        ["Risk Score", f"{(alert.risk_score or 0) * 100:.1f}%"],
        ["Alert Type", alert.alert_type.replace('_', ' ')],
        ["Severity", sev],
        ["Status", alert.status.replace('_', ' ')],
    ]
    sum_table = Table(summary_data, colWidths=[5*cm, 12*cm])
    sum_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#111827')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 4))

    # ── AI Narrative ──────────────────────────────────────────────────────────
    if alert.narrative:
        story.append(Paragraph("AI ANALYSIS NARRATIVE", h2_style))
        story.append(Paragraph(alert.narrative, body_style))
        story.append(Spacer(1, 4))

    # ── SHAP Explanation ──────────────────────────────────────────────────────
    if alert.shap_json:
        story.append(Paragraph("SHAP FEATURE IMPORTANCE", h2_style))
        shap_data = [["Feature", "Observed Value", "SHAP Impact", "Direction"]]
        for f in alert.shap_json:
            shap_data.append([
                f.get("friendly_name", f.get("feature", "")),
                str(round(float(f.get("value", 0)), 3)),
                str(round(abs(float(f.get("shap_value", 0))), 4)),
                "↑ Increases Risk" if f.get("direction") == "increases_risk" else "↓ Reduces Risk",
            ])
        shap_table = Table(shap_data, colWidths=[7*cm, 3.5*cm, 3.5*cm, 3*cm])
        shap_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(shap_table)
        story.append(Spacer(1, 4))

    # ── ML Model Scores ───────────────────────────────────────────────────────
    if risk_score_row:
        story.append(Paragraph("ML MODEL SCORE BREAKDOWN", h2_style))
        model_data = [["Model", "Score"]]
        for label, score in [
            ("Isolation Forest", risk_score_row.if_score),
            ("Autoencoder", risk_score_row.ae_score),
            ("LSTM", risk_score_row.lstm_score),
            ("GNN", risk_score_row.gnn_score),
            ("Rule-Based", risk_score_row.rule_score),
            ("Composite Risk Score", risk_score_row.risk_score),
        ]:
            model_data.append([label, f"{(score or 0) * 100:.1f}%"])
        model_table = Table(model_data, colWidths=[8*cm, 4*cm])
        model_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(model_table)
        story.append(Spacer(1, 4))

    # ── Analyst Notes ─────────────────────────────────────────────────────────
    if alert.notes:
        story.append(Paragraph("ANALYST NOTES & AUDIT TRAIL", h2_style))
        story.append(Paragraph(alert.notes.replace('\n', '<br/>'), body_style))
        story.append(Spacer(1, 4))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#d1d5db')))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by UEBA Insider Threat Detection Platform v2.0  ·  {now_str}  ·  CONFIDENTIAL",
        label_style,
    ))

    doc.build(story)
    buffer.seek(0)
    pdf_bytes = buffer.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ueba_alert_{alert_id}_report.pdf",
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# GET /graph  – Knowledge Graph entity-relationship data
# ---------------------------------------------------------------------------

@router.get("/graph")
def get_knowledge_graph(
    user_id: Optional[str] = None,
    alert_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Build an entity-relationship graph for a user or alert.
    Returns nodes (User, PC, USB, ExternalEmail, IP) and edges for
    visualization in the KnowledgeGraphPage.
    """
    # Resolve user from alert if alert_id provided
    if alert_id and not user_id:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert:
            user_id = alert.user_id

    if not user_id:
        raise HTTPException(status_code=400, detail="Provide user_id or alert_id")

    user: Optional[User] = db.query(User).filter(User.id == user_id).first()
    risk_score = user.latest_risk_score if user else 0.0
    user_name  = user.name if user else user_id

    # Aggregate DailyFeature records for this user
    features = (
        db.query(DailyFeature)
        .filter(DailyFeature.user_id == user_id)
        .order_by(DailyFeature.date.desc())
        .limit(30)
        .all()
    )

    # Build synthetic PC list from unique_pcs count
    max_pcs = int(max((f.unique_pcs or 0) for f in features)) if features else 1
    pcs = [{"id": f"PC-{user_id}-{i+1}", "logon_count": 1} for i in range(min(max_pcs, 8))]

    # USB: from usb_connect_count
    total_usb = int(sum((f.usb_connect_count or 0) for f in features))
    usb_devices = [f"USB-{i+1}" for i in range(min(total_usb, 5))]

    # External emails: from external_email_ratio
    avg_ext = (sum((f.external_email_ratio or 0) for f in features) / max(len(features), 1))
    # Generate synthetic external email domains based on ratio
    ext_email_count = min(int(avg_ext * 10), 6)
    domains = ["gmail.com", "yahoo.com", "protonmail.com", "outlook.com", "tutanota.com", "dropbox.com"]
    external_emails = [f"{user_id.lower()}@{domains[i % len(domains)]}" for i in range(ext_email_count)]

    # External IPs from augmented logon data (brute force / impossible travel flags)
    external_ips = []
    # Check alert notes for geo details
    alerts = db.query(Alert).filter(Alert.user_id == user_id).all()
    for a in alerts:
        if a.geo_details:
            ip = a.geo_details.get("city_b", "")
            if ip:
                external_ips.append(f"IP:{ip}")

    return {
        "user_id":       user_id,
        "user_name":     user_name,
        "risk_score":    round(risk_score, 3),
        "pcs":           pcs,
        "usb_devices":   usb_devices,
        "external_emails": external_emails,
        "external_ips":  external_ips[:4],
        "summary": {
            "total_days_analyzed": len(features),
            "max_pcs_accessed":    max_pcs,
            "total_usb_events":    total_usb,
            "avg_external_email_ratio": round(avg_ext, 3),
        }
    }

