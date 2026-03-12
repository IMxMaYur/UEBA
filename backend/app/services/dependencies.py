"""
FastAPI dependency: extract and validate JWT bearer token → current auth user.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import AuthUser
from app.services.auth_service import get_current_user_email

bearer_scheme = HTTPBearer()


def get_current_auth_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthUser:
    token = credentials.credentials
    email = get_current_user_email(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(AuthUser).filter(AuthUser.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: AuthUser = Depends(get_current_auth_user)) -> AuthUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
