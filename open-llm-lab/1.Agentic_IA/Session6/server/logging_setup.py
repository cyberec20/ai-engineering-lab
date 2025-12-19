from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AppConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if isinstance(record.args, dict):
            payload.update(record.args)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(config: AppConfig) -> None:
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(logs_dir / "runtime.jsonl", encoding="utf-8")
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, config.log_level, logging.INFO))

    if config.debug_internal:
        console = logging.StreamHandler()
        console.setFormatter(JsonFormatter())
        root.addHandler(console)
