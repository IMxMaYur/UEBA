"""
simulate_router.py – Trigger insider threat attack scenarios.

Supports two modes per scenario:
  POST /api/simulate/{scenario_name}          → Synthetic (instant, demo-ready)
  POST /api/simulate/{scenario_name}/detect   → Real CERT ML detection

New scenarios added: impossible_travel, brute_force
All scenarios now auto-trigger:
  - AI narrative generation
  - SOAR playbook execution
  - WebSocket broadcast to all connected analyst dashboards
"""
import asyncio
import datetime
import random
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import User, DailyFeature, RiskScore, Alert
from app.services.dependencies import get_current_auth_user
from app.services.narrative_engine import generate_narrative, generate_simple_narrative
from app.services.soar_engine import execute_playbook
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/simulate", tags=["simulate"])

# ─── Scenario definitions ────────────────────────────────────────────────────
SCENARIOS = {
    "data_exfiltration": {
        "alert_type": "DATA_EXFILTRATION",
        "severity": "CRITICAL",
        "risk_score": 0.93,
        "features": {"file_copy_count": 85, "usb_connect_count": 6,
                     "after_hours_login_count": 3, "exfil_indicator": 4.2},
        "description": "Late-night login + mass USB file copy (85 files)",
        "display_name": "Data Exfiltration",
        "icon": "🔴",
    },
    "privilege_abuse": {
        "alert_type": "PRIVILEGE_ABUSE",
        "severity": "HIGH",
        "risk_score": 0.82,
        "features": {"unique_pcs": 7, "file_copy_count": 20,
                     "after_hours_login_count": 2, "exfil_indicator": 2.1},
        "description": "Unusual server access + sensitive file download",
        "display_name": "Privilege Abuse",
        "icon": "🟠",
    },
    "credential_compromise": {
        "alert_type": "SUSPICIOUS_LOGIN",
        "severity": "HIGH",
        "risk_score": 0.78,
        "features": {"unique_pcs": 8, "login_count": 15,
                     "after_hours_login_count": 4, "http_request_count": 340},
        "description": "New device login + rapid multi-system access",
        "display_name": "Credential Compromise",
        "icon": "🟠",
    },
    "mass_download": {
        "alert_type": "MASS_DATA_DOWNLOAD",
        "severity": "HIGH",
        "risk_score": 0.76,
        "features": {"file_copy_count": 120, "http_request_count": 500,
                     "file_sharing_visit_count": 8, "exfil_indicator": 3.8},
        "description": "File access spike + large transfer volume",
        "display_name": "Mass Data Download",
        "icon": "🟡",
    },
    "sabotage": {
        "alert_type": "POTENTIAL_SABOTAGE",
        "severity": "CRITICAL",
        "risk_score": 0.91,
        "features": {"unique_pcs": 5, "file_copy_count": 30,
                     "after_hours_login_count": 5, "http_request_count": 200},
        "description": "Production server access + file deletion/config change",
        "display_name": "Insider Sabotage",
        "icon": "🔴",
    },
    "impossible_travel": {
        "alert_type": "IMPOSSIBLE_TRAVEL",
        "severity": "CRITICAL",
        "risk_score": 0.88,
        "features": {"login_count": 2, "after_hours_login_count": 1,
                     "unique_pcs": 2, "http_request_count": 50},
        "description": "Geographically impossible login sequence detected",
        "display_name": "Impossible Travel",
        "icon": "🌍",
    },
    "brute_force": {
        "alert_type": "BRUTE_FORCE",
        "severity": "CRITICAL",
        "risk_score": 0.94,
        "features": {"login_count": 47, "after_hours_login_count": 47,
                     "unique_pcs": 1, "http_request_count": 47},
        "description": "47 failed login attempts from Tor exit node in 3 minutes",
        "display_name": "Brute Force Attack",
        "icon": "🔒",
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

# Scenario-specific SHAP templates
SCENARIO_SHAP = {
    "impossible_travel": [
        {"feature": "impossible_travel", "friendly_name": "Impossible Geographic Travel",
         "value": 12556.0, "shap_value": 0.55, "direction": "increases_risk"},
        {"feature": "time_delta_minutes", "friendly_name": "Time Between Logins (min)",
         "value": 45.0, "shap_value": 0.35, "direction": "increases_risk"},
        {"feature": "new_country_login", "friendly_name": "Login from New Country",
         "value": 1.0, "shap_value": 0.28, "direction": "increases_risk"},
        {"feature": "velocity_km_per_hour", "friendly_name": "Required Travel Speed (km/h)",
         "value": 16741.0, "shap_value": 0.22, "direction": "increases_risk"},
    ],
    "brute_force": [
        {"feature": "failed_login_velocity", "friendly_name": "Failed Login Rate (per min)",
         "value": 15.67, "shap_value": 0.60, "direction": "increases_risk"},
        {"feature": "ip_reputation_score", "friendly_name": "IP Reputation (Known Malicious)",
         "value": 1.0, "shap_value": 0.45, "direction": "increases_risk"},
        {"feature": "foreign_country_source", "friendly_name": "Login Attempt from Foreign Country",
         "value": 1.0, "shap_value": 0.30, "direction": "increases_risk"},
        {"feature": "failed_login_attempts", "friendly_name": "Total Failed Logins",
         "value": 47.0, "shap_value": 0.25, "direction": "increases_risk"},
    ],
    "privilege_abuse": [
        {"feature": "unique_pcs", "friendly_name": "Unique Workstations Accessed",
         "value": 7.0, "shap_value": 0.48, "direction": "increases_risk"},
        {"feature": "file_copy_count", "friendly_name": "Files Copied",
         "value": 20.0, "shap_value": 0.35, "direction": "increases_risk"},
        {"feature": "after_hours_login_count", "friendly_name": "After-Hours Logins",
         "value": 2.0, "shap_value": 0.27, "direction": "increases_risk"},
        {"feature": "exfil_indicator", "friendly_name": "Exfiltration Composite Score",
         "value": 2.1, "shap_value": 0.22, "direction": "increases_risk"},
    ],
}

DAILY_FEATURE_COLS = {
    "login_count", "after_hours_login_count", "login_hour_mean", "unique_pcs",
    "usb_connect_count", "after_hours_usb", "file_copy_count", "after_hours_file_copy",
    "email_sent_count", "external_email_ratio", "suspicious_attachment_count",
    "total_email_size_bytes", "http_request_count", "file_sharing_visit_count",
    "exfil_indicator", "after_hours_activity_total", "behavior_spike_score",
}

# Realistic employee personas for simulation
SIM_PERSONAS = {
    "data_exfiltration":   ("Alice Chen",    "Finance"),
    "privilege_abuse":     ("Robert Mills",  "IT Operations"),
    "credential_compromise":("David Kumar",  "Engineering"),
    "mass_download":       ("Sarah Johnson", "R&D"),
    "sabotage":            ("Mark Davis",    "DevOps"),
    "impossible_travel":   ("Emily Zhang",   "Sales"),
    "brute_force":         ("TARGET-USER",   "External Attack"),
}


def _get_shap(scenario_name: str) -> list:
    return SCENARIO_SHAP.get(scenario_name, SHAP_TEMPLATE)


def _get_narrative(scenario_name: str, scenario: dict, shap: list, user_name: str) -> str:
    try:
        return generate_narrative(
            shap_values=shap,
            alert_type=scenario["alert_type"],
            severity=scenario["severity"],
            user_name=user_name,
            risk_score=scenario["risk_score"],
        )
    except Exception:
        return generate_simple_narrative(
            alert_type=scenario["alert_type"],
            severity=scenario["severity"],
            risk_score=scenario["risk_score"],
        )


def _persist_detected_user(db: Session, user_id: str, date_str: str,
                            scenario: dict, result: dict):
    """Save a real detected CERT user into the DB (upsert)."""
    import datetime as dt
    try:
        date_obj = dt.date.fromisoformat(date_str)
    except Exception:
        date_obj = dt.date.today()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(id=user_id, name=f"CERT Employee [{user_id}]",
                    department="CERT Dataset", role="user",
                    latest_risk_score=result["risk_score"], is_active=True)
        db.add(user)
        db.flush()
    else:
        user.latest_risk_score = result["risk_score"]

    feat_kwargs = {k: v for k, v in result["feature_row"].items() if k in DAILY_FEATURE_COLS}
    feat = db.query(DailyFeature).filter(
        DailyFeature.user_id == user_id, DailyFeature.date == date_obj
    ).first()
    if feat:
        for k, v in feat_kwargs.items():
            setattr(feat, k, v)
    else:
        db.add(DailyFeature(user_id=user_id, date=date_obj, **feat_kwargs))

    ms = result["model_scores"]
    rs = db.query(RiskScore).filter(
        RiskScore.user_id == user_id, RiskScore.date == date_obj
    ).first()
    if rs:
        rs.risk_score = result["risk_score"]
    else:
        db.add(RiskScore(
            user_id=user_id, date=date_obj,
            if_score=ms.get("if_score", 0), ae_score=ms.get("ae_score", 0),
            lstm_score=ms.get("lstm_score", 0), gnn_score=ms.get("gnn_score", 0),
            rule_score=ms.get("rule_score", 0), risk_score=result["risk_score"],
        ))

    existing = db.query(Alert).filter(
        Alert.user_id == user_id, Alert.date == date_obj,
        Alert.alert_type == result["alert_type"],
    ).first()
    if not existing:
        shap = result["shap_values"] or SHAP_TEMPLATE
        narrative = _get_narrative("", scenario, shap, f"CERT:{user_id}")
        new_alert = Alert(
            user_id=user_id, date=date_obj,
            alert_type=result["alert_type"], severity=result["severity"],
            risk_score=result["risk_score"], shap_json=shap,
            status="OPEN", narrative=narrative,
        )
        db.add(new_alert)
        db.flush()
        execute_playbook(new_alert, db)

    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1 – Synthetic simulation (instant, hardcoded feature values)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{scenario_name}")
async def trigger_simulation(
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
    sim_user_id = f"SIM_{scenario_name[:8].upper()}"
    persona_name, persona_dept = SIM_PERSONAS.get(
        scenario_name, ("Simulated User", "SIMULATED")
    )

    geo_details = None
    if scenario_name == "impossible_travel":
        from app.services.geo_detector import detect_impossible_travel
        travel = detect_impossible_travel()
        geo_details = {
            "city_a": travel.city_a, "country_a": travel.country_a,
            "city_b": travel.city_b, "country_b": travel.country_b,
            "time_delta_minutes": travel.time_delta_minutes,
            "distance_km": travel.distance_km,
            "description": travel.description,
        }

    attack_details = None
    if scenario_name == "brute_force":
        from app.services.brute_force_detector import detect_brute_force
        bf = detect_brute_force()
        attack_details = {
            "source_ip": bf.source_ip,
            "ip_reputation": bf.ip_reputation,
            "country": bf.country,
            "failed_attempts": bf.failed_attempts,
        }

    shap = _get_shap(scenario_name)
    narrative = _get_narrative(scenario_name, scenario, shap, persona_name)

    try:
        sim_user = db.query(User).filter(User.id == sim_user_id).first()
        if not sim_user:
            sim_user = User(
                id=sim_user_id, name=f"{persona_name} [{scenario['display_name']}]",
                department=persona_dept, role="user",
                latest_risk_score=scenario["risk_score"],
            )
            db.add(sim_user)
            db.flush()
        else:
            sim_user.latest_risk_score = scenario["risk_score"]
            sim_user.name = f"{persona_name} [{scenario['display_name']}]"

        feat_kwargs = {k: float(v) for k, v in scenario["features"].items()
                       if k in DAILY_FEATURE_COLS}
        feat = db.query(DailyFeature).filter(
            DailyFeature.user_id == sim_user_id, DailyFeature.date == today
        ).first()
        if feat:
            for k, v in feat_kwargs.items():
                setattr(feat, k, v)
        else:
            db.add(DailyFeature(user_id=sim_user_id, date=today, **feat_kwargs))

        base = scenario["risk_score"]
        rs = db.query(RiskScore).filter(
            RiskScore.user_id == sim_user_id, RiskScore.date == today
        ).first()
        if rs:
            rs.risk_score = base
        else:
            db.add(RiskScore(
                user_id=sim_user_id, date=today,
                if_score=round(min(1.0, base + random.uniform(-0.05, 0.05)), 3),
                ae_score=round(min(1.0, base + random.uniform(-0.05, 0.05)), 3),
                lstm_score=round(min(1.0, base + random.uniform(-0.08, 0.08)), 3),
                gnn_score=round(min(1.0, base + random.uniform(-0.1, 0.0)), 3),
                rule_score=0.9, risk_score=base,
            ))

        existing_alert = db.query(Alert).filter(
            Alert.user_id == sim_user_id, Alert.date == today,
            Alert.alert_type == scenario["alert_type"],
        ).first()

        soar_result = None
        alert_id = None
        if not existing_alert:
            new_alert = Alert(
                user_id=sim_user_id, date=today,
                alert_type=scenario["alert_type"], severity=scenario["severity"],
                risk_score=scenario["risk_score"], shap_json=shap,
                status="OPEN", narrative=narrative, geo_details=geo_details,
            )
            db.add(new_alert)
            db.flush()
            alert_id = new_alert.id
            soar_result = execute_playbook(new_alert, db)
        else:
            alert_id = existing_alert.id
            existing_alert.narrative = narrative
            if geo_details:
                existing_alert.geo_details = geo_details

        db.commit()

        # ── Broadcast via WebSocket to all connected dashboards ──────────
        soar_tier = soar_result["tier"] if soar_result else None
        asyncio.create_task(ws_manager.broadcast_alert(
            user_id=sim_user_id,
            alert_type=scenario["alert_type"],
            severity=scenario["severity"],
            risk_score=scenario["risk_score"],
            description=scenario["description"],
            alert_id=alert_id,
            narrative=narrative[:200] + "..." if narrative and len(narrative) > 200 else narrative,
            soar_tier=soar_tier,
        ))

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {
        "message": f"Scenario '{scenario['display_name']}' triggered successfully.",
        "user_id": sim_user_id,
        "persona_name": persona_name,
        "alert_type": scenario["alert_type"],
        "risk_score": scenario["risk_score"],
        "severity": scenario["severity"],
        "description": scenario["description"],
        "narrative": narrative,
        "soar_response": soar_result,
        "geo_details": geo_details,
        "attack_details": attack_details,
        "alert_id": alert_id,
        "mode": "synthetic",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2 – Real CERT dataset detection using trained ML models
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{scenario_name}/detect")
def detect_from_cert(
    scenario_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_auth_user),
):
    if scenario_name not in SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario. Available: {list(SCENARIOS.keys())}",
        )

    try:
        from ml.cert_detector import detect_scenario
        results = detect_scenario(scenario_name, db=db, top_n=5, start_date=start_date, end_date=end_date)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503,
            detail=f"CERT dataset not found. Error: {e}")
    except RuntimeError as e:
        raise HTTPException(status_code=503,
            detail=f"Trained models not found. Run python run_pipeline.py first. Error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")

    persisted = []
    for result in results:
        try:
            _persist_detected_user(
                db=db, user_id=result["user_id"],
                date_str=result["date"],
                scenario=SCENARIOS[scenario_name], result=result,
            )
            persisted.append(result["user_id"])
        except Exception:
            db.rollback()

    top = results[0]
    return {
        "message": f"Top {len(results)} real CERT users detected for '{scenario_name}'.",
        "user_id":       top["user_id"],
        "alert_type":    top["alert_type"],
        "severity":      top["severity"],
        "risk_score":    top["risk_score"],
        "date":          top["date"],
        "model_scores":  top["model_scores"],
        "shap_count":    len(top["shap_values"]),
        "mode":          "cert_dataset",
        "top_users": [
            {"user_id": r["user_id"], "risk_score": r["risk_score"],
             "date": r["date"], "model_scores": r["model_scores"]}
            for r in results
        ],
        "persisted_count": len(persisted),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 3 – List available scenarios (for frontend)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/")
def list_scenarios():
    """Return all available simulation scenarios with metadata."""
    return [
        {
            "name": name,
            "display_name": s["display_name"],
            "alert_type": s["alert_type"],
            "severity": s["severity"],
            "risk_score": s["risk_score"],
            "description": s["description"],
            "icon": s["icon"],
        }
        for name, s in SCENARIOS.items()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 4 – Real-time in-memory stream control (Kafka-compatible)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/start-stream")
async def start_live_stream(
    speed: float = 500.0,
    max_events: int = 20000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_auth_user),
):
    """
    Start the in-memory Kafka-compatible event stream.
    Replays CERT dataset as live events, runs sliding-window ML detection,
    and pushes real-time alerts via WebSocket.
    """
    from streaming.stream_producer import start_stream, get_stream_status, _running as prod_running
    from streaming.stream_consumer import start_consumer, get_consumer_status

    if prod_running:
        return {"message": "Stream already running.", "status": get_stream_status()}

    # Launch producer + consumer as background tasks
    asyncio.create_task(start_stream(
        speed_multiplier=speed,
        max_events_per_source=max_events,
        start_date=start_date,
        end_date=end_date,
    ))
    asyncio.create_task(start_consumer())

    return {
        "message": f"✅ Live stream started! Replaying CERT dataset at {speed}× speed.",
        "speed_multiplier": speed,
        "max_events_per_source": max_events,
        "date_filter": {"start": start_date, "end": end_date},
        "note": "Watch the Dashboard — alerts will fire in real-time via WebSocket.",
    }


@router.post("/stop-stream")
def stop_live_stream(current_user=Depends(get_current_auth_user)):
    """Stop the running in-memory event stream."""
    from streaming.stream_producer import stop_stream
    from streaming.stream_consumer import stop_consumer
    stop_stream()
    stop_consumer()
    return {"message": "✅ Stream stopped."}


@router.get("/stream-status")
def stream_status(current_user=Depends(get_current_auth_user)):
    """Get current producer and consumer statistics."""
    try:
        from streaming.stream_producer import get_stream_status
        from streaming.stream_consumer import get_consumer_status
        return {
            "producer": get_stream_status(),
            "consumer": get_consumer_status(),
        }
    except Exception as e:
        return {"error": str(e), "producer": {}, "consumer": {}}
