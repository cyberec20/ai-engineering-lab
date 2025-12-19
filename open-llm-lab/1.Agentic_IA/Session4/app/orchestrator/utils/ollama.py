from __future__ import annotations

from typing import Optional

import requests


def list_ollama_models(base_url: str, timeout_seconds: int = 5) -> Optional[set[str]]:
    """
    Best-effort: query local Ollama for installed models. Returns None if unreachable.
    """
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        models = {m.get("name") for m in (data.get("models") or []) if m.get("name")}
        return {m for m in models if isinstance(m, str)}
    except Exception:
        return None

