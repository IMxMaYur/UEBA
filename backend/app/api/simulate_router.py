"""
simulate_router.py – Trigger one of 5 insider threat attack scenarios,
injecting synthetic anomalous records and generating alerts.
"""
import datetime
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import User, DailyFeature, RiskScore, Alert
from app.services.dependencies import get_current_auth_user

router = APIRouter(prefix="/api/simulate", tags=["simulate"])

SCENARIOS = {
    "data_exfiltration": {
        "alert_type": "DATA_EXFILTRATION",
        "severity": "CRITICAL",
        "risk_score": 0.93,
        "features": {"file_copy_count": 85, "usb_connect_count": 6,
                     "after_hours_login_count": 3, "exfil_indicator": 4.2},
        "description": "Late-night login + mass USB file copy",
    },
    "privilege_abuse": {
        "alert_type": "PRIVILEGE_ABUSE",
        "severity": "HIGH",
        "risk_score": 0.82,
        "features": {"unique_pcs": 7, "file_copy_count": 20,
                     "after_hours_login_count": 2, "exfil_indicator": 2.1},
        "description": "Unusual server access + sensitive file download",
    },
    "credential_compromise": {
        "alert_type": "SUSPICIOUS_LOGIN",
        "severity": "HIGH",
        "risk_score": 0.78,
        "features": {"unique_pcs": 8, "login_count": 15,
                     "after_hours_login_count": 4, "http_request_count": 340},
        "description": "New device login + rapid multi-system access",
    },
    "mass_download": {
        "alert_type": "MASS_DATA_DOWNLOAD",
        "severity": "HIGH",
        "risk_score": 0.76,
        "features": {"file_copy_count": 120, "http_request_count": 500,
                     "file_sharing_visit_count": 8, "exfil_indicator": 3.8},
        "description": "File access spike + large transfer volume",
    },
    "sabotage": {
        "alert_type": "POTENTIAL_SABOTAGE",
        "severity": "CRITICAL",
        "risk_score": 0.91,
        "features": {"unique_pcs": 5, "file_copy_count": 30,
                     "after_hours_login_count": 5, "http_request_count": 200},
        "description": "Production server access + file deletion/config change",
    },
}

SHAP_TEMPLATE = [
    {"feature": "file_copy_count", "friendly_name": "Files Copied to Removable Media",
     "value": 85.0, "shap_value": 0.42, "direction": "increases_risk"},
    {"feature": "after_hours_login_count", "friendly_name": "After-Hours Logins",
     "value": 3.0, "shap_value": 0.31, "direction": "increases_risk"},
    {"feature": "usb_connect_count", "friendly_name": "USB Connections",
     "value": 6.0, "shap_value": 0.28, "direction": "increases_risk"},
    {"feature": "exfil_indicator", "friendly_name": "Exfiltration Composite Score",
     "value": 4.2, "shap_value": 0.25, "direction": "increases_risk"},
    {"feature": "file_sharing_visit_count", "friendly_name": "File Sharing Site Visits",
     "value": 2.0, "shap_value": 0.15, "direction": "increases_risk"},
]

# Allowed DailyFeature columns to avoid unknown field errors
DAILY_FEATURE_COLS = {
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb", "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "external_email_ratio", "suspicious_attachment_count",
    "total_email_size_bytes", "http_request_count", "file_sharing_visit_count",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
}


def _persist_detected_user(db: Session, user_id: str, date_str: str,
                            scenario: dict, result: dict):
    """Save a real detected CERT user into the DB (upsert)."""
    import datetime as dt

    try:
        date_obj = dt.date.fromisoformat(date_str)
    except Exception:
        date_obj = dt.date.today()

    # Upsert user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            name=f"CERT Employee [{user_id}]",
            department="CERT Dataset",
            role="user",
            latest_risk_score=result["risk_score"],
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.latest_risk_score = result["risk_score"]

    # Upsert DailyFeature
    feat_kwargs = {k: v for k, v in result["feature_row"].items() if k in DAILY_FEATURE_COLS}
    feat = db.query(DailyFeature).filter(
        DailyFeature.user_id == user_id, DailyFeature.date == date_obj
    ).first()
    if feat:
        for k, v in feat_kwargs.items():
            setattr(feat, k, v)
    else:
        db.add(DailyFeature(user_id=user_id, date=date_obj, **feat_kwargs))

    # Upsert RiskScore
    ms = result["model_scores"]
    rs = db.query(RiskScore).filter(
        RiskScore.user_id == user_id, RiskScore.date == date_obj
    ).first()
    if rs:
        rs.risk_score = result["risk_score"]
    else:
        db.add(RiskScore(
            user_id=user_id, date=date_obj,
            if_score=ms.get("if_score", 0),
            ae_score=ms.get("ae_score", 0),
            lstm_score=ms.get("lstm_score", 0),
            gnn_score=ms.get("gnn_score", 0),
            rule_score=ms.get("rule_score", 0),
            risk_score=result["risk_score"],
        ))

    # Upsert Alert
    existing = db.query(Alert).filter(
        Alert.user_id == user_id,
        Alert.date == date_obj,
        Alert.alert_type == result["alert_type"],
    ).first()
    if not existing:
        db.add(Alert(
            user_id=user_id,
            date=date_obj,
            alert_type=result["alert_type"],
            severity=result["severity"],
            risk_score=result["risk_score"],
            shap_json=result["shap_values"] or SHAP_TEMPLATE,
            status="OPEN",
        ))

    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1 – Synthetic simulation (instant, hardcoded feature values)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{scenario_name}")
def trigger_simulation(
    scenario_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_auth_user),
):
    if scenario_name not in SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario. Available: {list(SCENARIOS.keys())}",
        )

    scenario = SCENARIOS[scenario_name]
    today = datetime.date.today()
    sim_user_id = f"SIM_{scenario_name[:6].upper()}"

    try:
        # Upsert simulated user
        sim_user = db.query(User).filter(User.id == sim_user_id).first()
        if not sim_user:
            sim_user = User(
                id=sim_user_id,
                name=f"Simulation: {scenario['description']}",
                department="SIMULATED",
                role="user",
                latest_risk_score=scenario["risk_score"],
            )
            db.add(sim_user)
            db.flush()  # flush to get FK available before child inserts
        else:
            sim_user.latest_risk_score = scenario["risk_score"]

        # Upsert DailyFeature — filter to valid columns only
        feat_kwargs = {k: float(v) for k, v in scenario["features"].items() if k in DAILY_FEATURE_COLS}
        feat = db.query(DailyFeature).filter(
            DailyFeature.user_id == sim_user_id, DailyFeature.date == today
        ).first()
        if feat:
            for k, v in feat_kwargs.items():
                setattr(feat, k, v)
        else:
            db.add(DailyFeature(user_id=sim_user_id, date=today, **feat_kwargs))

        # Upsert RiskScore
        rs = db.query(RiskScore).filter(
            RiskScore.user_id == sim_user_id, RiskScore.date == today
        ).first()
        base = scenario["risk_score"]
        if rs:
            rs.risk_score = base
        else:
            db.add(RiskScore(
                user_id=sim_user_id, date=today,
                if_score=round(min(1.0, base + random.uniform(-0.05, 0.05)), 3),
                ae_score=round(min(1.0, base + random.uniform(-0.05, 0.05)), 3),
                lstm_score=round(min(1.0, base + random.uniform(-0.08, 0.08)), 3),
                gnn_score=round(min(1.0, base + random.uniform(-0.1, 0.0)), 3),
                rule_score=0.9,
                risk_score=base,
            ))

        # Upsert Alert (one per user per day per type)
        existing_alert = db.query(Alert).filter(
            Alert.user_id == sim_user_id,
            Alert.date == today,
            Alert.alert_type == scenario["alert_type"],
        ).first()
        if not existing_alert:
            db.add(Alert(
                user_id=sim_user_id,
                date=today,
                alert_type=scenario["alert_type"],
                severity=scenario["severity"],
                risk_score=scenario["risk_score"],
                shap_json=SHAP_TEMPLATE,
                status="OPEN",
            ))

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {
        "message": f"Scenario '{scenario_name}' triggered successfully.",
        "user_id": sim_user_id,
        "alert_type": scenario["alert_type"],
        "risk_score": scenario["risk_score"],
        "description": scenario["description"],
        "mode": "synthetic",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2 – Real CERT dataset detection using trained ML models
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{scenario_name}/detect")
def detect_from_cert(
    scenario_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_auth_user),
):
    """
    Load the CERT dataset, run all 4 trained ML models (no re-training),
    find the most anomalous real employee matching the scenario pattern,
    persist them to the DB, and return their real risk score + SHAP values.
    """
    if scenario_name not in SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario. Available: {list(SCENARIOS.keys())}",
        )

    try:
        from ml.cert_detector import detect_scenario
        result = detect_scenario(scenario_name)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"CERT dataset not found. Ensure Dataset/ folder exists relative to backend/. Error: {e}",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Trained models not found. Run python run_pipeline.py first. Error: {e}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")

    try:
        _persist_detected_user(
            db=db,
            user_id=result["user_id"],
            date_str=result["date"],
            scenario=SCENARIOS[scenario_name],
            result=result,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB persistence error: {str(e)}")

    return {
        "message": f"Real CERT user detected for scenario '{scenario_name}'.",
        "user_id":      result["user_id"],
        "alert_type":   result["alert_type"],
        "severity":     result["severity"],
        "risk_score":   result["risk_score"],
        "date":         result["date"],
        "model_scores": result["model_scores"],
        "shap_count":   len(result["shap_values"]),
        "mode": "cert_dataset",
    }
