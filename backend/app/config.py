"""
config.py – Application settings loaded from .env
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://ueba_user:ueba_pass@localhost:5432/ueba_db"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "change-me-to-a-random-secret-key-at-least-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    risk_threshold: float = 0.65
    dataset_path: str = "../Dataset"
    http_sample_rate: float = 0.10

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
