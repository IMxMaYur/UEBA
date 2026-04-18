import csv
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal
from app.models.orm_models import Base, User
from app.api import (
    auth_router, users_router, alerts_router, stats_router,
    simulate_router, investigation_router, seed_router,
)
from app.api import soar_router, ws_router
from app.services.auth_service import create_default_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Create all tables on startup (incl. new PlaybookAction table)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="UEBA – Insider Threat Detection Platform",
    description="AI-powered User and Entity Behavior Analytics using CERT r4.2 dataset.",
    version="2.0.0",
)

# ── CORS: allow * in demo mode for 2-laptop access ───────────────────────────
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,    # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(alerts_router.router)
app.include_router(stats_router.router)
app.include_router(simulate_router.router)
app.include_router(investigation_router.router)
app.include_router(seed_router.router)
app.include_router(soar_router.router)
app.include_router(ws_router.router)


def _seed_psychometric_data(db):
    """
    Read Dataset/psychometric.csv and hydrate the users table with OCEAN scores.
    Columns: employee_name, user_id, O, C, E, A, N
    Uses INSERT OR IGNORE semantics — only updates users that already exist.
    """
    csv_path = os.path.join(
        os.path.dirname(__file__),          # backend/app/
        "..", "..", "Dataset", "psychometric.csv"
    )
    csv_path = os.path.normpath(csv_path)

    if not os.path.exists(csv_path):
        logger.warning("psychometric.csv not found at %s – skipping OCEAN seeding.", csv_path)
        return

    seeded_count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uid = row.get("user_id", "").strip()
            if not uid:
                continue
            user = db.query(User).filter(User.id == uid).first()
            if user is None:
                continue    # user not in DB yet; skip quietly
            user.ocean_o = int(row["O"])
            user.ocean_c = int(row["C"])
            user.ocean_e = int(row["E"])
            user.ocean_a = int(row["A"])
            user.ocean_n = int(row["N"])
            seeded_count += 1

    db.commit()
    logger.info("✅ Seeded Psychometric Data: %d users enriched with OCEAN scores.", seeded_count)


@app.on_event("startup")
def startup_event():
    """Seed default admin/analyst credentials and OCEAN psychometric data on first run."""
    db = SessionLocal()
    try:
        create_default_admin(db)
        _seed_psychometric_data(db)
        mode_str = "DEMO (CORS=*)" if DEMO_MODE else "PRODUCTION"
        logger.info(f"UEBA API v2.0 started [{mode_str}]. Credentials seeded.")
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "UEBA API", "version": "2.0.0", "demo_mode": DEMO_MODE}

