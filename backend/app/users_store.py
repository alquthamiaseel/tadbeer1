from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import REPO_ROOT, settings

_lock = threading.Lock()


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    created_at: str


def users_path() -> Path:
    path = Path(settings.users_file)
    return path if path.is_absolute() else REPO_ROOT / path


def _read() -> list[dict]:
    path = users_path()
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []


def _write(records: list[dict]) -> None:
    path = users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(records, indent=2), encoding="utf-8")
    os.replace(temp, path)


def find_user(username: str) -> User | None:
    with _lock:
        for record in _read():
            if record["username"] == username:
                return User(**record)
    return None


def upsert_user(username: str, password_hash: str) -> bool:
    with _lock:
        records = _read()
        for record in records:
            if record["username"] == username:
                record["password_hash"] = password_hash
                _write(records)
                return False
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=password_hash,
            created_at=datetime.now(UTC).isoformat(),
        )
        records.append(asdict(user))
        _write(records)
        return True
