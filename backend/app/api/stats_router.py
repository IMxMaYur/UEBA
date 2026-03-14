"""
stats_router.py – Dashboard overview stats with Redis caching,
plus trend, leaderboard and model-metrics endpoints.
"""
import json
import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.orm_models import User, Alert, RiskScore
from app.schemas.schemas import (
    OverviewStats, DailyTrend, LeaderboardEntry, ModelMetrics,
)
from app.services.dependencies import get_current_auth_user
from app.config import settings

router = APIRouter(prefix="/api/stats", tags=["stats"])

# Path to the trained_models directory (backend/trained_models/)
MODELS_DIR = Path(__file__).resolve().parents[2] / "trained_models"

# Optional Redis caching
try:
    import redis as redis_lib
    _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
    _redis.ping()
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

CACHE_TTL = 300   # 5 minutes
CACHE_KEY  = "ueba:overview_stats"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _redis_get(key: str):
    return _redis.get(key) if REDIS_AVAILABLE else None


def _redis_set(key: str, value: str, ttl: int = CACHE_TTL):
    if REDIS_AVAILABLE:
        _redis.setex(key, ttl, value)


def _compute_stats(db: Session) -> OverviewStats:
    today = datetime.date.today()
    total_users     = db.query(func.count(User.id)).scalar() or 0
    high_risk       = db.query(func.count(User.id)).filter(
        User.latest_risk_score >= settings.risk_threshold).scalar() or 0
    open_alerts     = db.query(func.count(Alert.id)).filter(
        Alert.status == "OPEN").scalar() or 0
    critical_alerts = db.query(func.count(Alert.id)).filter(
        Alert.severity == "CRITICAL", Alert.status == "OPEN").scalar() or 0
    alerts_today    = db.query(func.count(Alert.id)).filter(
        Alert.date == today).scalar() or 0
    avg_risk = db.query(func.avg(User.latest_risk_score)).scalar() or 0.0

    return OverviewStats(
        total_users=total_users,
        high_risk_users=high_risk,
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        alerts_today=alerts_today,
        avg_risk_score=round(float(avg_risk), 4),
    )


# ---------------------------------------------------------------------------
# GET /overview  – 6 KPI numbers (cached)
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=OverviewStats)
def get_overview(
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    cached = _redis_get(CACHE_KEY)
    if cached:
        return OverviewStats(**json.loads(cached))
    stats = _compute_stats(db)
    _redis_set(CACHE_KEY, stats.model_dump_json())
    return stats


# ---------------------------------------------------------------------------
# GET /trends  – daily alert count + avg risk (for timeline chart)
# ---------------------------------------------------------------------------

@router.get("/trends", response_model=List[DailyTrend])
def get_trends(
    days: int = Query(30, ge=7, le=180, description="Number of days to look back"),
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """
    Returns one DailyTrend entry per calendar day for the last `days` days.
    Days with no alerts still appear (alert_count=0, avg_risk_score=0.0) so
    the frontend chart always has a continuous x-axis.
    """
    since = datetime.date.today() - datetime.timedelta(days=days)

    rows = (
        db.query(
            Alert.date,
            func.count(Alert.id).label("alert_count"),
            func.avg(Alert.risk_score).label("avg_risk"),
        )
        .filter(Alert.date >= since)
        .group_by(Alert.date)
        .order_by(Alert.date)
        .all()
    )

    trend_map = {
        row.date: DailyTrend(
            date=row.date,
            alert_count=int(row.alert_count),
            avg_risk_score=round(float(row.avg_risk or 0), 4),
        )
        for row in rows
    }

    result = []
    for i in range(days + 1):
        d = since + datetime.timedelta(days=i)
        result.append(trend_map.get(d, DailyTrend(date=d, alert_count=0, avg_risk_score=0.0)))

    return result


# ---------------------------------------------------------------------------
# GET /leaderboard  – top N users by risk score
# ---------------------------------------------------------------------------

@router.get("/leaderboard", response_model=List[LeaderboardEntry])
def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_auth_user),
):
    """Top users ranked by latest_risk_score, enriched with open + total alert counts."""
    top_users = (
        db.query(User)
        .order_by(User.latest_risk_score.desc())
        .limit(limit)
        .all()
    )

    result = []
    for user in top_users:
        open_count  = db.query(func.count(Alert.id)).filter(
            Alert.user_id == user.id, Alert.status == "OPEN").scalar() or 0
        total_count = db.query(func.count(Alert.id)).filter(
            Alert.user_id == user.id).scalar() or 0
        result.append(LeaderboardEntry(
            user_id=user.id,
            name=user.name,
            department=user.department,
            risk_score=round(float(user.latest_risk_score), 4),
            open_alerts=int(open_count),
            total_alerts=int(total_count),
        ))

    return result


# ---------------------------------------------------------------------------
# GET /model-metrics  – last pipeline evaluation results
# ---------------------------------------------------------------------------

@router.get("/model-metrics", response_model=ModelMetrics)
def get_model_metrics(_=Depends(get_current_auth_user)):
    """
    Returns evaluation metrics saved by run_pipeline.py into
    trained_models/metrics.json.  Returns zeros/null if not yet run.
    """
    metrics_path = MODELS_DIR / "metrics.json"
    if not metrics_path.exists():
        return ModelMetrics(
            roc_auc=0.0, average_precision=0.0,
            precision=0.0, recall=0.0, f1_score=0.0,
            threshold=settings.risk_threshold,
            n_alerts=0, n_true_positives=0,
            n_false_positives=0, n_false_negatives=0,
            last_trained=None,
        )
    data = json.loads(metrics_path.read_text())
    return ModelMetrics(**data)
