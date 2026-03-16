"""
auth_router.py – Login + Register endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm_models import AuthUser
from app.schemas.schemas import LoginRequest, TokenResponse
from app.services.auth_service import authenticate_user, create_access_token, hash_password
from app.services.dependencies import require_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/register", status_code=201)
def register_user(
    req: LoginRequest,
    role: str = "analyst",
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """
    Admin-only: create a new dashboard user with email, password, and role.
    Roles: admin | manager | analyst | viewer
    """
    valid_roles = {"admin", "manager", "analyst", "viewer"}
    if role not in valid_roles:
        raise HTTPException(status_code=422, detail=f"Invalid role. Must be one of: {sorted(valid_roles)}")

    existing = db.query(AuthUser).filter(AuthUser.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User '{req.email}' already exists.")

    new_user = AuthUser(
        email=req.email,
        hashed_password=hash_password(req.password),
        role=role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "email": new_user.email, "role": new_user.role}


@router.get("/users")
def list_auth_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Admin-only: list all dashboard users (email + role, no passwords)."""
    users = db.query(AuthUser).all()
    return [{"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]


@router.delete("/users/{user_id}", status_code=204)
def delete_auth_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Admin-only: delete a dashboard user."""
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
