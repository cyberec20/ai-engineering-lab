from __future__ import annotations

import re


_ws_re = re.compile(r"\s+")


def compact_whitespace(text: str) -> str:
    return _ws_re.sub(" ", text or "").strip()


def tokenize_for_overlap(text: str) -> set[str]:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", text, flags=re.IGNORECASE)
    tokens = {t for t in text.split() if len(t) >= 4}
    return tokens

