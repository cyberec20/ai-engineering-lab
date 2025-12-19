from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Optional

from langgraph.constants import END, START
from langgraph.errors import GraphInterrupt
from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from app.core.config import AppConfig
from app.orchestrator.llms.router import LLMRouter
from app.orchestrator.schemas.models import DraftAnswer, GuardVerdict, PlannerOutput
from app.orchestrator.schemas.state import ResearchState
from app.orchestrator.tools.web_tools import WebTools
from app.orchestrator.utils.ids import new_uuid
from app.orchestrator.utils.json_utils import safe_parse_json_object
from app.orchestrator.utils.lang import detect_language, extract_subject, wikipedia_lang_for
from app.orchestrator.utils.text import tokenize_for_overlap
from app.orchestrator.utils.time import now_iso


class TraceAdapterLike:
    def start_run(self, *, name: str, run_id: str, trace_id: str, inputs: dict, metadata: dict) -> None: ...

    def end_run(self, *, outputs: dict | None = None, error: str | None = None) -> None: ...

    def start_span(self, *, name: str, span_id: str, inputs: dict | None = None, metadata: dict | None = None) -> None: ...

    def end_span(self, *, span_id: str, outputs: dict | None = None, error: str | None = None, metadata: dict | None = None) -> None: ...

    def event(self, *, name: str, payload: dict | None = None) -> None: ...


def _start_step(name: str, *, details: dict | None = None) -> dict:
    step = {
        "name": name,
        "status": "OK",
        "started_at": now_iso(),
        "ended_at": None,
        "details": details or {},
    }
    return step


def _end_step(step: dict, *, status: str = "OK", details_update: dict | None = None) -> None:
    step["status"] = status
    step["ended_at"] = now_iso()
    if details_update:
        step["details"].update(details_update)


def _safe_parse(model_cls, text: str) -> Any:
    data = safe_parse_json_object(text)
    return model_cls.model_validate(data)


def _llm_json(
    deps: GraphDeps,
    *,
    role: str,
    system: str,
    user: str,
    model_cls,
    retries: int = 2,
) -> Any:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        raw = deps.llms.chat(role, system=system, user=user, json_mode=True)
        try:
            return _safe_parse(model_cls, raw)
        except Exception as e:
            last_err = e
            system = (
                system
                + "\n\nIMPORTANT: Return ONLY a single JSON object (no markdown, no extra keys). "
                + "If you are unsure, still return valid JSON matching the required schema."
            )
            user = user + f"\n\n(Attempt {attempt} failed: {e})\nReturn JSON only."
    raise last_err or ValueError("Failed to parse JSON from model output")


def _raw_excerpt(text: str, limit: int = 800) -> str:
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


def _normalize_user_message(user_message: str) -> str:
    """
    Normalize common user-typing quirks so subject extraction/search behaves predictably.
    """
    msg = (user_message or "").strip()
    if not msg:
        return msg
    msg = re.sub(r"(?i)^\s*nvestiga\b", "investiga", msg)
    return msg


def _fallback_plan_and_queries(user_message: str) -> PlannerOutput:
    question = (user_message or "").strip()
    base = question if len(question) <= 200 else question[:200]
    plan = [
        "Generate focused web search queries",
        "Search and fetch top sources",
        "Synthesize answer with citations",
        "Validate claims vs evidence (anti-hallucination)",
    ]
    # Keep queries tightly coupled to the user's topic (extract subject from imperative prompts).
    lang = detect_language(question)
    subject = extract_subject(question, lang)
    intent = _detect_intent(question, lang)
    queries = _build_queries(subject, lang, intent) or [base]
    return PlannerOutput(plan=plan, queries=[q for q in queries if q.strip()])


def _sanitize_queries(user_message: str, queries: list[str] | None) -> list[str]:
    user_tokens = tokenize_for_overlap(user_message)
    cleaned: list[str] = []
    for q in queries or []:
        q = (q or "").strip()
        if not q:
            continue
        # Remove common leading punctuation from questions to improve search.
        q = q.replace("¿", "").replace("?", "").replace("¡", "").replace("!", "").strip()
        # Drop accidental JSON/dict-like strings the model might emit.
        if "{" in q or "}" in q or q.startswith("[") or q.startswith("("):
            continue
        # Drop queries that are not related to the user's question (common when LLM returns "creative" JSON).
        q_tokens = tokenize_for_overlap(q)
        if user_tokens and len(user_tokens & q_tokens) == 0 and user_message.lower() not in q.lower():
            continue
        if len(q) > 220:
            q = q[:220]
        cleaned.append(q)
    cleaned = list(dict.fromkeys(cleaned))
    if cleaned:
        return cleaned[:5]
    return _fallback_plan_and_queries(user_message).queries[:5]


def _build_queries_from_subject(subject: str, lang: str) -> list[str]:
    subject = (subject or "").strip()
    if not subject:
        return []
    subject = subject.replace("¿", "").replace("?", "").replace("¡", "").replace("!", "").strip()
    lang = (lang or "en").split("-", 1)[0]
    if lang == "es":
        return [
            subject,
            f"{subject} wikipedia",
            f"{subject} biografía aportes",
            f"{subject} contribuciones principales",
        ]
    if lang == "it":
        return [subject, f"{subject} wikipedia", f"{subject} biografia contributi", f"{subject} contributi principali"]
    if lang == "fr":
        return [subject, f"{subject} wikipedia", f"{subject} biographie contributions", f"{subject} principales contributions"]
    if lang == "de":
        return [subject, f"{subject} wikipedia", f"{subject} biografie beiträge", f"{subject} wichtigste beiträge"]
    if lang == "pt":
        return [subject, f"{subject} wikipedia", f"{subject} biografia contribuições", f"{subject} principais contribuições"]
    return [subject, f"{subject} wikipedia", f"{subject} biography contributions", f"{subject} main contributions"]


def _detect_intent(user_message: str, lang: str) -> str:
    msg = (user_message or "").lower().strip()
    lang = (lang or "en").split("-", 1)[0]
    if lang == "es":
        if re.match(r"^(?:que|qué)\s+es\s+", msg) or "definición" in msg or "define" in msg:
            return "definition"
    if lang == "it":
        if re.match(r"^(?:cos'?è|che cos'?è)\s+", msg) or "definizione" in msg:
            return "definition"
    if lang == "fr":
        if re.match(r"^qu['’]est-ce que\s+", msg) or "définition" in msg:
            return "definition"
    if lang == "de":
        if re.match(r"^was ist\s+", msg) or "definition" in msg:
            return "definition"
    if lang == "pt":
        if re.match(r"^o que é\s+", msg) or "definição" in msg:
            return "definition"
    if re.match(r"^what is\s+", msg) or msg.startswith("define "):
        return "definition"
    return "general"


def _build_queries(subject: str, lang: str, intent: str) -> list[str]:
    subject = (subject or "").strip()
    if not subject:
        return []
    if intent == "definition":
        lang = (lang or "en").split("-", 1)[0]
        if lang == "es":
            return [
                subject,
                f"{subject} definición",
                f"{subject} wikipedia",
                f"site:wikipedia.org {subject}",
            ]
        if lang == "it":
            return [subject, f"{subject} definizione", f"{subject} wikipedia", f"site:wikipedia.org {subject}"]
        if lang == "fr":
            return [subject, f"{subject} définition", f"{subject} wikipedia", f"site:wikipedia.org {subject}"]
        if lang == "de":
            return [subject, f"{subject} definition", f"{subject} wikipedia", f"site:wikipedia.org {subject}"]
        if lang == "pt":
            return [subject, f"{subject} definição", f"{subject} wikipedia", f"site:wikipedia.org {subject}"]
        return [subject, f"{subject} definition", f"{subject} wikipedia", f"site:wikipedia.org {subject}"]

    return _build_queries_from_subject(subject, lang)


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # Remove common wiki citation markers and awkward IPA-ish parentheses early in the lead.
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\(\s*;[^)]*\)", "", text)  # e.g. "( ; 4 January ... )"
    # Remove common boilerplate from scraped pages.
    text = re.sub(r"(?i)\bskip to content\b", "", text)
    text = re.sub(r"(?i)\bcopyright\b.*?(?:\.\s|$)", "", text)
    text = re.sub(r"Â©", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Deduplicate immediate repeated sentences (common in some pages)
    if ". " in text:
        parts = text.split(". ")
        if len(parts) >= 2 and parts[0].strip() == parts[1].strip():
            text = ". ".join(parts[1:]).strip()
    for sep in [". ", ".\n", "。", "?\n", "? ", "! ", "!\n"]:
        idx = text.find(sep)
        if idx != -1 and idx > 30:
            return text[: idx + 1].strip()
    return text[:240].strip()


def _fallback_draft_from_snippets(user_message: str, snippets: dict[str, dict]) -> DraftAnswer:
    items: list[tuple[str, str, str]] = []
    for sid, s in (snippets or {}).items():
        url = (s.get("url") or "").strip()
        txt = (s.get("fetched_text") or s.get("snippet") or "").strip()
        sent = _first_sentence(txt)
        if url and sent:
            items.append((sid, url, sent))

    items = items[:5]
    if not items:
        raise ValueError("No usable snippet text for deterministic synthesis")

    key_points = []
    for i, (sid, url, sent) in enumerate(items, start=1):
        key_points.append(
            {
                "id": f"kp{i}",
                "claim": sent,
                "citations": [{"url": url, "snippet_id": sid}],
                "confidence": 0.6,
            }
        )

    final_answer = " ".join([kp["claim"] for kp in key_points])[:1200].strip()
    return DraftAnswer(
        question=(user_message or "").strip(),
        key_points=key_points,  # type: ignore[arg-type]
        final_answer=final_answer,
        limitations=["Respuesta generada de forma determinista desde los snippets obtenidos."],
        followups=["¿Quieres que busque más fuentes o profundice en algún aporte específico?"],
    )


def _translate_text(deps: GraphDeps, *, text: str, target_lang: str) -> str:
    if not text.strip():
        return text
    system = (
        f"You are a translation assistant. Translate the user's text into '{target_lang}'. "
        "Do not add or remove information. Keep it natural and fluent. "
        "Do NOT add preambles, apologies, explanations, analysis, 'thought process', or markdown. Output plain text only."
    )
    user = text
    try:
        return deps.llms.chat("planner", system=system, user=user, json_mode=False).strip()
    except Exception:
        return text


def _localize_labels(lang: str) -> dict[str, str]:
    lang = (lang or "en").split("-", 1)[0]
    if lang == "es":
        return {"key_points": "Puntos clave", "limitations": "Limitaciones"}
    if lang == "it":
        return {"key_points": "Punti chiave", "limitations": "Limitazioni"}
    if lang == "fr":
        return {"key_points": "Points clés", "limitations": "Limites"}
    if lang == "de":
        return {"key_points": "Kernaussagen", "limitations": "Einschränkungen"}
    if lang == "pt":
        return {"key_points": "Pontos-chave", "limitations": "Limitações"}
    return {"key_points": "Key points", "limitations": "Limitations"}


def _sanitize_public_text(text: str) -> str:
    """
    Remove common LLM meta/internals that must not appear in user output.
    """
    t = (text or "").strip()
    if not t:
        return t
    # Strip markdown fences and common "internal" sections.
    t = re.sub(r"```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = t.replace("```", "").strip()
    # Remove "thought process" style content (English/Spanish)
    t = re.sub(r"(?is)\b(thought process|razonamiento|cadena de pensamiento|chain of thought)\b.*$", "", t).strip()
    # Remove leading thanks/apologies that some models inject
    t = re.sub(
        r"^\s*(gracias|¡gracias|thank you|thanks|lo siento|sorry)[^\n]*\n+",
        "",
        t,
        flags=re.IGNORECASE,
    ).strip()
    # Remove obvious instruction-following meta lines
    t = re.sub(r"(?im)^\s*(ok(?:ay)?[, ]+here.*|here is the thought process.*)\s*$", "", t).strip()
    # Deduplicate repeated lines
    lines = [ln.strip() for ln in t.splitlines()]
    out_lines: list[str] = []
    for ln in lines:
        if not ln:
            out_lines.append("")
            continue
        if out_lines and out_lines[-1] == ln:
            continue
        out_lines.append(ln)
    t = "\n".join(out_lines).strip()
    return t


def _translate_bundle(
    deps: GraphDeps,
    *,
    target_lang: str,
    final_answer: str,
    key_points: list[str],
    limitations: list[str],
) -> tuple[str, list[str], list[str]]:
    """
    Translate final output in one call to reduce latency and prevent mixed-language output.
    Returns translated (final_answer, key_points, limitations). Best-effort; falls back to originals.
    """
    if not target_lang:
        return final_answer, key_points, limitations

    src_blob = "\n".join([final_answer] + key_points + limitations)
    if detect_language(src_blob) == (target_lang.split("-", 1)[0]):
        return final_answer, key_points, limitations

    class _Bundle(BaseModel):
        final_answer: str
        key_points: list[str]
        limitations: list[str]

    system = (
        f"You are a translation service. Translate the JSON fields into '{target_lang}'. "
        "Keep meaning, do not add any new information. Return ONLY valid JSON with the same keys. "
        "No extra keys, no markdown, no preamble."
    )
    payload = {
        "final_answer": final_answer,
        "key_points": key_points,
        "limitations": limitations,
    }
    user = f"INPUT JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\nReturn JSON only."
    try:
        retries = max(1, int(getattr(deps.config, "translation_retries", 1)))
        out: _Bundle = _llm_json(deps, role="planner", system=system, user=user, model_cls=_Bundle, retries=retries)
        return out.final_answer, out.key_points, out.limitations
    except Exception:
        # Fallback: translate only the main body (still sanitize)
        return _translate_text(deps, text=final_answer, target_lang=target_lang), key_points, limitations


@dataclass(frozen=True)
class GraphDeps:
    config: AppConfig
    llms: LLMRouter
    web: WebTools
    tracer: TraceAdapterLike


def build_research_operator_graph(deps: GraphDeps):
    max_iterations = deps.config.max_iterations

    def planner(state: ResearchState) -> ResearchState:
        user_msg = _normalize_user_message(state.get("user_message") or "")
        input_lang = state.get("input_language") or detect_language(user_msg)
        span_id = new_uuid()
        deps.tracer.start_span(
            name="planner",
            span_id=span_id,
            inputs={"user_message": state.get("user_message")},
            metadata={"run_id": state.get("run_id")},
        )
        step = _start_step("planner")
        try:
            if not getattr(deps.config, "enable_llm_planner", False):
                out = _fallback_plan_and_queries(user_msg)
                subj = extract_subject(user_msg, input_lang)
                out = PlannerOutput(plan=out.plan, queries=_build_queries(subj, input_lang, _detect_intent(user_msg, input_lang)))
                _end_step(step, status="WARN", details_update={"fallback": True, "queries": out.queries, "plan": out.plan})
                deps.tracer.end_span(
                    span_id=span_id,
                    outputs={"queries": out.queries, "plan": out.plan, "fallback": True},
                    metadata={"run_id": state.get("run_id")},
                )
                return {"plan": out.plan, "queries": out.queries, "input_language": input_lang, "execution_summary": [step]}

            system = (
                "You are the planner. Output strict JSON with keys: plan (list of steps), queries (list of web search queries)."
                " Keep queries short and targeted. Do not return nested objects; both plan and queries must be JSON arrays of strings."
                " Example: {\"plan\":[\"step1\"],\"queries\":[\"query1\",\"query2\"]}"
            )
            user = f"User question:\n{user_msg}\n\nReturn JSON only."
            raw_first: str | None = None
            try:
                raw_first = deps.llms.chat("planner", system=system, user=user, json_mode=True)
                out: PlannerOutput = _safe_parse(PlannerOutput, raw_first)
                _end_step(step, details_update={"queries": out.queries, "plan": out.plan})
                deps.tracer.end_span(
                    span_id=span_id,
                    outputs={"queries": out.queries, "plan": out.plan},
                    metadata={"run_id": state.get("run_id")},
                )
                return {"plan": out.plan, "queries": out.queries, "input_language": input_lang, "execution_summary": [step]}
            except Exception as first_err:
                try:
                    repair_system = (
                        "You are a JSON schema converter. Convert the INPUT into strict JSON with keys:\n"
                        "- plan: array of strings\n"
                        "- queries: array of strings\n"
                        "Return ONLY the JSON object. Do not include any other keys."
                    )
                    repair_user = (
                        "INPUT:\n"
                        f"{_raw_excerpt(raw_first or '')}\n\n"
                        f"Original question:\n{user_msg}\n\nReturn JSON only."
                    )
                    out = _llm_json(
                        deps,
                        role="planner",
                        system=repair_system,
                        user=repair_user,
                        model_cls=PlannerOutput,
                        retries=2,
                    )
                    _end_step(
                        step,
                        status="WARN",
                        details_update={
                            "repair": True,
                            "queries": out.queries,
                            "plan": out.plan,
                            "first_error": str(first_err),
                            "raw_excerpt": _raw_excerpt(raw_first or ""),
                        },
                    )
                    deps.tracer.end_span(
                        span_id=span_id,
                        outputs={"queries": out.queries, "plan": out.plan, "repair": True},
                        metadata={"run_id": state.get("run_id")},
                    )
                    return {"plan": out.plan, "queries": out.queries, "input_language": input_lang, "execution_summary": [step]}
                except Exception as repair_err:
                    out = _fallback_plan_and_queries(user_msg)
                    subj = extract_subject(user_msg, input_lang)
                    out = PlannerOutput(plan=out.plan, queries=_build_queries_from_subject(subj, input_lang))
                    _end_step(
                        step,
                        status="WARN",
                        details_update={
                            "fallback": True,
                            "queries": out.queries,
                            "plan": out.plan,
                            "first_error": str(first_err),
                            "repair_error": str(repair_err),
                            "raw_excerpt": _raw_excerpt(raw_first or ""),
                        },
                    )
                    deps.tracer.end_span(
                        span_id=span_id,
                        outputs={"queries": out.queries, "plan": out.plan, "fallback": True},
                        metadata={"run_id": state.get("run_id")},
                    )
                    return {"plan": out.plan, "queries": out.queries, "input_language": input_lang, "execution_summary": [step]}
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return {"status": "FAILED", "input_language": input_lang, "execution_summary": [step]}

    def researcher(state: ResearchState) -> ResearchState:
        span_id = new_uuid()
        deps.tracer.start_span(
            name="researcher",
            span_id=span_id,
            inputs={"queries": state.get("queries", [])},
            metadata={"run_id": state.get("run_id")},
        )
        step = _start_step("researcher")
        try:
            user_msg = _normalize_user_message(state.get("user_message") or "")
            input_lang = state.get("input_language") or detect_language(user_msg)
            subject = extract_subject(user_msg, input_lang)
            subject = subject.replace("¿", "").replace("?", "").replace("¡", "").replace("!", "").strip()
            intent = _detect_intent(user_msg, input_lang)
            base_queries = _build_queries(subject, input_lang, intent)
            planner_queries = _sanitize_queries(subject, state.get("queries"))
            max_queries = max(1, int(getattr(deps.config, "web_max_queries", 3)))
            queries = list(dict.fromkeys(base_queries + planner_queries))[:max_queries]
            wiki_lang = wikipedia_lang_for(input_lang)
            all_results: list[dict] = []
            snippets: dict[str, dict] = dict(state.get("snippets") or {})
            provider_errors: list[dict] = []
            wikipedia_direct_used = 0
            graph_mode = getattr(deps.config, "graph_mode", "fast")
            fetches_per_query = max(1, int(getattr(deps.config, "web_fetches_per_query", 1)))

            # For definitions, try the Wikipedia title directly first (most reliable).
            if intent == "definition" and subject:
                try:
                    fetched = deps.web.wikipedia_fetch(subject, lang=wiki_lang)
                    if fetched.text:
                        snippet_id = new_uuid()
                        snippets[snippet_id] = {
                            "id": snippet_id,
                            "url": fetched.url,
                            "title": fetched.title or subject,
                            "snippet": fetched.text[:240],
                            "fetched_text": fetched.text,
                        }
                        wikipedia_direct_used += 1
                except Exception as e:
                    provider_errors.append({"provider": "wikipedia_fetch_title", "query": subject, "error": str(e)})

            for q in queries:
                q_span = new_uuid()
                deps.tracer.start_span(
                    name="web_search",
                    span_id=q_span,
                    inputs={"query": q},
                    metadata={"run_id": state.get("run_id")},
                )
                try:
                    if graph_mode == "fast":
                        results = []
                        deps.tracer.end_span(
                            span_id=q_span,
                            outputs={"results": 0, "skipped": True},
                            metadata={"run_id": state.get("run_id")},
                        )
                    else:
                        results = deps.web.web_search(q)
                        deps.tracer.end_span(
                            span_id=q_span,
                            outputs={"results": len(results)},
                            metadata={"run_id": state.get("run_id")},
                        )
                except Exception as e:
                    all_results.append({"title": "", "url": "", "snippet": "", "error": str(e), "query": q})
                    deps.tracer.end_span(span_id=q_span, error=str(e), metadata={"run_id": state.get("run_id")})
                    results = []
                    provider_errors.append({"provider": "duckduckgo", "query": q, "error": str(e)})

                if not results:
                    w_span = new_uuid()
                    deps.tracer.start_span(
                        name="wikipedia_search",
                        span_id=w_span,
                        inputs={"query": q},
                        metadata={"run_id": state.get("run_id")},
                    )
                    try:
                        results = deps.web.wikipedia_search(q, lang=wiki_lang)
                        deps.tracer.end_span(
                            span_id=w_span,
                            outputs={"results": len(results)},
                            metadata={"run_id": state.get("run_id")},
                        )
                    except Exception as e:
                        all_results.append({"title": "", "url": "", "snippet": "", "error": str(e), "query": q, "provider": "wikipedia"})
                        deps.tracer.end_span(span_id=w_span, error=str(e), metadata={"run_id": state.get("run_id")})
                        provider_errors.append({"provider": "wikipedia_search", "query": q, "error": str(e)})
                        continue

                if not results:
                    f_span = new_uuid()
                    deps.tracer.start_span(
                        name="wikipedia_fetch_title",
                        span_id=f_span,
                        inputs={"title": subject or q},
                        metadata={"run_id": state.get("run_id")},
                    )
                    try:
                        title = (subject or q).strip()
                        title = title.replace("wikipedia", "").strip()
                        fetched = deps.web.wikipedia_fetch(title, lang=wiki_lang)
                        if fetched.text:
                            wikipedia_direct_used += 1
                            snippet_text = fetched.text[:240]
                            results = [
                                type(
                                    "R",
                                    (),
                                    {"title": fetched.title or q, "url": fetched.url, "snippet": snippet_text},
                                )()
                            ]
                        else:
                            provider_errors.append(
                                {"provider": "wikipedia_fetch_title", "query": title, "error": "empty_extract"}
                            )
                        deps.tracer.end_span(
                            span_id=f_span,
                            outputs={"chars": len(fetched.text or ""), "url": fetched.url},
                            metadata={"run_id": state.get("run_id")},
                        )
                    except Exception as e:
                        deps.tracer.end_span(span_id=f_span, error=str(e), metadata={"run_id": state.get("run_id")})
                        provider_errors.append({"provider": "wikipedia_fetch_title", "query": title, "error": str(e)})
                        continue

                for r in results:
                    all_results.append({"title": r.title, "url": r.url, "snippet": r.snippet})

                for r in results[:fetches_per_query]:
                    f_span = new_uuid()
                    deps.tracer.start_span(
                        name="web_fetch",
                        span_id=f_span,
                        inputs={"url": r.url},
                        metadata={"run_id": state.get("run_id")},
                    )
                    try:
                        if "wikipedia.org/wiki/" in r.url:
                            fetched = deps.web.wikipedia_fetch(r.url, lang=wiki_lang)
                        else:
                            fetched = deps.web.web_fetch(r.url)
                        snippet_id = new_uuid()
                        snippets[snippet_id] = {
                            "id": snippet_id,
                            "url": fetched.url,
                            "title": fetched.title or r.title,
                            "snippet": r.snippet,
                            "fetched_text": fetched.text,
                        }
                        deps.tracer.end_span(
                            span_id=f_span,
                            outputs={"url": fetched.url, "chars": len(fetched.text or "")},
                            metadata={"run_id": state.get("run_id")},
                        )
                    except Exception:
                        snippet_id = new_uuid()
                        snippets[snippet_id] = {
                            "id": snippet_id,
                            "url": r.url,
                            "title": r.title,
                            "snippet": r.snippet,
                            "fetched_text": None,
                        }
                        deps.tracer.end_span(
                            span_id=f_span, error="web_fetch_failed", metadata={"run_id": state.get("run_id")}
                        )

            sources = sorted({s["url"] for s in snippets.values() if s.get("url")})
            _end_step(
                step,
                details_update={
                    "snippets": len(snippets),
                    "sources": len(sources),
                    "queries_used": queries,
                    "wikipedia_direct_used": wikipedia_direct_used,
                    "provider_errors": provider_errors[:5],
                },
            )
            deps.tracer.end_span(
                span_id=span_id,
                outputs={"snippets": len(snippets), "sources": len(sources)},
                metadata={"run_id": state.get("run_id")},
            )
            if len(snippets) == 0:
                notes = (
                    "No se pudieron obtener resultados web (posible rate limit/CAPTCHA o cambios HTML). "
                    "Ajusta la consulta o aprueba HITL para continuar sin evidencia."
                )
                _end_step(step, status="WARN", details_update={"no_evidence": True, "hitl": True})
                return {
                    "status": "NEEDS_HITL",
                    "hitl_required": True,
                    "hitl_notes": notes,
                    "execution_summary": [step],
                    "web_results": all_results,
                    "snippets": snippets,
                    "sources": sources,
                }
            return {
                "web_results": all_results,
                "snippets": snippets,
                "sources": sources,
                "execution_summary": [step],
            }
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return {"status": "FAILED", "execution_summary": [step]}

    def synthesizer(state: ResearchState) -> ResearchState:
        span_id = new_uuid()
        deps.tracer.start_span(name="synthesizer", span_id=span_id, metadata={"run_id": state.get("run_id")})
        step = _start_step("synthesizer")
        try:
            snippets = state.get("snippets") or {}
            input_lang = state.get("input_language") or detect_language(state.get("user_message") or "")
            if not snippets:
                notes = "Sin evidencia web disponible para sintetizar. Se requiere HITL."
                _end_step(step, status="WARN", details_update={"no_evidence": True, "hitl": True})
                deps.tracer.end_span(
                    span_id=span_id,
                    outputs={"hitl": True, "reason": "no_evidence"},
                    metadata={"run_id": state.get("run_id")},
                )
                return {
                    "status": "NEEDS_HITL",
                    "hitl_required": True,
                    "hitl_notes": notes,
                    "execution_summary": [step],
                }

            if not getattr(deps.config, "enable_llm_synthesizer", True):
                draft = _fallback_draft_from_snippets(state.get("user_message") or "", snippets)
                _end_step(step, status="WARN", details_update={"fallback": True})
                deps.tracer.end_span(
                    span_id=span_id,
                    outputs={"key_points": len(draft.key_points), "fallback": True},
                    metadata={"run_id": state.get("run_id")},
                )
                return {"draft_answer": draft.model_dump(), "input_language": input_lang, "execution_summary": [step]}

            evidence_lines: list[str] = []
            for sid, s in list(snippets.items())[:6]:
                txt = (s.get("fetched_text") or s.get("snippet") or "")[:600]
                evidence_lines.append(f"- snippet_id={sid} url={s.get('url')}\n  text={txt}")
            evidence = "\n".join(evidence_lines) if evidence_lines else "(no evidence available)"

            system = (
                "You are the synthesizer. Produce a strict JSON object with keys: "
                "question, key_points (list of {id, claim, citations:[{url, snippet_id}], confidence}), "
                "final_answer, limitations (list), followups (list). "
                "Rules: claims must be grounded in the provided evidence; include at least one citation per key point; "
                "use snippet_id values exactly as provided. "
                f"IMPORTANT: Write all human-readable fields (question, claim, final_answer, limitations, followups) in '{input_lang}'."
            )
            user = f"Question:\n{state['user_message']}\n\nEvidence:\n{evidence}\n\nReturn JSON only."
            raw_first: str | None = None
            try:
                raw_first = deps.llms.chat("synthesizer", system=system, user=user, json_mode=True)
                draft: DraftAnswer = _safe_parse(DraftAnswer, raw_first)
            except Exception as first_err:
                if getattr(deps.config, "graph_mode", "fast") == "fast":
                    draft = _fallback_draft_from_snippets(state.get("user_message") or "", snippets)
                    _end_step(
                        step,
                        status="WARN",
                        details_update={"fallback": True, "first_error": str(first_err), "raw_excerpt": _raw_excerpt(raw_first or "")},
                    )
                    deps.tracer.end_span(
                        span_id=span_id,
                        outputs={"key_points": len(draft.key_points), "fallback": True},
                        metadata={"run_id": state.get("run_id")},
                    )
                    return {"draft_answer": draft.model_dump(), "input_language": input_lang, "execution_summary": [step]}
                try:
                    repair_system = (
                        "You are a JSON schema converter. Convert the INPUT into strict JSON with keys:\n"
                        "- question: string\n"
                        "- key_points: array of {id, claim, citations:[{url, snippet_id}], confidence}\n"
                        "- final_answer: string\n"
                        "- limitations: array of strings\n"
                        "- followups: array of strings\n"
                        "Return ONLY the JSON object. Do not include any other keys."
                    )
                    repair_user = (
                        "INPUT:\n"
                        f"{_raw_excerpt(raw_first or '')}\n\n"
                        f"Question:\n{state['user_message']}\n\n"
                        "Reminder: citations must refer to provided snippet_id and url pairs.\n\nReturn JSON only."
                    )
                    draft = _llm_json(
                        deps,
                        role="synthesizer",
                        system=repair_system,
                        user=repair_user,
                        model_cls=DraftAnswer,
                        retries=1,
                    )
                    _end_step(
                        step,
                        status="WARN",
                        details_update={"repair": True, "first_error": str(first_err), "raw_excerpt": _raw_excerpt(raw_first or "")},
                    )
                    deps.tracer.end_span(
                        span_id=span_id,
                        outputs={"key_points": len(draft.key_points), "repair": True},
                        metadata={"run_id": state.get("run_id")},
                    )
                    return {"draft_answer": draft.model_dump(), "execution_summary": [step]}
                except Exception as repair_err:
                    try:
                        draft = _fallback_draft_from_snippets(state.get("user_message") or "", dict(snippets))
                        if input_lang != "en":
                            # Translate deterministic English-ish claims into target language.
                            draft = DraftAnswer(
                                question=_translate_text(deps, text=draft.question, target_lang=input_lang),
                                key_points=[
                                    {
                                        **kp.model_dump(),
                                        "claim": _translate_text(deps, text=kp.claim, target_lang=input_lang),
                                    }
                                    for kp in draft.key_points
                                ],
                                final_answer=_translate_text(deps, text=draft.final_answer, target_lang=input_lang),
                                limitations=[
                                    _translate_text(deps, text=x, target_lang=input_lang) for x in draft.limitations
                                ],
                                followups=[_translate_text(deps, text=x, target_lang=input_lang) for x in draft.followups],
                            )
                        _end_step(
                            step,
                            status="WARN",
                            details_update={
                                "fallback": True,
                                "first_error": str(first_err),
                                "repair_error": str(repair_err),
                                "raw_excerpt": _raw_excerpt(raw_first or ""),
                            },
                        )
                        deps.tracer.end_span(
                            span_id=span_id,
                            outputs={"key_points": len(draft.key_points), "fallback": True},
                            metadata={"run_id": state.get("run_id")},
                        )
                        return {"draft_answer": draft.model_dump(), "input_language": input_lang, "execution_summary": [step]}
                    except Exception:
                        notes = (
                            "El modelo no devolvió el formato JSON requerido para la síntesis y no se pudo "
                            "construir una síntesis determinista. Se requiere HITL para continuar."
                        )
                        _end_step(
                            step,
                            status="WARN",
                            details_update={
                                "hitl": True,
                                "first_error": str(first_err),
                                "repair_error": str(repair_err),
                                "raw_excerpt": _raw_excerpt(raw_first or ""),
                            },
                        )
                        deps.tracer.end_span(
                            span_id=span_id,
                            outputs={"hitl": True, "reason": "invalid_schema"},
                            metadata={"run_id": state.get("run_id")},
                        )
                        return {
                            "status": "NEEDS_HITL",
                            "hitl_required": True,
                            "hitl_notes": notes,
                            "input_language": input_lang,
                            "execution_summary": [step],
                        }
            _end_step(step, details_update={"key_points": len(draft.key_points)})
            deps.tracer.end_span(
                span_id=span_id,
                outputs={"key_points": len(draft.key_points)},
                metadata={"run_id": state.get("run_id")},
            )
            return {"draft_answer": draft.model_dump(), "input_language": input_lang, "execution_summary": [step]}
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return {"status": "FAILED", "input_language": input_lang, "execution_summary": [step]}

    def anti_hallucination_guard(state: ResearchState) -> Command | ResearchState:
        span_id = new_uuid()
        deps.tracer.start_span(
            name="anti_hallucination_guard", span_id=span_id, metadata={"run_id": state.get("run_id")}
        )
        step = _start_step("anti_hallucination_guard")

        try:
            if not state.get("draft_answer"):
                _end_step(step, status="ERROR", details_update={"error": "missing draft_answer"})
                deps.tracer.end_span(
                    span_id=span_id, error="missing draft_answer", metadata={"run_id": state.get("run_id")}
                )
                return {"status": "FAILED", "guard_executed": True, "execution_summary": [step]}

            snippets = state.get("snippets") or {}
            draft = DraftAnswer.model_validate(state["draft_answer"])
            missing: list[str] = []
            for kp in draft.key_points:
                ok = True
                for c in kp.citations:
                    sn = snippets.get(c.snippet_id)
                    if not sn:
                        ok = False
                        continue
                    if sn.get("url") != c.url:
                        ok = False
                    claim_tokens = tokenize_for_overlap(kp.claim)
                    evidence_text = f"{sn.get('snippet','')} {sn.get('fetched_text','')}"
                    evidence_tokens = tokenize_for_overlap(evidence_text)
                    if len(claim_tokens & evidence_tokens) < 2:
                        ok = False
                if not ok:
                    missing.append(kp.id)

            rationale: str | None = None
            # Optional LLM rationale: do not override heuristics; enrich only.
            if getattr(deps.config, "enable_llm_guard_rationale", False):
                try:
                    system = (
                        "You are the anti-hallucination guard. Given key points and snippets, "
                        "return strict JSON: {supported: bool, missing_point_ids: [..], rationale: string}. "
                        "Never claim support without evidence."
                    )
                    snippets_brief = [
                        {"id": s["id"], "url": s["url"], "text": (s.get("fetched_text") or s.get("snippet") or "")[:500]}
                        for s in list(snippets.values())[:10]
                    ]
                    payload = {"key_points": draft.model_dump().get("key_points"), "snippets": snippets_brief}
                    raw = deps.llms.chat(
                        "guard",
                        system=system,
                        user=f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\nReturn JSON only.",
                        json_mode=True,
                    )
                    verdict: GuardVerdict = _safe_parse(GuardVerdict, raw)
                    rationale = verdict.rationale
                    missing = sorted(set(missing) | set(verdict.missing_point_ids))
                except Exception:
                    pass

            supported = len(missing) == 0
            details = {"supported": supported, "missing_point_ids": missing}
            if rationale:
                details["rationale"] = rationale

            if supported:
                _end_step(step, details_update=details)
                deps.tracer.end_span(span_id=span_id, outputs=details, metadata={"run_id": state.get("run_id")})
                return {"guard_executed": True, "status": "SUCCESS", "execution_summary": [step]}

            iteration = int(state.get("iteration_count") or 0)
            if iteration < max_iterations:
                iteration += 1
                # Add targeted follow-up queries for missing points
                extra_queries = [f"evidence for: {kp.claim}" for kp in draft.key_points if kp.id in missing][:3]
                queries = list(dict.fromkeys((state.get("queries") or []) + extra_queries))
                _end_step(step, status="WARN", details_update={**details, "action": "iterate", "iteration_count": iteration})
                deps.tracer.end_span(
                    span_id=span_id,
                    outputs={**details, "action": "iterate", "iteration_count": iteration},
                    metadata={"run_id": state.get("run_id")},
                )
                return Command(
                    update={
                        "guard_executed": True,
                        "iteration_count": iteration,
                        "queries": queries,
                        "execution_summary": [step],
                    },
                    goto="researcher",
                )

            hitl_notes = f"Insufficient evidence for key_points: {missing}"
            _end_step(step, status="WARN", details_update={**details, "action": "hitl"})
            deps.tracer.end_span(
                span_id=span_id, outputs={**details, "action": "hitl"}, metadata={"run_id": state.get("run_id")}
            )
            return Command(
                update={
                    "guard_executed": True,
                    "hitl_required": True,
                    "status": "NEEDS_HITL",
                    "hitl_notes": hitl_notes,
                    "execution_summary": [step],
                },
                goto="hitl",
            )
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return {"status": "FAILED", "guard_executed": True, "execution_summary": [step]}

    def reflector(state: ResearchState) -> Command | ResearchState:
        span_id = new_uuid()
        deps.tracer.start_span(name="reflector", span_id=span_id, metadata={"run_id": state.get("run_id")})
        step = _start_step("reflector")
        try:
            if state.get("status") == "FAILED":
                _end_step(step, status="ERROR", details_update={"action": "final"})
                deps.tracer.end_span(span_id=span_id, outputs={"action": "final"}, metadata={"run_id": state.get("run_id")})
                return Command(update={"execution_summary": [step]}, goto="final")

            if state.get("status") == "NEEDS_HITL" or state.get("hitl_required"):
                _end_step(step, status="WARN", details_update={"action": "hitl"})
                deps.tracer.end_span(span_id=span_id, outputs={"action": "hitl"}, metadata={"run_id": state.get("run_id")})
                return Command(update={"execution_summary": [step]}, goto="hitl")

            # Optional reflection; do not block if fails
            reflection: Optional[str] = None
            if getattr(deps.config, "enable_llm_reflector", False):
                try:
                    draft = state.get("draft_answer") or {}
                    system = "You are the reflector. Briefly state if the answer is clear and what might be missing."
                    user = f"Question: {state.get('user_message')}\nDraft JSON: {draft}\n"
                    reflection = deps.llms.chat("reflector", system=system, user=user, json_mode=False)[:500]
                except Exception:
                    reflection = None

            timestamps = dict(state.get("timestamps") or {})
            if reflection:
                timestamps["reflection"] = now_iso()
            _end_step(step, details_update={"action": "final", "reflection": reflection} if reflection else {"action": "final"})
            deps.tracer.end_span(span_id=span_id, outputs={"action": "final"}, metadata={"run_id": state.get("run_id")})
            update: dict[str, Any] = {"timestamps": timestamps, "execution_summary": [step]}
            if state.get("status") == "SUCCESS":
                update["status"] = "SUCCESS"
            return Command(update=update, goto="final")
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return Command(update={"status": "FAILED", "execution_summary": [step]}, goto="final")

    def hitl(state: ResearchState) -> ResearchState:
        span_id = new_uuid()
        deps.tracer.start_span(name="hitl", span_id=span_id, metadata={"run_id": state.get("run_id")})
        step = _start_step("hitl")
        try:
            payload = {
                "message": "Human approval required to proceed.",
                "hitl_notes": state.get("hitl_notes"),
                "sources": state.get("sources", []),
            }
            decision = interrupt(payload)
            approved = bool((decision or {}).get("approved"))
            notes = (decision or {}).get("notes")
            if not approved:
                _end_step(step, status="ERROR", details_update={"approved": False})
                deps.tracer.end_span(span_id=span_id, outputs={"approved": False}, metadata={"run_id": state.get("run_id")})
                return {"status": "FAILED", "hitl_notes": notes or state.get("hitl_notes"), "execution_summary": [step]}

            _end_step(step, details_update={"approved": True})
            deps.tracer.end_span(span_id=span_id, outputs={"approved": True}, metadata={"run_id": state.get("run_id")})
            return {
                "hitl_required": False,
                "status": "SUCCESS",
                "hitl_notes": notes or state.get("hitl_notes"),
                "execution_summary": [step],
            }
        except GraphInterrupt:
            raise
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return {"status": "FAILED", "execution_summary": [step]}

    def final(state: ResearchState) -> ResearchState:
        span_id = new_uuid()
        deps.tracer.start_span(name="final", span_id=span_id, metadata={"run_id": state.get("run_id")})
        step = _start_step("final")
        try:
            draft = None
            if state.get("draft_answer"):
                try:
                    draft = DraftAnswer.model_validate(state["draft_answer"])
                except Exception:
                    draft = None

            status = state.get("status")
            if status is None:
                status = "FAILED"

            input_lang = state.get("input_language") or detect_language(state.get("user_message") or "")
            labels = _localize_labels(input_lang)

            if status == "SUCCESS" and draft:
                raw_key_points = [kp.claim for kp in draft.key_points]
                raw_limitations = list(draft.limitations or [])
                translated_answer, translated_kps, translated_lims = _translate_bundle(
                    deps,
                    target_lang=input_lang,
                    final_answer=draft.final_answer,
                    key_points=raw_key_points,
                    limitations=raw_limitations,
                )

                citations = []
                for claim, kp in zip(translated_kps, draft.key_points, strict=False):
                    urls = sorted({c.url for c in kp.citations})
                    citations.append(f"- {_sanitize_public_text(claim)} (sources: {', '.join(urls)})")

                answer = (
                    f"{_sanitize_public_text(translated_answer)}\n\n{labels['key_points']}:\n"
                    + "\n".join(citations[:10])
                    + (
                        "\n\n"
                        + labels["limitations"]
                        + ":\n"
                        + "\n".join(f"- {_sanitize_public_text(x)}" for x in translated_lims)
                        if translated_lims
                        else ""
                    )
                ).strip()
                final_answer = answer
            elif status == "SUCCESS" and not draft:
                # Human approved, but there is no evidence-backed draft to summarize.
                final_answer = (
                    "Aprobación humana recibida, pero no hay evidencia web disponible en esta ejecución. "
                    "Para evitar alucinaciones no puedo afirmar resultados sin fuentes. "
                    "Sugerencia: reformula la consulta o aporta URLs/fragmentos en HITL."
                )
            elif status == "NEEDS_HITL":
                final_answer = "NEEDS_HITL"
            else:
                final_answer = state.get("final_answer") or "FAILED"
                status = "FAILED"

            _end_step(step, details_update={"status": status})
            deps.tracer.end_span(span_id=span_id, outputs={"status": status}, metadata={"run_id": state.get("run_id")})
            return {"final_answer": final_answer, "status": status, "execution_summary": [step]}
        except Exception as e:
            _end_step(step, status="ERROR", details_update={"error": str(e)})
            deps.tracer.end_span(span_id=span_id, error=str(e), metadata={"run_id": state.get("run_id")})
            return {"status": "FAILED", "execution_summary": [step]}

    builder = StateGraph(ResearchState)
    builder.add_node("planner", planner)
    builder.add_node("researcher", researcher)
    builder.add_node("synthesizer", synthesizer)
    builder.add_node("anti_hallucination_guard", anti_hallucination_guard)
    builder.add_node("reflector", reflector)
    builder.add_node("hitl", hitl)
    builder.add_node("final", final)

    builder.add_edge(START, "planner")
    def _route_after_planner(state: ResearchState) -> str:
        return "final" if state.get("status") == "FAILED" else "researcher"

    def _route_after_synth(state: ResearchState) -> str:
        return "final" if state.get("status") == "FAILED" else "anti_hallucination_guard"

    builder.add_conditional_edges("planner", _route_after_planner, {"researcher": "researcher", "final": "final"})

    def _route_after_researcher(state: ResearchState) -> str:
        if state.get("status") == "FAILED":
            return "final"
        if state.get("status") == "NEEDS_HITL" or state.get("hitl_required"):
            return "hitl"
        return "synthesizer"

    builder.add_conditional_edges(
        "researcher",
        _route_after_researcher,
        {"synthesizer": "synthesizer", "hitl": "hitl", "final": "final"},
    )

    def _route_after_synth(state: ResearchState) -> str:
        if state.get("status") == "FAILED":
            return "final"
        if state.get("status") == "NEEDS_HITL" or state.get("hitl_required"):
            return "hitl"
        return "anti_hallucination_guard"

    builder.add_conditional_edges(
        "synthesizer",
        _route_after_synth,
        {"anti_hallucination_guard": "anti_hallucination_guard", "hitl": "hitl", "final": "final"},
    )
    builder.add_edge("anti_hallucination_guard", "reflector")
    builder.add_edge("hitl", "final")
    builder.add_edge("final", END)

    return builder
