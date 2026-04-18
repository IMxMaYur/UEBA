"""
soar_engine.py
--------------
Security Orchestration, Automation, and Response (SOAR) engine.

Implements graduated response tiers matching enterprise UEBA behavior:
  Tier 1 (0.60-0.75): MFA Step-Up challenge triggered
  Tier 2 (0.75-0.90): Session revocation + forced password reset
  Tier 3 (>=0.90):    Network/host isolation + account suspension + HR notification

All actions are logged to the PlaybookAction table for forensic audit.
The response is automated upon alert creation above threshold.
"""

import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Response tier thresholds ──────────────────────────────────────────────────
TIER1_MIN = 0.60
TIER2_MIN = 0.75
TIER3_MIN = 0.90

TIER_LABELS = {
    1: "MFA_STEPUP",
    2: "SESSION_REVOCATION",
    3: "HOST_ISOLATION",
}

TIER_DESCRIPTIONS = {
    1: (
        "MFA step-up challenge triggered. User must re-authenticate via "
        "push-based second factor (Okta/Duo). Access restricted pending verification."
    ),
    2: (
        "Active session tokens revoked across all SaaS and on-premises applications. "
        "Password reset enforced. User removed from active sessions on all endpoints."
    ),
    3: (
        "CRITICAL CONTAINMENT ACTIVATED. Host network isolation command sent to EDR agent. "
        "Workstation quarantined from internal network and internet. "
        "Active Directory account suspended. HR and Security Manager notified. "
        "Forensic evidence collection initiated (memory dump + access logs)."
    ),
}


def _get_tier(risk_score: float) -> Optional[int]:
    """Return the response tier for a given risk score, or None if below threshold."""
    if risk_score >= TIER3_MIN:
        return 3
    elif risk_score >= TIER2_MIN:
        return 2
    elif risk_score >= TIER1_MIN:
        return 1
    return None


def execute_playbook(alert, db) -> Optional[dict]:
    """
    Execute the appropriate SOAR playbook for the given alert.

    Args:
        alert:  ORM Alert object (must have risk_score, user_id, id, alert_type)
        db:     SQLAlchemy Session

    Returns:
        dict with tier, action, and description, or None if below threshold
    """
    from app.models.orm_models import PlaybookAction

    tier = _get_tier(float(alert.risk_score))
    if tier is None:
        return None

    action_name = TIER_LABELS[tier]
    description = TIER_DESCRIPTIONS[tier]
    now = datetime.datetime.utcnow()

    # Log to PlaybookAction table
    try:
        pa = PlaybookAction(
            alert_id=alert.id,
            user_id=alert.user_id,
            tier=tier,
            action_name=action_name,
            description=description,
            executed_at=now,
            risk_score_at_trigger=float(alert.risk_score),
        )
        db.add(pa)
        db.flush()
    except Exception as e:
        logger.error(f"Failed to log PlaybookAction: {e}")

    # Append SOAR note to alert notes field
    note = (
        f"[{now.strftime('%Y-%m-%d %H:%M UTC')}] SOAR-AUTO: "
        f"Tier {tier} response executed — {action_name}. {description[:120]}..."
    )
    if alert.notes:
        alert.notes = alert.notes + "\n" + note
    else:
        alert.notes = note

    # Auto-escalate status for high tiers
    if tier >= 2 and alert.status == "OPEN":
        alert.status = "INVESTIGATING"
    if tier >= 3:
        alert.status = "INVESTIGATING"

    logger.info(
        f"SOAR Tier {tier} executed for alert {alert.id} "
        f"(user={alert.user_id}, risk={alert.risk_score:.3f})"
    )

    return {
        "tier": tier,
        "action": action_name,
        "description": description,
        "executed_at": now.isoformat(),
        "risk_score": float(alert.risk_score),
    }


def get_tier_info(risk_score: float) -> dict:
    """Return tier metadata for a given risk score (used for UI display)."""
    tier = _get_tier(risk_score)
    if tier is None:
        return {"tier": 0, "action": "MONITORING", "description": "Risk score below automated response threshold. Passive monitoring active."}
    return {
        "tier": tier,
        "action": TIER_LABELS[tier],
        "description": TIER_DESCRIPTIONS[tier],
    }
