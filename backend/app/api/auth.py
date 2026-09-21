from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app import users_store
from app.config import settings
from app.security import create_token, verify_password, verify_token

UNCONFIGURED = (
    "DASHBOARD_AUTH is on but SESSION_SECRET is still the default. "
    "Set a real secret or turn DASHBOARD_AUTH off."
)


async def require_dashboard_auth(authorization: str | None = Header(default=None)) -> None:
    if not settings.dashboard_auth:
        return

    if not settings.session_secret or settings.session_secret == "changeme-session-secret":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=UNCONFIGURED)

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or verify_token(token) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorised",
            headers={"WWW-Authenticate": "Bearer"},
        )


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    username: str


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn) -> LoginOut:
    user = users_store.find_user(body.username)

    valid = user is not None and verify_password(body.password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong username or password"
        )

    return LoginOut(token=create_token(uuid.UUID(user.id), user.username), username=user.username)
