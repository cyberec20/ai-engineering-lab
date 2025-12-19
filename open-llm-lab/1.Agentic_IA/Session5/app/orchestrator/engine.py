from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class SessionData:
    created_at: float
    updated_at: float
    agents_created: list[dict[str, Any]]
    memory: dict[str, Any]


class SessionStore:
    def __init__(self, *, ttl_seconds: int, max_sessions: int) -> None:
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._sessions: dict[str, SessionData] = {}

    def _gc(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if (now - s.updated_at) > self._ttl]
        for sid in expired:
            self._sessions.pop(sid, None)
        if len(self._sessions) <= self._max:
            return
        for sid, _ in sorted(self._sessions.items(), key=lambda kv: kv[1].updated_at)[: max(0, len(self._sessions) - self._max)]:
            self._sessions.pop(sid, None)

    def get_or_create(self, session_id: str) -> SessionData:
        self._gc()
        now = time.time()
        s = self._sessions.get(session_id)
        if s is None:
            s = SessionData(created_at=now, updated_at=now, agents_created=[], memory={})
            self._sessions[session_id] = s
        else:
            s.updated_at = now
        return s

    def set_memory(self, session_id: str, key: str, value: Any) -> None:
        s = self.get_or_create(session_id)
        s.memory[key] = value
        s.updated_at = time.time()

    def get_memory(self, session_id: str, key: str, default: Any = None) -> Any:
        s = self.get_or_create(session_id)
        return s.memory.get(key, default)

