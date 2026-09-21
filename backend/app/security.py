"""Password hashing and session tokens.

Stdlib only, deliberately: PBKDF2-HMAC-SHA256 for password storage and an
HMAC-signed, expiring token for sessions. This is not the last word in web
auth, but for a single-instance dashboard behind an optional shared gate it is
plenty, and it avoids pulling in a hashing library for a graduation project.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid

from app.config import settings

_PBKDF2_ITERATIONS = 390_000
_SALT_BYTES = 16
#: How long a signed-in session lasts before the cookie needs a fresh login.
TOKEN_LIFETIME_SECONDS = 60 * 60 * 12


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_hex, digest_hex = password_hash.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _signature(payload: str) -> str:
    return hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(user_id: uuid.UUID, username: str) -> str:
    """An opaque, tamper-evident session token: ``user_id.username.expiry.signature``.

    Safe to hand to a browser as a cookie value: it proves *who signed in and
    until when*, not the password, and cannot be edited without invalidating
    the signature.
    """
    expiry = int(time.time()) + TOKEN_LIFETIME_SECONDS
    username_b64 = base64.urlsafe_b64encode(username.encode()).decode().rstrip("=")
    payload = f"{user_id}.{username_b64}.{expiry}"
    return f"{payload}.{_signature(payload)}"


def verify_token(token: str) -> dict | None:
    """The token's claims if it is validly signed and not expired, else None."""
    parts = token.split(".")
    if len(parts) != 4:
        return None
    user_id, username_b64, expiry_str, signature = parts
    payload = f"{user_id}.{username_b64}.{expiry_str}"
    if not hmac.compare_digest(_signature(payload), signature):
        return None
    try:
        expiry = int(expiry_str)
        if expiry < time.time():
            return None
        username = base64.urlsafe_b64decode(username_b64 + "==").decode()
        return {"user_id": uuid.UUID(user_id), "username": username}
    except (ValueError, UnicodeDecodeError):
        return None
