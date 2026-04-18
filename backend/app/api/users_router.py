"""
users_router.py – User list, user behavior timeline.
"""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import User, DailyFeature, RiskScore, Alert
from app.schemas.schemas import UserOut, UserBehaviorResponse, DailyFeatureOut, RiskScoreOut, AlertOut, UserUpdateRequest
from app.services.dependencies import get_current_auth_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(
    limit: int = Query(1000, le=10000),
    offset: int = 0,
    min_risk: float = 0.0,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    q = db.query(User).filter(User.latest_risk_score >= min_risk)
    q = q.order_by(User.latest_risk_score.desc()).offset(offset).limit(limit)
    return q.all()


@router.get("/{user_id}", response_model=UserBehaviorResponse)
def get_user_behavior(
    user_id: str,
    days: int = Query(90, le=365),
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    features = (
        db.query(DailyFeature)
        .filter(DailyFeature.user_id == user_id)
        .order_by(DailyFeature.date.desc())
        .limit(days)
        .all()
    )
    risk_scores = (
        db.query(RiskScore)
        .filter(RiskScore.user_id == user_id)
        .order_by(RiskScore.date.desc())
        .limit(days)
        .all()
    )
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == user_id)
        .order_by(Alert.date.desc())
        .all()
    )

    # Build baseline dict (mean ± std over all days)
    if features:
        feat_names = ["login_count", "usb_connect_count", "file_copy_count",
                      "email_sent_count", "http_request_count", "exfil_indicator"]
        import statistics
        baseline = {}
        for fn in feat_names:
            vals = [getattr(f, fn) for f in features]
            baseline[fn] = {"mean": round(sum(vals)/len(vals), 3), "std": round(statistics.pstdev(vals), 3)}
    else:
        baseline = {}

    return UserBehaviorResponse(
        user=user,
        features_timeline=features,
        risk_timeline=risk_scores,
        alerts=alerts,
        baseline=baseline,
    )


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Update mutable fields on a user record (name, department, role, is_active).
    Useful for tagging simulated users or enriching profiles after investigation.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.name is not None:
        user.name = req.name
    if req.department is not None:
        user.department = req.department
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active

    db.commit()
    db.refresh(user)
    return user
