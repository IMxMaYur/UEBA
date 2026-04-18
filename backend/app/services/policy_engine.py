"""
policy_engine.py — Security Policy Evaluation Engine
=====================================================
Evaluates incoming telemetry events against the active policies.
Returns violation status and appropriate warning level.
"""

import logging
from sqlalchemy.orm import Session
from app.models.orm_models import Policy, EmployeeSession

logger = logging.getLogger(__name__)

# Events that are always flagged (no policy needed)
ALWAYS_FLAG_EVENTS = {
    "USB_INSERTED": {"severity": "HIGH", "message": "USB device connected to workstation"},
}

# Events that are informational (never flagged alone)
INFO_EVENTS = {"FILE_MODIFIED", "HEARTBEAT", "LOGIN", "LOGOUT", "USB_REMOVED"}


def evaluate_event(db: Session, employee_id: str, event_type: str, details: dict) -> dict:
    """
    Evaluate an event against active policies.
    
    Returns:
        {
            "violation": True/False,
            "warning_level": 1/2/3,
            "warning_count": int,
            "warning_message": str,
            "action": "warn" / "restrict" / None
        }
    """
    result = {
        "violation": False,
        "warning_level": 0,
        "warning_count": 0,
        "warning_message": "",
        "action": None,
    }

    # Skip info-only events
    if event_type in INFO_EVENTS:
        return result

    # Check always-flag events
    if event_type in ALWAYS_FLAG_EVENTS:
        flag_info = ALWAYS_FLAG_EVENTS[event_type]
        result["violation"] = True
        result["warning_message"] = flag_info["message"]
        # Increment warning count
        session = _get_or_create_session(db, employee_id)
        session.warning_count += 1
        result["warning_count"] = session.warning_count
        result["warning_level"] = min(session.warning_count, 3)
        result["action"] = "restrict" if session.warning_count >= 3 else "warn"
        if session.warning_count >= 3:
            session.is_restricted = True
            session.status = "RESTRICTED"
        db.commit()
        return result

    # Check event-specific policies
    violation_msg = None

    if event_type == "RESTRICTED_WEBSITE":
        domain = details.get("domain", "")
        violation_reason = details.get("violation_reason", "")
        violation_msg = f"Accessed restricted website: {domain}. {violation_reason}"

    elif event_type == "BLOCKED_PROCESS":
        proc_name = details.get("process_name", "Unknown")
        violation_msg = f"Launched blocked application: {proc_name}"

    elif event_type == "FILE_DELETED":
        fname = details.get("file_name", "Unknown")
        violation_msg = f"Deleted file: {fname}. File deletions are monitored."

    elif event_type == "FILE_CREATED":
        # Check if file was created on a USB drive
        monitored_folder = details.get("monitored_folder", "")
        fname = details.get("file_name", "")
        # Check if it looks like a copy to USB (monitored folder is a drive root like E:\)
        if len(monitored_folder) <= 3 and ":" in monitored_folder:
            violation_msg = f"File copied to USB drive ({monitored_folder}): {fname}"

    elif event_type == "FILE_MOVED":
        dest = details.get("dest_path", "")
        fname = details.get("file_name", "")
        # Check if moved to a USB drive
        if len(dest) > 2 and dest[1] == ':':
            # Check if destination drive is a removable drive (simple heuristic)
            drive_letter = dest[0].upper()
            if drive_letter not in ('C', 'D'):  # Likely external drive
                violation_msg = f"File moved to external drive ({drive_letter}:): {fname}"

    if violation_msg:
        result["violation"] = True
        result["warning_message"] = violation_msg
        session = _get_or_create_session(db, employee_id)
        session.warning_count += 1
        result["warning_count"] = session.warning_count
        result["warning_level"] = min(session.warning_count, 3)
        result["action"] = "restrict" if session.warning_count >= 3 else "warn"
        if session.warning_count >= 3:
            session.is_restricted = True
            session.status = "RESTRICTED"
        db.commit()

    return result


def _get_or_create_session(db: Session, employee_id: str) -> EmployeeSession:
    """Get or create an employee session record."""
    import datetime
    session = db.query(EmployeeSession).filter(
        EmployeeSession.employee_id == employee_id
    ).first()
    if not session:
        session = EmployeeSession(
            employee_id=employee_id,
            status="ONLINE",
            warning_count=0,
            connected_at=datetime.datetime.utcnow(),
            last_heartbeat=datetime.datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def reset_warnings(db: Session, employee_id: str):
    """Admin resets the warning count for an employee."""
    session = _get_or_create_session(db, employee_id)
    session.warning_count = 0
    session.is_restricted = False
    session.status = "ONLINE"
    db.commit()
    logger.info(f"Warnings reset for {employee_id}")
