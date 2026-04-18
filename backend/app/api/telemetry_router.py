"""
telemetry_router.py — Live Telemetry Ingestion from Endpoint Agent
===================================================================
Receives real-time events (USB, file, browser, process) from the agent,
evaluates them against active policies, stores in DB, and broadcasts
to connected admin dashboards via WebSocket.

Prefix: /api/telemetry
"""

import datetime
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import ActivityEvent, EmployeeSession
from app.services.policy_engine import evaluate_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

# ── In-memory store for WebSocket broadcast ─────────────────────────────────
# Connected admin dashboard websocket handlers will read from here
_live_event_subscribers = []


def subscribe_live(callback):
    """Register a callback to receive live events (for WebSocket broadcast)."""
    _live_event_subscribers.append(callback)


def unsubscribe_live(callback):
    _live_event_subscribers.remove(callback)


def _broadcast(event_data):
    """Send event to all connected admin dashboards."""
    for cb in _live_event_subscribers[:]:
        try:
            cb(event_data)
        except Exception:
            _live_event_subscribers.remove(cb)


# ── POST /events — Receive telemetry from agent ────────────────────────────

@router.post("/events")
def receive_event(payload: dict, db: Session = Depends(get_db)):
    """
    Receives a single telemetry event from the endpoint agent.
    Evaluates it against policies and returns violation status.
    """
    event_type = payload.get("event_type", "UNKNOWN")
    employee_id = payload.get("employee_id", "unknown")
    hostname = payload.get("hostname", "")
    details = payload.get("details", {})
    timestamp_str = payload.get("timestamp")

    try:
        timestamp = datetime.datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.datetime.utcnow()
    except (ValueError, TypeError):
        timestamp = datetime.datetime.utcnow()

    # Evaluate against policies
    policy_result = evaluate_event(db, employee_id, event_type, details)

    # Store the event
    event = ActivityEvent(
        employee_id=employee_id,
        hostname=hostname,
        event_type=event_type,
        details=details,
        is_violation=policy_result["violation"],
        warning_level=policy_result["warning_level"] if policy_result["violation"] else None,
        timestamp=timestamp,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Broadcast to admin dashboard
    broadcast_data = {
        "id": event.id,
        "type": "live_event",
        "event_type": event_type,
        "employee_id": employee_id,
        "hostname": hostname,
        "details": details,
        "is_violation": policy_result["violation"],
        "warning_level": policy_result["warning_level"],
        "warning_count": policy_result["warning_count"],
        "timestamp": timestamp.isoformat(),
    }
    _broadcast(broadcast_data)

    if policy_result["violation"]:
        logger.warning(
            f"⚠️  VIOLATION: {event_type} by {employee_id} "
            f"(warning #{policy_result['warning_count']}, level {policy_result['warning_level']})"
        )
    else:
        logger.info(f"📡 Event: {event_type} from {employee_id}")

    return policy_result


# ── POST /heartbeat — Agent heartbeat ──────────────────────────────────────

@router.post("/heartbeat")
def receive_heartbeat(payload: dict, db: Session = Depends(get_db)):
    """
    Receives periodic heartbeat from the endpoint agent.
    Updates the employee session status.
    """
    employee_id = payload.get("employee_id", "unknown")
    hostname = payload.get("hostname", "")
    os_info = payload.get("os", "")
    warning_count = payload.get("warning_count", 0)
    is_restricted = payload.get("is_restricted", False)

    # Upsert employee session
    session = db.query(EmployeeSession).filter(
        EmployeeSession.employee_id == employee_id
    ).first()

    if session:
        session.last_heartbeat = datetime.datetime.utcnow()
        session.hostname = hostname
        session.os_info = os_info
        session.warning_count = warning_count
        session.is_restricted = is_restricted
        if not is_restricted:
            session.status = "ONLINE"
    else:
        session = EmployeeSession(
            employee_id=employee_id,
            hostname=hostname,
            os_info=os_info,
            status="ONLINE",
            warning_count=warning_count,
            is_restricted=is_restricted,
            last_heartbeat=datetime.datetime.utcnow(),
            connected_at=datetime.datetime.utcnow(),
        )
        db.add(session)

    db.commit()

    # Broadcast status update
    _broadcast({
        "type": "heartbeat",
        "employee_id": employee_id,
        "status": session.status,
        "warning_count": warning_count,
        "is_restricted": is_restricted,
        "hostname": hostname,
    })

    return {"status": "ok"}


# ── GET /sessions — List all employee sessions ─────────────────────────────

@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    """List all employee sessions with online/offline status."""
    import datetime as dt

    sessions = db.query(EmployeeSession).all()
    result = []
    now = datetime.datetime.utcnow()

    for s in sessions:
        # Mark as offline if no heartbeat in 15 seconds
        if s.last_heartbeat and (now - s.last_heartbeat).total_seconds() > 15:
            if s.status == "ONLINE":
                s.status = "OFFLINE"
                db.commit()

        result.append({
            "employee_id": s.employee_id,
            "hostname": s.hostname,
            "os_info": s.os_info,
            "status": s.status,
            "warning_count": s.warning_count,
            "is_restricted": s.is_restricted,
            "last_heartbeat": s.last_heartbeat.isoformat() if s.last_heartbeat else None,
            "connected_at": s.connected_at.isoformat() if s.connected_at else None,
        })

    return result


# ── GET /events — Fetch recent events (for dashboard) ──────────────────────

@router.get("/events")
def list_events(
    employee_id: str = None,
    limit: int = 100,
    violations_only: bool = False,
    db: Session = Depends(get_db),
):
    """Fetch recent activity events, optionally filtered by employee and violations."""
    query = db.query(ActivityEvent).order_by(ActivityEvent.timestamp.desc())

    if employee_id:
        query = query.filter(ActivityEvent.employee_id == employee_id)
    if violations_only:
        query = query.filter(ActivityEvent.is_violation == True)

    events = query.limit(limit).all()

    return [
        {
            "id": e.id,
            "employee_id": e.employee_id,
            "hostname": e.hostname,
            "event_type": e.event_type,
            "details": e.details,
            "is_violation": e.is_violation,
            "warning_level": e.warning_level,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]


# ── POST /reset-warnings — Admin resets warnings for an employee ───────────

@router.post("/reset-warnings/{employee_id}")
def reset_employee_warnings(employee_id: str, db: Session = Depends(get_db)):
    """Admin resets the warning count and restriction status for an employee."""
    from app.services.policy_engine import reset_warnings
    reset_warnings(db, employee_id)

    _broadcast({
        "type": "warning_reset",
        "employee_id": employee_id,
    })

    return {"status": "ok", "message": f"Warnings reset for {employee_id}"}
