from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    memory: dict[str, Any] = field(default_factory=dict)


class SessionStore:
    def __init__(self, *, ttl_seconds: int, max_sessions: int) -> None:
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._sessions: dict[str, SessionState] = {}

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    def get_or_create(self, session_id: str) -> SessionState:
        self._gc()
        st = self._sessions.get(session_id)
        if st is None:
            st = SessionState(session_id=session_id)
            self._sessions[session_id] = st
        st.updated_at = time.time()
        return st

    def set(self, session_id: str, key: str, value: Any) -> None:
        st = self.get_or_create(session_id)
        st.memory[key] = value
        st.updated_at = time.time()

    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        st = self.get_or_create(session_id)
        return st.memory.get(key, default)

    def _gc(self) -> None:
        now = time.time()
        expired = [sid for sid, st in self._sessions.items() if (now - st.updated_at) > self._ttl]
        for sid in expired:
            self._sessions.pop(sid, None)
        if len(self._sessions) > self._max:
            ordered = sorted(self._sessions.values(), key=lambda s: s.updated_at)
            for st in ordered[: max(0, len(self._sessions) - self._max)]:
                self._sessions.pop(st.session_id, None)

