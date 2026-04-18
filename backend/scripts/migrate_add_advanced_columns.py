"""
migrate_add_advanced_columns.py
--------------------------------
Safe, idempotent migration that adds the new columns introduced by the
UEBA improvement upgrade:

  daily_features:
    - peer_risk_score       FLOAT DEFAULT 0
    - dlp_keyword_hit_count FLOAT DEFAULT 0
    - email_sentiment_score FLOAT DEFAULT 0
    - is_false_positive     BOOLEAN DEFAULT FALSE

Run once:
    python scripts/migrate_add_advanced_columns.py
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NEW_COLUMNS = [
    ("peer_risk_score",        "FLOAT",   "0"),
    ("dlp_keyword_hit_count",  "FLOAT",   "0"),
    ("email_sentiment_score",  "FLOAT",   "0"),
    ("is_false_positive",      "BOOLEAN", "FALSE"),
]


def migrate():
    from app.database import engine
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("daily_features")}

    with engine.begin() as conn:
        for col_name, col_type, default in NEW_COLUMNS:
            if col_name in existing:
                logger.info(f"  SKIP  daily_features.{col_name} (already exists)")
            else:
                sql = (
                    f"ALTER TABLE daily_features "
                    f"ADD COLUMN {col_name} {col_type} DEFAULT {default};"
                )
                conn.execute(text(sql))
                logger.info(f"  ADDED daily_features.{col_name} ({col_type} DEFAULT {default})")

    logger.info("Migration complete.")


if __name__ == "__main__":
    migrate()
