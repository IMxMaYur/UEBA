"""
auth_router.py – Login endpoint + admin auth-user management.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.orm_models import AuthUser
from app.schemas.schemas import LoginRequest, TokenResponse
from app.services.auth_service import authenticate_user, create_access_token, hash_password
from app.services.dependencies import require_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": user.role})
    return TokenResponse(access_token=token)


# ── Auth User Management (admin-only) ────────────────────────────────────────

class AuthUserListItem(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    class Config: from_attributes = True


class CreateAuthUserRequest(BaseModel):
    email: str
    password: str
    role: str = "analyst"


@router.get("/users", response_model=List[AuthUserListItem])
def list_auth_users(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Admin-only: list all system (auth) users."""
    return db.query(AuthUser).order_by(AuthUser.id).all()


@router.post("/users", response_model=AuthUserListItem, status_code=201)
def create_auth_user(
    req: CreateAuthUserRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Admin-only: create a new system user."""
    existing = db.query(AuthUser).filter(AuthUser.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User {req.email} already exists.")
    new_user = AuthUser(
        email=req.email,
        hashed_password=hash_password(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.delete("/users/{email}", status_code=204)
def delete_auth_user(
    email: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Admin-only: delete a system user (cannot delete yourself)."""
    if current_user.email == email:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    user = db.query(AuthUser).filter(AuthUser.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()
