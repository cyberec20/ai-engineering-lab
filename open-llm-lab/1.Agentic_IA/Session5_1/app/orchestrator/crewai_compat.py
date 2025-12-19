from __future__ import annotations

import signal


def patch_signals_for_windows() -> None:
    """CrewAI 1.7.0 imports Unix-only signals; patch missing ones on Windows.

    This is safe for our use because we don't rely on Unix job-control signals.
    """

    fallback = getattr(signal, "SIGTERM", 15)
    for name in [
        "SIGHUP",
        "SIGQUIT",
        "SIGUSR1",
        "SIGUSR2",
        "SIGTSTP",
        "SIGTTIN",
        "SIGTTOU",
        "SIGCONT",
        "SIGPIPE",
    ]:
        if not hasattr(signal, name):
            setattr(signal, name, fallback)

