"""
auth_service.py – JWT token creation and password utilities.
"""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.orm_models import AuthUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user_email(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[AuthUser]:
    user = db.query(AuthUser).filter(AuthUser.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_default_admin(db: Session):
    """Create a default admin user if no auth users exist."""
    if db.query(AuthUser).count() == 0:
        admin = AuthUser(
            email="admin@ueba.local",
            hashed_password=hash_password("Admin@1234"),
            role="admin",
        )
        db.add(admin)
        analyst = AuthUser(
            email="analyst@ueba.local",
            hashed_password=hash_password("Analyst@1234"),
            role="analyst",
        )
        db.add(analyst)
        db.commit()
