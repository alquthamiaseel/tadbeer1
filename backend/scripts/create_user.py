"""Create or update a dashboard login.

There is no sign-up flow — accounts are provisioned by whoever runs the
backend. Running this twice for the same username resets that user's password
rather than failing, so it doubles as "I forgot my password."

Usage:
    python -m scripts.create_user --username alice --password s3cret
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.security import hash_password


async def create_user(username: str, password: str) -> int:
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user is None:
            session.add(User(username=username, password_hash=hash_password(password)))
            await session.commit()
            print(f"Created user {username!r}.")
        else:
            user.password_hash = hash_password(password)
            await session.commit()
            print(f"Updated the password for {username!r}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    return asyncio.run(create_user(args.username, args.password))


if __name__ == "__main__":
    sys.exit(main())
