from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    """
    Ensure `import app...` works regardless of where pytest is invoked from.

    When running from the repo root, `Session4/` isn't automatically on sys.path,
    which can cause `ModuleNotFoundError: app`.
    """
    session4_dir = Path(__file__).resolve().parents[1]
    session4_dir_str = str(session4_dir)
    if session4_dir_str not in sys.path:
        sys.path.insert(0, session4_dir_str)

