from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class AuditEntry:
    kind: str
    target: str
    ok: bool = True
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    detail: dict | None = None
    error: str | None = None


@dataclass
class Collector:
    entries: list[AuditEntry] = field(default_factory=list)

    def add(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    @property
    def input_tokens(self) -> int:
        return sum(entry.input_tokens for entry in self.entries)

    @property
    def output_tokens(self) -> int:
        return sum(entry.output_tokens for entry in self.entries)


_current: ContextVar[Collector | None] = ContextVar("audit_collector", default=None)


@contextlib.contextmanager
def collecting() -> Iterator[Collector]:
    collector = Collector()
    token = _current.set(collector)
    try:
        yield collector
    finally:
        _current.reset(token)


def record(entry: AuditEntry) -> None:
    collector = _current.get()
    if collector is not None:
        collector.add(entry)


def record_llm(
    *,
    model: str,
    ok: bool,
    duration_ms: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thought_tokens: int = 0,
    output_model: str | None = None,
    error: str | None = None,
) -> None:
    record(
        AuditEntry(
            kind="llm",
            target=model,
            ok=ok,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            detail={"schema": output_model, "thought_tokens": thought_tokens},
            error=error,
        )
    )


def record_api(
    *,
    service: str,
    method: str,
    url: str,
    status: int | None,
    ok: bool,
    duration_ms: int,
    attempts: int = 1,
    error: str | None = None,
) -> None:
    record(
        AuditEntry(
            kind="api",
            target=f"{service} {method} {_path_of(url)}"[:200],
            ok=ok,
            duration_ms=duration_ms,
            detail={"status": status, "attempts": attempts},
            error=error,
        )
    )


def _path_of(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    slash = without_scheme.find("/")
    return without_scheme[slash:] if slash != -1 else without_scheme
