"""
seed_router.py – Admin-only endpoints to seed CERT dataset users and reset the database.
- POST /api/seed/users    → reads psychometric.csv as primary source with OCEAN values
- POST /api/seed/reset    → clears all alerts, risk_scores, daily_features, and simulated users
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import User, Alert, RiskScore, DailyFeature
from app.services.dependencies import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seed", tags=["seed"])

# Dataset directory is at <project_root>/Dataset/
DATASET_DIR = Path(__file__).resolve().parents[3] / "Dataset"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_int(val, default=None):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ─── Seed Users ───────────────────────────────────────────────────────────────

def _do_seed(db: Session) -> dict:
    """
    Read psychometric.csv (primary source – has employee_name, user_id, O, C, E, A, N)
    and optionally logon.csv for any extra user IDs not in psychometric.csv.
    Upserts all CERT employees with their OCEAN personality scores.
    """
    import pandas as pd

    psych_csv = DATASET_DIR / "psychometric.csv"
    logon_csv = DATASET_DIR / "logon.csv"

    if not psych_csv.exists():
        raise FileNotFoundError(f"psychometric.csv not found at {psych_csv}")

    # --- Primary source: psychometric.csv ---
    logger.info("Reading psychometric.csv …")
    psych_df = pd.read_csv(psych_csv, dtype=str)

    # Expected columns: employee_name, user_id, O, C, E, A, N
    required = {"employee_name", "user_id", "O", "C", "E", "A", "N"}
    if not required.issubset(set(psych_df.columns)):
        raise ValueError(f"psychometric.csv missing columns. Got: {list(psych_df.columns)}")

    created = 0
    updated = 0

    for _, row in psych_df.iterrows():
        uid = str(row.get("user_id", "")).strip()
        if not uid:
            continue

        ocean = {
            "ocean_o": _safe_int(row.get("O")),
            "ocean_c": _safe_int(row.get("C")),
            "ocean_e": _safe_int(row.get("E")),
            "ocean_a": _safe_int(row.get("A")),
            "ocean_n": _safe_int(row.get("N")),
        }
        name = str(row.get("employee_name", "")).strip() or None

        existing = db.query(User).filter(User.id == uid).first()
        if existing:
            # Always update name and OCEAN from psychometric (it's the authoritative source)
            existing.name = name
            existing.department = existing.department or "CERT Dataset"
            existing.ocean_o = ocean["ocean_o"]
            existing.ocean_c = ocean["ocean_c"]
            existing.ocean_e = ocean["ocean_e"]
            existing.ocean_a = ocean["ocean_a"]
            existing.ocean_n = ocean["ocean_n"]
            updated += 1
        else:
            db.add(User(
                id=uid,
                name=name,
                department="CERT Dataset",
                role=None,
                is_active=True,
                latest_risk_score=0.0,
                **ocean,
            ))
            created += 1

    # --- Secondary source: logon.csv (any extra IDs not in psychometric) ---
    if logon_csv.exists():
        logger.info("Reading logon.csv for supplementary user IDs …")
        logon_df = pd.read_csv(logon_csv, usecols=["user"], dtype={"user": str}, low_memory=True)
        extra_ids = set(logon_df["user"].dropna().unique()) - set(psych_df["user_id"].dropna())
        for uid in extra_ids:
            uid = str(uid).strip()
            if not uid:
                continue
            if not db.query(User).filter(User.id == uid).first():
                db.add(User(
                    id=uid,
                    name=None,
                    department="CERT Dataset",
                    role=None,
                    is_active=True,
                    latest_risk_score=0.0,
                ))
                created += 1

    db.commit()
    total = db.query(User).count()
    logger.info(f"Seed complete: {created} created, {updated} updated. Total users: {total}")
    return {
        "message": f"✅ Seeded {created} new users, enriched {updated} with OCEAN data. Total in registry: {total}.",
        "total_users": total,
        "created": created,
        "updated": updated,
    }


@router.post("/users")
def seed_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Admin-only: reads psychometric.csv and upserts all CERT employees with OCEAN scores."""
    try:
        return _do_seed(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Seed failed")
        raise HTTPException(status_code=500, detail=f"Seed failed: {exc}")


# ─── Reset (Fresh Start) ───────────────────────────────────────────────────────

@router.post("/reset")
def reset_operational_data(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Admin-only: clears all operational/simulated data for a fresh start.
    Deletes: alerts, risk_scores, daily_features, and all users whose ID starts
    with 'SIM_' (simulated users). Resets latest_risk_score to 0 for all remaining users.
    Preserves: user registry (CERT employees with OCEAN data), auth users.
    """
    try:
        # Delete all alerts
        n_alerts = db.query(Alert).delete()

        # Delete all risk scores
        n_scores = db.query(RiskScore).delete()

        # Delete all daily features
        n_features = db.query(DailyFeature).delete()

        # Delete simulated users (those whose ID starts with 'SIM_')
        n_sim = db.query(User).filter(User.id.like("SIM_%")).delete(synchronize_session="fetch")

        # Reset all remaining users' risk score to 0
        db.query(User).update({"latest_risk_score": 0.0})

        db.commit()

        logger.info(
            f"Reset complete: {n_alerts} alerts, {n_scores} risk scores, "
            f"{n_features} daily features, {n_sim} simulated users deleted."
        )
        return {
            "message": f"✅ Fresh start complete! Cleared {n_alerts} alerts, {n_scores} risk scores, {n_features} daily features, {n_sim} simulated users.",
            "alerts_deleted": n_alerts,
            "risk_scores_deleted": n_scores,
            "daily_features_deleted": n_features,
            "simulated_users_deleted": n_sim,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("Reset failed")
        raise HTTPException(status_code=500, detail=f"Reset failed: {exc}")
