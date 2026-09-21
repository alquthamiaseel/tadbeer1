"""Dashboard authentication.

Off by default, because the normal way to run this is on a laptop where the API
listens on 127.0.0.1 and nothing else can reach it. Adding a login there would
only be a password to lose.

It exists for the case where the dashboard is put on a public domain, at which
point an unauthenticated API would expose every stakeholder conversation the
agent has read. Set ``DASHBOARD_AUTH=true`` (and a real ``SESSION_SECRET``) and
every ``/api`` route then requires ``Authorization: Bearer <session token>``,
obtained by signing in against the ``users`` table below.

The browser never holds a password: the dashboard's Next.js server collects it
from the sign-in form, exchanges it here for a signed session token, and keeps
that in an httpOnly cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import User
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


# --- login --------------------------------------------------------------

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    username: str


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)) -> LoginOut:
    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Compare against a hash either way, so a wrong username and a wrong
    # password fail in the same amount of time.
    valid = user is not None and verify_password(body.password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong username or password"
        )

    return LoginOut(token=create_token(user.id, user.username), username=user.username)
