"""
policy_router.py — Security Policy Management CRUD
====================================================
Allows admins to create, read, update, and delete security policies
(restricted websites, blocked processes, etc.).

Prefix: /api/policies
"""

import datetime
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import Policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/policies", tags=["policies"])


# ── GET / — List all policies ──────────────────────────────────────────────

@router.get("")
def list_policies(
    policy_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all active security policies, optionally filtered by type."""
    query = db.query(Policy).filter(Policy.is_active == True)
    if policy_type:
        query = query.filter(Policy.policy_type == policy_type.upper())
    policies = query.order_by(Policy.created_at.desc()).all()

    return [
        {
            "id": p.id,
            "policy_type": p.policy_type,
            "value": p.value,
            "description": p.description,
            "severity": p.severity,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ]


# ── POST / — Create a new policy ──────────────────────────────────────────

@router.post("")
def create_policy(payload: dict, db: Session = Depends(get_db)):
    """
    Create a new security policy.
    Body: { policy_type, value, description?, severity? }
    """
    policy_type = payload.get("policy_type", "").upper().strip()
    value = payload.get("value", "").strip()
    description = payload.get("description", "")
    severity = payload.get("severity", "MEDIUM").upper()

    valid_types = {"RESTRICTED_WEBSITE", "RESTRICTED_KEYWORD", "BLOCKED_PROCESS", "MONITORED_FOLDER"}
    if policy_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy_type. Must be one of: {', '.join(valid_types)}"
        )
    if not value:
        raise HTTPException(status_code=400, detail="Policy value is required")

    # Check for duplicates
    existing = db.query(Policy).filter(
        Policy.policy_type == policy_type,
        Policy.value == value,
        Policy.is_active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Policy already exists: {policy_type} = {value}")

    policy = Policy(
        policy_type=policy_type,
        value=value,
        description=description,
        severity=severity,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    logger.info(f"Policy created: {policy_type} = {value}")

    return {
        "id": policy.id,
        "policy_type": policy.policy_type,
        "value": policy.value,
        "description": policy.description,
        "severity": policy.severity,
        "is_active": policy.is_active,
    }


# ── DELETE /{id} — Deactivate a policy ────────────────────────────────────

@router.delete("/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    """Deactivate (soft delete) a policy."""
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy.is_active = False
    db.commit()
    logger.info(f"Policy deactivated: {policy.policy_type} = {policy.value}")
    return {"status": "deleted", "id": policy_id}


# ── POST /seed — Seed default policies for demo ───────────────────────────

@router.post("/seed")
def seed_default_policies(db: Session = Depends(get_db)):
    """Seed the database with sensible default policies for the demo."""
    defaults = [
        # Restricted websites
        ("RESTRICTED_WEBSITE", "facebook.com", "Social media - not permitted during work hours", "MEDIUM"),
        ("RESTRICTED_WEBSITE", "instagram.com", "Social media - not permitted during work hours", "MEDIUM"),
        ("RESTRICTED_WEBSITE", "tiktok.com", "Social media - not permitted during work hours", "MEDIUM"),
        ("RESTRICTED_WEBSITE", "reddit.com", "Social media - not permitted during work hours", "MEDIUM"),
        ("RESTRICTED_WEBSITE", "twitter.com", "Social media - not permitted during work hours", "MEDIUM"),
        ("RESTRICTED_WEBSITE", "twitch.tv", "Streaming platform - not permitted", "MEDIUM"),
        ("RESTRICTED_WEBSITE", "bet365.com", "Gambling site - strictly prohibited", "HIGH"),
        ("RESTRICTED_WEBSITE", "torproject.org", "Tor browser - anonymization tool", "HIGH"),

        # Restricted keywords
        ("RESTRICTED_KEYWORD", "torrent", "File sharing / piracy keyword", "HIGH"),
        ("RESTRICTED_KEYWORD", "hack", "Hacking related keyword", "HIGH"),
        ("RESTRICTED_KEYWORD", "crack", "Software cracking keyword", "HIGH"),
        ("RESTRICTED_KEYWORD", "exploit", "Security exploit keyword", "HIGH"),
        ("RESTRICTED_KEYWORD", "darkweb", "Dark web related keyword", "HIGH"),

        # Blocked processes
        ("BLOCKED_PROCESS", "ftp.exe", "FTP client - unapproved file transfer", "HIGH"),
        ("BLOCKED_PROCESS", "torrent.exe", "Torrent client", "HIGH"),
        ("BLOCKED_PROCESS", "wireshark.exe", "Network sniffer - security tool", "HIGH"),
        ("BLOCKED_PROCESS", "nmap.exe", "Port scanner - security tool", "HIGH"),
    ]

    created = 0
    for ptype, value, desc, severity in defaults:
        existing = db.query(Policy).filter(
            Policy.policy_type == ptype,
            Policy.value == value,
        ).first()
        if not existing:
            db.add(Policy(policy_type=ptype, value=value, description=desc, severity=severity))
            created += 1

    db.commit()
    logger.info(f"Seeded {created} default policies")
    return {"status": "ok", "created": created, "total_defaults": len(defaults)}
