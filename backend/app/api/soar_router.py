"""
soar_router.py
--------------
SOAR (Security Orchestration, Automation and Response) API endpoints.
Allows analysts to view automated playbook actions per alert and
manually trigger a playbook re-execution.

Prefix: /api/soar
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import Alert, PlaybookAction
from app.services.dependencies import get_current_auth_user
from app.services.soar_engine import execute_playbook, get_tier_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/soar", tags=["soar"])


# ── Schema ── (inline for simplicity)
from pydantic import BaseModel
import datetime


class PlaybookActionOut(BaseModel):
    id: int
    alert_id: int
    user_id: str
    tier: int
    action_name: str
    description: Optional[str]
    executed_at: datetime.datetime
    risk_score_at_trigger: Optional[float]

    class Config:
        from_attributes = True


class PlaybookResult(BaseModel):
    tier: int
    action: str
    description: str
    executed_at: str
    risk_score: float


@router.get("/alerts/{alert_id}/actions", response_model=List[PlaybookActionOut])
def get_playbook_actions(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """Return all SOAR actions taken for a given alert."""
    actions = (
        db.query(PlaybookAction)
        .filter(PlaybookAction.alert_id == alert_id)
        .order_by(PlaybookAction.executed_at)
        .all()
    )
    return actions


@router.post("/alerts/{alert_id}/execute", response_model=PlaybookResult)
def manual_execute_playbook(
    alert_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Manually trigger the SOAR playbook for an alert.
    Useful for re-escalating or demonstrating response automation.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    result = execute_playbook(alert, db)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"Risk score {alert.risk_score:.3f} is below automated response threshold (0.60)"
        )

    db.commit()
    logger.info(f"Manual SOAR playbook executed for alert {alert_id}")
    return result


@router.get("/tier-info")
def get_tier_information(risk_score: float = 0.75):
    """Return tier metadata for a given risk score (for UI display)."""
    return get_tier_info(risk_score)
