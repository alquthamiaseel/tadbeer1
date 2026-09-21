from __future__ import annotations

import argparse
import sys

from app import users_store
from app.security import hash_password


def create_user(username: str, password: str) -> int:
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1

    created = users_store.upsert_user(username, hash_password(password))
    if created:
        print(f"Created user {username!r} in {users_store.users_path()}.")
    else:
        print(f"Updated the password for {username!r}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    return create_user(args.username, args.password)


if __name__ == "__main__":
    sys.exit(main())
