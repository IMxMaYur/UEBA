"""
main.py – FastAPI application entry point for the UEBA platform.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal
from app.models.orm_models import Base, User
from app.api import auth_router, users_router, alerts_router, stats_router, simulate_router, investigation_router, seed_router
from app.services.auth_service import create_default_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Create all tables on startup (creates new OCEAN columns if DB already exists)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="UEBA – Insider Threat Detection Platform",
    description="AI-powered User and Entity Behavior Analytics using CERT r4.2 dataset.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
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


@app.on_event("startup")
def startup_event():
    """Seed default admin credentials and auto-populate CERT users on first run."""
    db = SessionLocal()
    try:
        # 1. Create default admin/analyst auth accounts
        create_default_admin(db)

        # 2. Auto-seed CERT employees from psychometric.csv if user registry is sparse
        user_count = db.query(User).count()
        if user_count < 100:
            logger.info(f"Only {user_count} users found — auto-seeding from psychometric.csv …")
            try:
                from app.api.seed_router import _do_seed
                result = _do_seed(db)
                logger.info(f"Auto-seed: {result['message']}")
            except Exception as seed_err:
                logger.warning(f"Auto-seed skipped: {seed_err}")
        else:
            logger.info(f"User registry has {user_count} users — skipping auto-seed.")

        logger.info("UEBA API started successfully.")
    finally:
        db.close()


# Health endpoints — available at both /health (direct) and /api/health (through Vite proxy)
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "UEBA API"}
