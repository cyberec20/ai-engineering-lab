from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .base import NodeResult


@dataclass
class RiskPolicies:
    max_spread: float
    min_range: float
    max_ohlc_delta: float
    min_body: float


def _partition_reasons(gating_reasons: list[str], gating_enabled: bool) -> tuple[list[str], list[str]]:
    if gating_enabled:
        return gating_reasons, []
    return [], gating_reasons


def run_risk_guard(
    snapshot,
    policies: RiskPolicies,
    gating_reasons: list[str],
    signals: Iterable | None,
    gating_enabled: bool,
) -> NodeResult:
    violations, warnings = _partition_reasons(gating_reasons, gating_enabled)
    if signals is None:
        violations.append("missing technical signals")
    allowed = not violations
    payload = {
        "allowed": allowed,
        "violations": violations,
        "warnings": warnings,
        "snapshot_ts": snapshot.ts.isoformat(),
    }
    summary = "ALLOW" if allowed else "BLOCK"
    return NodeResult("risk_guard", payload, summary, 0)
