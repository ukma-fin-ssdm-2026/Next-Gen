"""Короткоживучі OIDC-потоки та непрозорі серверні сесії."""

from dataclasses import dataclass
from secrets import token_urlsafe
from threading import Lock
import time
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class _ExpiringValue:
    value: Any
    expires_at: float


class InMemoryOidcFlowStore:
    """Зберігає MSAL flow на сервері; для production замінюється Redis."""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl_seconds = ttl_seconds
        self._flows: dict[str, _ExpiringValue] = {}
        self._lock = Lock()

    def save(self, state: str, flow: dict[str, Any]) -> None:
        with self._lock:
            self._flows[state] = _ExpiringValue(
                value=flow,
                expires_at=time.monotonic() + self._ttl_seconds,
            )

    def pop(self, state: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._flows.pop(state, None)
        if item is None or item.expires_at <= time.monotonic():
            return None
        return item.value


class InMemoryAuthSessionStore:
    """Зберігає на сервері зв'язок cookie із локальним User."""

    def __init__(self, ttl_seconds: int = 8 * 60 * 60) -> None:
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, _ExpiringValue] = {}
        self._lock = Lock()

    def create(self, user_id: UUID) -> str:
        token = token_urlsafe(32)
        with self._lock:
            self._sessions[token] = _ExpiringValue(
                value=user_id,
                expires_at=time.monotonic() + self._ttl_seconds,
            )
        return token

    def resolve(self, token: str) -> UUID | None:
        with self._lock:
            item = self._sessions.get(token)
            if item is not None and item.expires_at <= time.monotonic():
                self._sessions.pop(token, None)
                item = None
        return None if item is None else item.value

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)
