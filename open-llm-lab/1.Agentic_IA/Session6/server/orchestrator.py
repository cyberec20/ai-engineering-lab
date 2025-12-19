from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .config import AppConfig
from .llm_client import LLMClient
from .mt5_bridge import MT5Bridge
from .nodes.market_reader import run_market_reader
from .nodes.tech_analysis import run_tech_analysis
from .nodes.risk_guard import RiskPolicies, run_risk_guard
from .nodes.final_decider import run_final_decider
from .nodes.explainer import run_explainer
from .nodes.base import NodeResult
from .schemas import DeskEvaluateRequest, DeskEvaluateResponse, MarketSnapshot, NodeOutput
from .tracing import build_callbacks

logger = logging.getLogger(__name__)


class DeskState(TypedDict, total=False):
    request: DeskEvaluateRequest
    snapshot: MarketSnapshot
    market_reader: dict
    tech_analysis: dict
    risk_guard: dict
    final_decider: dict
    explainer: Any
    node_outputs: list[NodeOutput]
    _allow_deep: bool
    _gate_reasons: list[str]


_DECISION_CACHE: OrderedDict[str, DeskEvaluateResponse] = OrderedDict()


def _cache_key(snapshot: MarketSnapshot, request: DeskEvaluateRequest) -> str:
    return f"{request.symbol}|{request.timeframe}|{snapshot.ts.isoformat()}"


def _cache_lookup(key: str) -> DeskEvaluateResponse | None:
    cached = _DECISION_CACHE.get(key)
    if cached:
        _DECISION_CACHE.move_to_end(key)
        return cached.model_copy(deep=True)
    return None


def _cache_store(key: str, response: DeskEvaluateResponse, limit: int) -> None:
    _DECISION_CACHE[key] = response.model_copy(deep=True)
    _DECISION_CACHE.move_to_end(key)
    while len(_DECISION_CACHE) > max(1, limit):
        _DECISION_CACHE.popitem(last=False)


def _evaluate_gate(snapshot: MarketSnapshot, config: AppConfig) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    spread = snapshot.ask - snapshot.bid
    if spread > config.gate_max_spread:
        reasons.append(f"spread {spread:.3f} > {config.gate_max_spread}")
    ohlc = snapshot.ohlc or {}
    high = ohlc.get("high", snapshot.bid)
    low = ohlc.get("low", snapshot.bid)
    rng = high - low
    if rng < config.gate_min_range:
        reasons.append(f"range {rng:.3f} < {config.gate_min_range}")
    body = abs(ohlc.get("close", snapshot.bid) - ohlc.get("open", snapshot.bid))
    if body < config.gate_min_body:
        reasons.append(f"body {body:.3f} < {config.gate_min_body}")
    tick_delta = abs(snapshot.bid - ohlc.get("close", snapshot.bid))
    if tick_delta > config.gate_max_ohlc_delta:
        reasons.append(f"tick delta {tick_delta:.3f} > {config.gate_max_ohlc_delta}")
    allow = not reasons
    return allow, reasons


def build_graph(config: AppConfig, bridge: MT5Bridge) -> StateGraph:
    llm = LLMClient(config)

    graph = StateGraph(DeskState)
    policies = RiskPolicies(
        max_spread=config.gate_max_spread,
        min_range=config.gate_min_range,
        max_ohlc_delta=config.gate_max_ohlc_delta,
        min_body=config.gate_min_body,
    )

    def _log(stage: str, **payload: Any) -> None:
        if config.debug_internal:
            logger.info("stage=%s data=%s", stage, payload)

    def _append_output(state: DeskState, result, model_name: str) -> None:
        outputs = state.setdefault("node_outputs", [])
        outputs.append(
            NodeOutput(
                name=result.name,
                model=model_name,
                latency_ms=result.latency_ms,
                summary=result.summary,
                raw=result.content,
            )
        )

    def market_reader_node(state: DeskState) -> DeskState:
        _log("market_reader.start")
        snapshot = state.get("snapshot")
        if snapshot is None:
            snapshot = bridge.latest(state["request"].symbol, state["request"].timeframe)
            if not snapshot:
                raise RuntimeError("No market data available")
            state["snapshot"] = snapshot
        result = run_market_reader(llm, config.model_market_reader, snapshot)
        _append_output(state, result, config.model_market_reader)
        state["market_reader"] = result.content
        if "_allow_deep" not in state:
            allow, reasons = _evaluate_gate(snapshot, config)
            state["_gate_reasons"] = reasons
            if config.enable_gating:
                state["_allow_deep"] = allow
                if reasons:
                    _log("gating.triggered", reasons=reasons)
            else:
                state["_allow_deep"] = True
                if reasons:
                    _log("gating.warning", reasons=reasons)
        _log("market_reader.done", latency_ms=result.latency_ms)
        return state

    def tech_node(state: DeskState) -> DeskState:
        _log("tech_analysis.start")
        if config.enable_gating and not state.get("_allow_deep", True):
            reason = "; ".join(state.get("_gate_reasons", [])) or "gated"
            result = NodeResult("tech_analysis", {"skipped": True, "reason": reason}, reason, 0)
        else:
            result = run_tech_analysis(llm, config.model_tech_analysis, state.get("market_reader", {}))
        _append_output(state, result, config.model_tech_analysis)
        state["tech_analysis"] = result.content
        _log("tech_analysis.done", latency_ms=result.latency_ms)
        return state

    def risk_node(state: DeskState) -> DeskState:
        _log("risk_guard.start")
        snapshot = state.get("snapshot")
        if not snapshot:
            raise RuntimeError("snapshot missing for risk guard")
        result = run_risk_guard(
            snapshot,
            policies,
            state.get("_gate_reasons", []),
            state.get("tech_analysis", {}).get("signals") if isinstance(state.get("tech_analysis"), dict) else None,
            config.enable_gating,
        )
        model_name = config.model_risk_guard or "rule_guard"
        _append_output(state, result, model_name)
        state["risk_guard"] = result.content
        _log("risk_guard.done", latency_ms=result.latency_ms)
        return state

    def final_node(state: DeskState) -> DeskState:
        _log("final_decider.start")
        run_deep = state.get("_allow_deep", True)
        risk_data = state.get("risk_guard", {}) or {}
        gating_block = config.enable_gating and not run_deep
        risk_block = not risk_data.get("allowed", True)
        if gating_block or risk_block:
            reasons = []
            if gating_block:
                reasons.extend(state.get("_gate_reasons", []))
            if risk_block:
                reasons.extend(risk_data.get("violations", []))
            payload = {"decision": "WAIT", "reasons": reasons}
            result = NodeResult("final_decider", payload, "WAIT", 0)
        else:
            result = run_final_decider(
                llm,
                config.model_final_decider,
                state.get("market_reader", {}),
                state.get("tech_analysis", {}),
                risk_data,
            )
        _append_output(state, result, config.model_final_decider)
        state["final_decider"] = result.content
        _log("final_decider.done", latency_ms=result.latency_ms)
        return state

    def explainer_node(state: DeskState) -> DeskState:
        _log("explainer.start")
        if config.enable_gating and not state.get("_allow_deep", True):
            result = NodeResult("explainer", {"narrative": "Skipped due to gating."}, "SKIPPED", 0)
        else:
            models = [
                config.model_market_reader,
                config.model_tech_analysis,
                config.model_risk_guard or "rule_guard",
                config.model_final_decider,
                config.model_explainer,
            ]
            result = run_explainer(llm, config.model_explainer, state.get("final_decider", {}), models)
        _append_output(state, result, config.model_explainer)
        state["explainer"] = result.content
        _log("explainer.done", latency_ms=result.latency_ms)
        return state

    graph.add_node("market_reader", market_reader_node)
    graph.add_node("tech_analysis", tech_node)
    graph.add_node("risk_guard", risk_node)
    graph.add_node("final_decider", final_node)
    graph.add_node("explainer", explainer_node)

    graph.set_entry_point("market_reader")
    graph.add_edge("market_reader", "tech_analysis")
    graph.add_edge("tech_analysis", "risk_guard")
    graph.add_edge("risk_guard", "final_decider")
    graph.add_edge("final_decider", "explainer")
    graph.add_edge("explainer", END)

    return graph


def _wait_snapshot(bridge: MT5Bridge, request: DeskEvaluateRequest, timeout: float = 5.0, step: float = 0.15):
    elapsed = 0.0
    while elapsed <= timeout:
        snap = bridge.latest(request.symbol, request.timeframe)
        if snap:
            return snap
        time.sleep(step)
        elapsed += step
    return None


def evaluate(config: AppConfig, bridge: MT5Bridge, request: DeskEvaluateRequest) -> DeskEvaluateResponse:
    snapshot = _wait_snapshot(bridge, request)
    if not snapshot:
        logger.warning("no snapshot available", extra={"symbol": request.symbol, "timeframe": request.timeframe})
        return DeskEvaluateResponse(
            decision="WAIT",
            reasons=["No market snapshot available yet."],
            market_snapshot=None,
            node_outputs=[],
            meta={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": "WAIT",
                "cached": False,
                "models_used": [],
            },
        )
    key = _cache_key(snapshot, request)
    cached = _cache_lookup(key)
    if cached:
        cached.meta["timestamp"] = datetime.now(timezone.utc).isoformat()
        cached.meta["cached"] = True
        return cached

    graph = build_graph(config, bridge).compile()
    state: DeskState = {"request": request, "snapshot": snapshot}
    callbacks = build_callbacks(config)
    run_config = {"callbacks": callbacks} if callbacks else None
    final_state = graph.invoke(state, config=run_config)
    snapshot = final_state.get("snapshot") or snapshot
    decision = final_state.get("final_decider", {})
    reasons = decision.get("reasons", []) if isinstance(decision, dict) else []
    node_outputs = final_state.get("node_outputs", [])
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision.get("decision", "WAIT") if isinstance(decision, dict) else "WAIT",
        "models_used": [
            config.model_market_reader,
            config.model_tech_analysis,
            config.model_risk_guard or "rule_guard",
            config.model_final_decider,
            config.model_explainer,
        ],
    }

    reason_texts = [reason if isinstance(reason, str) else json.dumps(reason, ensure_ascii=False) for reason in reasons]
    response = DeskEvaluateResponse(
        decision=decision.get("decision", "WAIT") if isinstance(decision, dict) else "WAIT",
        reasons=reason_texts,
        market_snapshot=snapshot,
        node_outputs=node_outputs,
        meta=meta,
    )
    _cache_store(key, response, config.decision_cache_size)
    return response
