"""
main.py – FastAPI application entry point for the UEBA platform.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal
from app.models.orm_models import Base
from app.api import auth_router, users_router, alerts_router, stats_router, simulate_router, investigation_router
from app.services.auth_service import create_default_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Create all tables on startup
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


@app.on_event("startup")
def startup_event():
    """Seed default admin/analyst credentials on first run."""
    db = SessionLocal()
    try:
        create_default_admin(db)
        logger.info("UEBA API started. Default credentials seeded if needed.")
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "UEBA API"}
