"""Optional shared-password protection for the API.

Off by default, because the normal way to run this is on a laptop where the API
listens on 127.0.0.1 and nothing else can reach it. Adding auth there would only
be a password to lose.

It exists for the case where the dashboard is put on a public domain, at which
point an unauthenticated API would expose every stakeholder conversation the
agent has read. Set ``DASHBOARD_AUTH=true`` and ``DASHBOARD_PASSWORD`` and every
``/api`` route then requires ``Authorization: Bearer <password>``.

The browser never holds that password: the dashboard's Next.js server keeps it
and attaches it to its own calls, so the browser only ever has a session cookie.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.config import settings

UNCONFIGURED = (
    "DASHBOARD_AUTH is on but DASHBOARD_PASSWORD is still the default. "
    "Set a real password or turn DASHBOARD_AUTH off."
)


def check_password(candidate: str) -> bool:
    """Constant-time comparison, so a wrong guess leaks nothing by timing."""
    return hmac.compare_digest(candidate, settings.dashboard_password)


async def require_dashboard_auth(authorization: str | None = Header(default=None)) -> None:
    if not settings.dashboard_auth:
        return

    if not settings.dashboard_password or settings.dashboard_password == "changeme":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=UNCONFIGURED)

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not check_password(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorised",
            headers={"WWW-Authenticate": "Bearer"},
        )
