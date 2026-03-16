"""
alerts_router.py – Alert list, detail with SHAP, status updates.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.orm_models import Alert
from app.schemas.schemas import AlertOut, AlertUpdateRequest, BulkAlertUpdate, AlertSummaryItem
from app.services.dependencies import get_current_auth_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Statuses visible on dashboard (DISMISSED = hidden from normal views)
ACTIVE_STATUSES = ["OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"]


@router.get("", response_model=List[AlertOut])
def list_alerts(
    status: Optional[str] = Query(None, description="OPEN|INVESTIGATING|RESOLVED"),
    severity: Optional[str] = Query(None, description="LOW|MEDIUM|HIGH|CRITICAL"),
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status.upper())
    else:
        # By default exclude DISMISSED alerts (soft-deleted from dashboard view)
        q = q.filter(Alert.status != "DISMISSED")
    if severity:
        q = q.filter(Alert.severity == severity.upper())
    q = q.order_by(Alert.risk_score.desc(), Alert.created_at.desc())
    return q.offset(offset).limit(limit).all()



@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    req: AlertUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if req.status:
        alert.status = req.status.upper()
    if req.notes is not None:
        alert.notes = req.notes
    db.commit()
    db.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# PATCH /bulk  – Bulk status update
# ---------------------------------------------------------------------------

@router.patch("/bulk", response_model=List[AlertOut])
def bulk_update_alerts(
    req: BulkAlertUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Update status (and optionally append a note) for multiple alerts at once.
    Returns the list of updated alerts.
    """
    valid_statuses = {"OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"}
    status_upper = req.status.upper()
    if status_upper not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{req.status}'. Must be one of: {sorted(valid_statuses)}",
        )

    alerts = db.query(Alert).filter(Alert.id.in_(req.alert_ids)).all()
    if not alerts:
        raise HTTPException(status_code=404, detail="No matching alerts found")

    for alert in alerts:
        alert.status = status_upper
        if req.notes:
            alert.notes = (alert.notes + "\n" + req.notes) if alert.notes else req.notes

    db.commit()
    for alert in alerts:
        db.refresh(alert)
    return alerts


# ---------------------------------------------------------------------------
# GET /summary  – Count grouped by alert_type + severity + status
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=List[AlertSummaryItem])
def get_alert_summary(
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Returns alert counts grouped by (alert_type, severity, status).
    Useful for the dashboard summary cards and charts.
    """
    rows = (
        db.query(
            Alert.alert_type,
            Alert.severity,
            Alert.status,
            func.count(Alert.id).label("count"),
        )
        .group_by(Alert.alert_type, Alert.severity, Alert.status)
        .order_by(Alert.severity, Alert.alert_type)
        .all()
    )
    return [
        AlertSummaryItem(
            alert_type=row.alert_type,
            severity=row.severity,
            status=row.status,
            count=row.count,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# DELETE /{alert_id}  – Soft-dismiss: hides from dashboard, keeps in DB
# ---------------------------------------------------------------------------

@router.delete("/{alert_id}", status_code=204)
def dismiss_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Soft-dismiss an alert: sets status to DISMISSED so it's hidden from
    the dashboard view. The record is preserved in the database.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "DISMISSED"
    db.commit()


# ---------------------------------------------------------------------------
# DELETE /bulk/dismiss  – Bulk soft-dismiss
# ---------------------------------------------------------------------------

@router.delete("/bulk/dismiss", status_code=200)
def bulk_dismiss_alerts(
    alert_ids: list[int],
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """Soft-dismiss multiple alerts at once."""
    db.query(Alert).filter(Alert.id.in_(alert_ids)).update(
        {"status": "DISMISSED"}, synchronize_session="fetch"
    )
    db.commit()
    return {"dismissed": len(alert_ids)}
