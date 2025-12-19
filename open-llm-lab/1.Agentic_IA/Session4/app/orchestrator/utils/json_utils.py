from __future__ import annotations

import json
import re
from typing import Any


def safe_json_loads(text: str) -> Any:
    """
    Parse JSON from an LLM output that may include leading/trailing whitespace.
    Raises ValueError if parsing fails.
    """
    return json.loads((text or "").strip())


_fence_re = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_first_json_object(text: str) -> str:
    """
    Best-effort extraction of a JSON object from messy LLM output.
    """
    s = (text or "").strip()
    s = _fence_re.sub("", s).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in text")
    return s[start : end + 1]


def safe_parse_json_object(text: str) -> Any:
    """
    Try strict parse, then try extracting first JSON object from the text.
    """
    try:
        return safe_json_loads(text)
    except Exception:
        return safe_json_loads(extract_first_json_object(text))
