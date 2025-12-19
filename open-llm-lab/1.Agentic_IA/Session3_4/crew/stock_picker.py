# crew/stock_picker.py

"""
Flujo "Stock Picker" educativo para la Sesi\u00f3n 3.4.

Cambios clave:
- RAG persistente (pgvector): el Researcher ingesta/lee; Analyst y Judge reciben docs recuperados; Coder/Writer no leen RAG.
- Coder cuantitativo: yfinance (2 a\u00f1os por defecto, modo largo 5 a\u00f1os), split 70/30, forecast 60-90 d\u00edas,
  modelos ARIMA/SARIMAX, GARCH y Prophet; PNG en charts/<ticker>/.
- PDF final: el Judge entrega informe en PDF con gr\u00e1ficas; las im\u00e1genes temporales se borran al final.
- Respuesta /stocks-rag: mensaje corto + ruta PDF; debug solo en la respuesta textual (no en el PDF).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta, timezone

import requests

from llm_client_local import call_llm_local
from crew.config_loader import get_api_key
from crew.rag_store import ensure_schema, ingest_documents, query_similar
from crew.coder import run_coder, CoderResult, ModelResult
from crew.pdf_report import create_pdf_report


BASE_DIR = Path(__file__).resolve().parent
CHARTS_ROOT = str(BASE_DIR / "charts")
REPORTS_ROOT = str(BASE_DIR / "reports")


# =========================
# 1) Capa de datos - APIs num\u00e9ricas
# =========================


def _get_api_key_fmp() -> str | None:
    return get_api_key("fmp", env_var="FMP_API_KEY")


def _get_api_key_alpha() -> str | None:
    return get_api_key("alpha_vantage", env_var="ALPHAVANTAGE_API_KEY")


def _get_api_key_finnhub() -> str | None:
    return get_api_key("finnhub", env_var="FINNHUB_API_KEY")


def _fetch_fmp_profile_and_metrics(ticker: str) -> Dict[str, Any]:
    api_key = _get_api_key_fmp()
    if not api_key:
        return {"warning": "FMP_API_KEY no est\u00e1 configurada; se omiten datos de FMP."}

    base = "https://financialmodelingprep.com/api/v3"
    out: Dict[str, Any] = {}

    # Profile
    try:
        url_profile = f"{base}/profile/{ticker}?apikey={api_key}"
        r = requests.get(url_profile, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            prof = data[0]
            out["companyName"] = prof.get("companyName")
            out["sector"] = prof.get("sector")
            out["industry"] = prof.get("industry")
            out["country"] = prof.get("country")
            out["mktCap"] = prof.get("mktCap")
            out["beta"] = prof.get("beta")
            out["ipoDate"] = prof.get("ipoDate")
            out["description"] = prof.get("description") or prof.get("descriptionEs")
        else:
            out["warning"] = "No se encontr\u00f3 profile en FMP."
    except Exception as exc:
        out["warning"] = f"Error al consultar profile FMP: {exc}."

    # Key metrics
    try:
        url_metrics = f"{base}/key-metrics/{ticker}?limit=1&apikey={api_key}"
        r = requests.get(url_metrics, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            km = data[0]
            out["pe_ratio"] = km.get("peRatio")
            out["pb_ratio"] = km.get("pbRatio")
            out["dividend_yield"] = km.get("dividendYield")
        else:
            out.setdefault("warning", "")
            out["warning"] += " No se encontr\u00f3 key-metrics en FMP."
    except Exception as exc:
        out.setdefault("warning", "")
        out["warning"] += f" Error al consultar key-metrics FMP: {exc}."

    return out


def _fetch_alpha_timeseries_summary(ticker: str) -> Dict[str, Any]:
    api_key = _get_api_key_alpha()
    if not api_key:
        return {"warning": "ALPHAVANTAGE_API_KEY no est\u00e1 configurada; se omiten datos de Alpha Vantage."}

    url = (
        "https://www.alphavantage.co/query"
        f"?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize=compact&apikey={api_key}"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        return {"warning": f"Error al consultar Alpha Vantage para {ticker}: {exc}"}

    if isinstance(data, dict) and data.get("Information"):
        return {"warning": f"Alpha Vantage devolvi\u00f3 Information/premium para {ticker}: {data.get('Information')}"}

    ts = data.get("Time Series (Daily)")
    if not isinstance(ts, dict):
        return {"warning": f"No se encontr\u00f3 'Time Series (Daily)' en Alpha Vantage para {ticker}."}

    dates = sorted(ts.keys(), reverse=True)
    if not dates:
        return {"warning": f"No hay datos de fechas en Alpha Vantage para {ticker}."}

    latest_date = dates[0]
    latest_data = ts[latest_date]
    close_latest = float(latest_data.get("4. close", "0") or 0.0)

    closes: List[float] = []
    for d in dates:
        try:
            closes.append(float(ts[d].get("4. close", "0") or 0.0))
        except Exception:
            continue

    if not closes:
        return {"warning": f"No se pudieron extraer precios de cierre en Alpha Vantage para {ticker}."}

    return {
        "latest_date": latest_date,
        "latest_close": close_latest,
        "max_close_window": max(closes),
        "min_close_window": min(closes),
    }


def _fetch_finnhub_quote(ticker: str) -> Dict[str, Any]:
    api_key = _get_api_key_finnhub()
    if not api_key:
        return {"warning": "FINNHUB_API_KEY no est\u00e1 configurada; se omiten datos de Finnhub /quote."}
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json() or {}
    except Exception as exc:
        return {"warning": f"Error al consultar Finnhub /quote para {ticker}: {exc}"}

    c = data.get("c")
    if c in (0, None):
        return {"warning": f"Finnhub /quote no devolvi\u00f3 precios v\u00e1lidos para {ticker}."}

    return {
        "current": data.get("c"),
        "change": data.get("d"),
        "change_pct": data.get("dp"),
        "high_day": data.get("h"),
        "low_day": data.get("l"),
        "open_day": data.get("o"),
        "prev_close": data.get("pc"),
    }


def _fetch_finnhub_earnings_calendar(ticker: str, days_ahead: int = 45) -> Dict[str, Any]:
    api_key = _get_api_key_finnhub()
    if not api_key:
        return {"warning": "FINNHUB_API_KEY no est\u00e1 configurada; se omite calendario de earnings."}

    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=days_ahead)
    url = (
        "https://finnhub.io/api/v1/calendar/earnings"
        f"?from={today.isoformat()}&to={end.isoformat()}&symbol={ticker}&token={api_key}"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json() or {}
    except Exception as exc:
        return {"warning": f"Error al consultar calendario de earnings para {ticker}: {exc}"}

    earnings = data.get("earningsCalendar") or []
    if not isinstance(earnings, list) or not earnings:
        return {"warning": f"No se encontraron earnings pr\u00f3ximos para {ticker}."}

    first = earnings[0]
    return {
        "next_report_date": first.get("date"),
        "eps_estimate": first.get("epsEstimate"),
        "revenue_estimate": first.get("revenueEstimate"),
        "time": first.get("time"),
    }


def _fetch_finnhub_news(ticker: str, days: int = 7, max_items: int = 5) -> List[Dict[str, Any]]:
    api_key = _get_api_key_finnhub()
    if not api_key:
        return []

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days)
    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={ticker}&from={start.isoformat()}&to={today.isoformat()}&token={api_key}"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    news_items: List[Dict[str, Any]] = []
    for item in data[:max_items]:
        title = item.get("headline") or item.get("title")
        summary = item.get("summary") or ""
        url_item = item.get("url") or ""
        date_ts = item.get("datetime")
        news_items.append(
            {"title": title, "summary": summary, "url": url_item, "datetime": date_ts}
        )
    return news_items


def _fetch_finnhub_profile_basic(ticker: str) -> Dict[str, Any]:
    api_key = _get_api_key_finnhub()
    if not api_key:
        return {}
    url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={api_key}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json() or {}
        if not isinstance(data, dict) or not data.get("ticker"):
            return {}
        return data
    except Exception:
        return {}


# =========================
# 2) Snapshots y RAG
# =========================


def _build_snapshot_text(ticker: str) -> Tuple[str, Dict[str, Any]]:
    ticker = ticker.upper()

    fmp_data = _fetch_fmp_profile_and_metrics(ticker)
    alpha_data = _fetch_alpha_timeseries_summary(ticker)
    finnhub_quote = _fetch_finnhub_quote(ticker)
    finnhub_earnings = _fetch_finnhub_earnings_calendar(ticker)

    raw = {
        "fmp": fmp_data,
        "alpha": alpha_data,
        "finnhub_quote": finnhub_quote,
        "finnhub_earnings": finnhub_earnings,
    }

    lines: List[str] = [f"=== SNAPSHOT PARA {ticker} ==="]

    # FMP
    if "warning" in fmp_data:
        lines.append(f"[FMP WARNING] {fmp_data['warning']}")
        fallback_profile = _fetch_finnhub_profile_basic(ticker)
        if fallback_profile:
            lines.append(f"[FALLBACK FINNHUB] Perfil b\u00e1sico para {ticker}:")
            lines.append(
                f"Sector: {fallback_profile.get('sector')} | "
                f"Industria: {fallback_profile.get('finnhubIndustry')} | "
                f"Market Cap: {fallback_profile.get('marketCapitalization')}"
            )
            if fallback_profile.get("ipo"):
                lines.append(f"IPO date: {fallback_profile.get('ipo')}")
            if fallback_profile.get("name"):
                lines.append(f"Nombre: {fallback_profile.get('name')}")
    else:
        lines.append(f"Nombre: {fmp_data.get('companyName')}")
        lines.append(
            f"Pa\u00eds: {fmp_data.get('country')} | Sector: {fmp_data.get('sector')} | "
            f"Industria: {fmp_data.get('industry')}"
        )
        lines.append(f"Market Cap: {fmp_data.get('mktCap')}")
        lines.append(f"Beta: {fmp_data.get('beta')}")
        lines.append(f"IPO date: {fmp_data.get('ipoDate')}")
        lines.append(
            f"PE Ratio: {fmp_data.get('pe_ratio')} | PB Ratio: {fmp_data.get('pb_ratio')} "
            f"| Dividend Yield: {fmp_data.get('dividend_yield')}"
        )

    # Alpha Vantage (free TIME_SERIES_DAILY)
    if "warning" in alpha_data:
        lines.append(f"[ALPHA WARNING] {alpha_data['warning']}")
    else:
        lines.append(
            "Alpha Vantage (TIME_SERIES_DAILY): "
            f"\u00daltima fecha: {alpha_data.get('latest_date')}, "
            f"Cierre: {alpha_data.get('latest_close')}, "
            f"M\u00e1x ventana: {alpha_data.get('max_close_window')}, "
            f"M\u00edn ventana: {alpha_data.get('min_close_window')}"
        )

    # Finnhub /quote
    if "warning" in finnhub_quote:
        lines.append(f"[FINNHUB WARNING] {finnhub_quote['warning']}")
    else:
        lines.append(
            "Finnhub /quote: "
            f"Precio actual: {finnhub_quote.get('current')}, "
            f"Cambio: {finnhub_quote.get('change')} "
            f"({finnhub_quote.get('change_pct')}%), "
            f"M\u00e1x d\u00eda: {finnhub_quote.get('high_day')}, "
            f"M\u00edn d\u00eda: {finnhub_quote.get('low_day')}, "
            f"Apertura: {finnhub_quote.get('open_day')}, "
            f"Cierre previo: {finnhub_quote.get('prev_close')}"
        )

    # Finnhub calendario
    if "warning" in finnhub_earnings:
        lines.append(f"[FINNHUB CAL WARNING] {finnhub_earnings['warning']}")
    else:
        lines.append(
            "Finnhub calendario (earnings pr\u00f3ximos): "
            f"Fecha: {finnhub_earnings.get('next_report_date')}, "
            f"EPS est.: {finnhub_earnings.get('eps_estimate')}, "
            f"Ingresos est.: {finnhub_earnings.get('revenue_estimate')}, "
            f"Momento: {finnhub_earnings.get('time')}"
        )

    snapshot_text = "\n".join(lines)
    return snapshot_text, raw


def _build_rag_docs_for_ticker(ticker: str) -> List[str]:
    ticker = ticker.upper()
    docs: List[str] = []

    fmp_data = _fetch_fmp_profile_and_metrics(ticker)
    desc = fmp_data.get("description")
    if desc:
        docs.append(f"[FMP DESCRIPTION] {ticker}\n{desc}")

    news_items = _fetch_finnhub_news(ticker, days=10, max_items=5)
    for idx, item in enumerate(news_items, start=1):
        title = item.get("title") or "(sin t\u00edtulo)"
        summary = item.get("summary") or ""
        url = item.get("url") or ""
        doc = (
            f"[FINNHUB NEWS] {ticker} - Noticia {idx}\n"
            f"T\u00edtulo: {title}\n"
            f"Resumen: {summary}\n"
            f"URL: {url}\n"
        )
        docs.append(doc)

    cal = _fetch_finnhub_earnings_calendar(ticker)
    if cal and "warning" not in cal and cal.get("next_report_date"):
        docs.append(
            f"[FINNHUB EARNINGS] {ticker}\n"
            f"Pr\u00f3ximo reporte: {cal.get('next_report_date')} ({cal.get('time')})\n"
            f"EPS estimado: {cal.get('eps_estimate')}\n"
            f"Ingresos estimados: {cal.get('revenue_estimate')}\n"
        )

    return docs


def _ingest_and_retrieve_persistent(
    tickers: List[str],
    rag_docs_by_ticker: Dict[str, List[str]],
    risk_profile: str,
    horizon: str,
    top_k: int = 5,
) -> Tuple[Dict[str, List[str]], List[str]]:
    warnings: List[str] = []
    try:
        ensure_schema()
    except Exception as exc:
        warnings.append(f"[RAG_PERSIST] No se pudo asegurar el esquema pgvector: {exc}")
        return {}, warnings

    docs = []
    for t in tickers:
        for doc in rag_docs_by_ticker.get(t, []):
            docs.append({"ticker": t, "content": doc})

    try:
        ingest_documents(docs)
    except Exception as exc:
        warnings.append(f"[RAG_PERSIST] Fall\u00f3 la ingesta en pgvector: {exc}")
        return {}, warnings

    retrieved: Dict[str, List[str]] = {}
    for t in tickers:
        query = f"Contexto reciente para {t} (riesgo {risk_profile}, horizonte {horizon})"
        try:
            rows = query_similar(ticker=t, query=query, k=top_k)
            if rows:
                retrieved[t] = rows
        except Exception as exc:
            warnings.append(f"[RAG_PERSIST] Fall\u00f3 la recuperaci\u00f3n para {t}: {exc}")
            continue
    return retrieved, warnings


# =========================
# 3) Prompts LLM
# =========================


RESEARCHER_SYSTEM = """
Eres el Researcher. Usas datos de APIs y RAG persistente (pgvector).
Acceso a RAG: s\u00ed. Coder/Writer no usan RAG.
Responsable de sintetizar fundamentals, contexto y advertencias por ticker.
"""

ANALYST_SYSTEM = """
Eres el Analyst multimodal. Usas RAG + resultados cuant del Coder.
Acceso a RAG: sí. Usa imágenes y métricas para escenarios y riesgos.
Puedes ver las gráficas generadas por el Coder (rutas de imágenes incluidas en el contexto) y debes usarlas.
No des recomendaciones de compra/venta.
"""

WRITER_SYSTEM = """
Eres el Writer. Redactas informe claro en español neutro usando el texto del Analyst.
No consultas RAG directamente. No das recomendaciones de compra/venta.
Si el Analyst repite secciones (riesgos, notas finales, acciones), elimina duplicados y deja una sola versión coherente. Agrupa los puntos en la sección correcta.
"""

JUDGE_SYSTEM = """
Eres el Judge. Revisas tono/coherencia, agregas breve resumen ejecutivo y "cosas a vigilar".
Acceso a RAG: sí. No incluyas debug en la salida. No des recomendaciones de compra/venta. Si detectas duplicación o formato confuso, corrígelo y devuelve una versión deduplicada y clara.
"""


# =========================
# 4) Ejecuci\u00f3n de agentes
# =========================


def _run_researcher(
    tickers: List[str],
    risk_profile: str,
    horizon: str,
    snapshots_by_ticker: Dict[str, str],
    rag_docs_by_ticker: Optional[Dict[str, List[str]]] = None,
    persistent_docs_by_ticker: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, str]:
    context_lines: List[str] = []
    for t in tickers:
        context_lines.append(f"### {t} - Snapshot num\u00e9rico")
        context_lines.append(snapshots_by_ticker[t])
        if rag_docs_by_ticker and rag_docs_by_ticker.get(t):
            context_lines.append(f"### {t} - Documentos RAG recientes")
            context_lines.extend(rag_docs_by_ticker[t])
        if persistent_docs_by_ticker and persistent_docs_by_ticker.get(t):
            context_lines.append(f"### {t} - Documentos persistentes (pgvector)")
            context_lines.extend(persistent_docs_by_ticker[t])
        context_lines.append("")

    user_prompt = f"""
Perfil del inversor:
- Perfil de riesgo: {risk_profile}
- Horizonte temporal: {horizon}

Analiza cada ticker usando snapshots + RAG y entrega un resumen estructurado por ticker.
Incluye perfil, fundamentales clave, eventos recientes, riesgos y advertencias de datos.
"""

    messages = [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {"role": "user", "content": user_prompt + "\n\n" + "\n".join(context_lines)},
    ]

    resp = call_llm_local(
        model="deepseek-r1:8b",
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )
    text = (resp or "").strip()
    return {"ALL": text, "_context": "\n".join(context_lines)}


def _format_coder_context(coder_results: Dict[str, CoderResult]) -> str:
    lines: List[str] = []
    for t, res in coder_results.items():
        lines.append(f"### {t} - Resultados cuant (Coder)")
        if res.warnings:
            for w in res.warnings:
                lines.append(f"[WARN] {w}")
        if not res.models:
            lines.append("Sin modelos v?lidos.")
            lines.append("")
            continue
        for m in res.models:
            if m.summary:
                lines.append(f"- {m.name}: {m.summary}")
            if m.metrics:
                metrics_str = ", ".join(f"{k}={v:.3f}" for k, v in m.metrics.items() if isinstance(v, (int, float, float)))
                if metrics_str:
                    lines.append(f"  M?tricas: {metrics_str}")
            if getattr(m, 'image_paths', None):
                lines.append("  Im?genes:")
                for pth in m.image_paths:
                    lines.append(f"    - {pth}")
            if m.warnings:
                for w in m.warnings:
                    lines.append(f"  [WARN] {w}")
        lines.append("")
    return "\n".join(lines).strip()



def _run_analyst(
    researcher_summary: Dict[str, str],
    risk_profile: str,
    horizon: str,
    coder_context: str,
) -> str:
    researcher_text = researcher_summary.get("ALL", "")
    researcher_context = researcher_summary.get("_context", "")

    user_prompt = f"""
Perfil del inversor:
- Perfil de riesgo: {risk_profile}
- Horizonte temporal: {horizon}

Resumen del Researcher:
{researcher_text}

Resultados cuant (Coder):
{coder_context}

Contexto base (snapshots + RAG) para validar:
{researcher_context}

Analiza pros/contras/riesgos por ticker, integra las se\u00f1ales cuantitativas y el contexto RAG.
No des recomendaciones de compra/venta.
"""

    messages = [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    resp = call_llm_local(
        model="ministral-3:8b",
        messages=messages,
        temperature=0.35,
        max_tokens=2200,
    )
    return (resp or "").strip()


def _run_writer(
    analyst_text: str,
    risk_profile: str,
    horizon: str,
    context: str = "",
) -> str:
    user_prompt = f"""
El Analyst produjo este an\u00e1lisis:
{analyst_text}

Redacta un informe final claro en espa\u00f1ol neutro:
- Introducci\u00f3n breve.
- Apartado por ticker (qu\u00e9 hace, m\u00e9tricas clave resumidas, pros, contras, riesgos).
- Mini-secci\u00f3n de encaje con el perfil ({risk_profile}) y horizonte ({horizon}) sin recomendar compra/venta.

Contexto de referencia (snapshots + RAG):
{context}
"""

    messages = [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    resp = call_llm_local(
        model="qwen3:8b",
        messages=messages,
        temperature=0.4,
        max_tokens=2500,
    )
    return (resp or "").strip()


def _run_judge(
    final_report: str,
    context: str = "",
) -> str:
    user_prompt = f"""
Informe del Writer:
{final_report}

Tareas:
- Revisa tono/coherencia (sin promesas ni asesor\u00eda).
- A\u00f1ade 2-3 bullets de cosas a vigilar.
- Devuelve el informe ajustado completo (no incluyas debug).

Contexto base (snapshots + RAG) por si necesitas validar:
{context}
"""

    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    resp = call_llm_local(
        model="qwen2.5:7b",
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )
    return (resp or "").strip()


# =========================
# 5) Limpieza de texto para PDF
# =========================


def _dedupe_headings(text: str) -> str:
    """
    Elimina secciones duplicadas basadas en el título de heading (###, ####).
    Conserva la primera aparición de cada heading.
    """
    lines = text.split("\n")
    seen = set()
    out: List[str] = []
    skip_block = False
    current_heading = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().lower()
            if heading in seen:
                skip_block = True
                current_heading = heading
                continue
            seen.add(heading)
            skip_block = False
            current_heading = heading
            out.append(line)
        else:
            if skip_block:
                continue
            out.append(line)
    return "\n".join(out)


def _sanitize_for_pdf(text: str, max_len: int = 60) -> str:
    """
    Corta tokens largos y reemplaza NBSP para evitar errores al generar el PDF.
    """
    safe_lines: List[str] = []
    for raw_line in text.split("\n"):
        raw_line = raw_line.replace("\u00a0", " ")
        tokens = []
        for tok in raw_line.split(" "):
            if len(tok) > max_len:
                tokens.extend([tok[i:i + max_len] for i in range(0, len(tok), max_len)])
            else:
                tokens.append(tok)
        safe_lines.append(" ".join(tokens).strip())
    return "\n".join(safe_lines)


def _dedupe_sections(text: str) -> str:
    """
    Agrupa por encabezados (#, ##, ###) y elimina bloques duplicados (mismo encabezado + contenido).
    """
    lines = text.split("\n")
    sections = []
    current_heading = None
    current_body: List[str] = []
    for line in lines:
        if line.strip().startswith("#"):
            if current_heading or current_body:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = line.strip()
            current_body = []
        else:
            current_body.append(line)
    if current_heading or current_body:
        sections.append((current_heading, "\n".join(current_body).strip()))

    seen = set()
    dedup_sections: List[str] = []
    for heading, body in sections:
        key = (heading or "", body)
        if key in seen:
            continue
        seen.add(key)
        if heading:
            dedup_sections.append(heading)
        if body:
            dedup_sections.append(body)
    return "\n".join(dedup_sections)


def _strip_tables(text: str) -> str:
    """
    Convierte tablas Markdown (líneas con '|') en bullets simples para evitar desbordes en PDF.
    """
    out: List[str] = []
    for line in text.split("\n"):
        if "|" in line and not line.strip().startswith("#"):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts:
                out.append("- " + " | ".join(parts))
            continue
        out.append(line)
    return "\n".join(out)


# =========================
# 5) Utilidades de charts/PDF
# =========================


def _collect_images(coder_results: Dict[str, CoderResult]) -> Dict[str, List[str]]:
    imgs: Dict[str, List[str]] = {}
    for t, res in coder_results.items():
        images = []
        seen = set()
        for m in res.models:
            for pth in m.image_paths:
                if pth in seen:
                    continue
                seen.add(pth)
                images.append(pth)
        imgs[t] = images
    return imgs


def _cleanup_charts(charts_root: str) -> List[str]:
    warnings: List[str] = []
    if not os.path.isdir(charts_root):
        return warnings
    for item in os.listdir(charts_root):
        full = os.path.join(charts_root, item)
        try:
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=False)
            elif os.path.isfile(full):
                os.remove(full)
        except Exception as exc:
            warnings.append(f"No se pudo borrar {full}: {exc}")
    return warnings


def _build_short_message(tickers: List[str], pdf_path: str) -> str:
    return f"[stocks-rag] Informe PDF listo para {', '.join(tickers)}. Descarga: {pdf_path}"


# =========================
# 6) API principal
# =========================


def run_stock_picker(
    tickers: List[str],
    risk_profile: str,
    horizon: str,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Modo sin RAG persistente (compatibilidad).
    """
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not tickers:
        raise ValueError("Debes especificar al menos un ticker v\u00e1lido.")

    snapshots_by_ticker: Dict[str, str] = {}
    raw_snapshots: Dict[str, Dict[str, Any]] = {}
    for t in tickers:
        snap_text, _raw = _build_snapshot_text(t)
        snapshots_by_ticker[t] = snap_text
        raw_snapshots[t] = _raw

    researcher_summary = _run_researcher(
        tickers=tickers,
        risk_profile=risk_profile,
        horizon=horizon,
        snapshots_by_ticker=snapshots_by_ticker,
        rag_docs_by_ticker=None,
    )

    analyst_text = _run_analyst(
        researcher_summary=researcher_summary,
        risk_profile=risk_profile,
        horizon=horizon,
        coder_context="(sin capa cuantitativa en este modo)",
    )

    writer_report = _run_writer(
        analyst_text=analyst_text,
        risk_profile=risk_profile,
        horizon=horizon,
        context=researcher_summary.get("_context", ""),
    )

    judged_report = _run_judge(
        final_report=writer_report,
        context=researcher_summary.get("_context", ""),
    )

    out: Dict[str, Any] = {"final_report": judged_report}

    if debug:
        trace_items: List[Dict[str, str]] = [
            {"agent": "Researcher", "model": "deepseek-r1:8b", "content": researcher_summary.get("ALL", "")},
            {"agent": "Analyst", "model": "ministral-3:8b", "content": analyst_text},
            {"agent": "Writer", "model": "qwen3:8b", "content": writer_report},
            {"agent": "Judge", "model": "qwen2.5:7b", "content": judged_report},
            {"agent": "Context", "model": "input", "content": researcher_summary.get("_context", "")},
        ]
        api_lines: List[str] = []
        for t in tickers:
            raw = raw_snapshots.get(t, {})
            fmp_w = (raw.get("fmp") or {}).get("warning")
            alpha_w = (raw.get("alpha") or {}).get("warning")
            quote_w = (raw.get("finnhub_quote") or {}).get("warning")
            earn_w = (raw.get("finnhub_earnings") or {}).get("warning")
            warnings = [w for w in (fmp_w, alpha_w, quote_w, earn_w) if w]
            if warnings:
                api_lines.append(f"[{t}] Warnings APIs:")
                for w in warnings:
                    api_lines.append(f"  - {w}")
                api_lines.append("")
        if api_lines:
            trace_items.append({"agent": "APIs", "model": "fuentes", "content": "\n".join(api_lines).strip()})
        out["trace"] = trace_items
        out["snapshots_by_ticker"] = snapshots_by_ticker

    return out


def run_stock_picker_rag(
    tickers: List[str],
    risk_profile: str,
    horizon: str,
    debug: bool = False,
    lookback_mode: str = "default",
    forecast_horizon: int = 75,
) -> Dict[str, Any]:
    """
    Modo 3.4: RAG persistente + capa cuantitativa + PDF.
    """
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not tickers:
        raise ValueError("Debes especificar al menos un ticker v\u00e1lido.")

    # Snapshots
    snapshots_by_ticker: Dict[str, str] = {}
    raw_snapshots: Dict[str, Dict[str, Any]] = {}
    for t in tickers:
        snap_text, _raw = _build_snapshot_text(t)
        snapshots_by_ticker[t] = snap_text
        raw_snapshots[t] = _raw

    # RAG vol\u00e1til
    rag_docs_by_ticker: Dict[str, List[str]] = {t: _build_rag_docs_for_ticker(t) for t in tickers}

    # RAG persistente
    persistent_docs_by_ticker, persist_warnings = _ingest_and_retrieve_persistent(
        tickers=tickers,
        rag_docs_by_ticker=rag_docs_by_ticker,
        risk_profile=risk_profile,
        horizon=horizon,
        top_k=5,
    )

    # Coder cuant
    coder_results = run_coder(
        tickers=tickers,
        charts_root=CHARTS_ROOT,
        lookback_mode=lookback_mode,
        forecast_horizon=forecast_horizon,
        train_ratio=0.7,
    )
    coder_context = _format_coder_context(coder_results)

    # Researcher (con RAG)
    researcher_summary = _run_researcher(
        tickers=tickers,
        risk_profile=risk_profile,
        horizon=horizon,
        snapshots_by_ticker=snapshots_by_ticker,
        rag_docs_by_ticker=rag_docs_by_ticker,
        persistent_docs_by_ticker=persistent_docs_by_ticker or None,
    )

    # Analyst
    analyst_text = _run_analyst(
        researcher_summary=researcher_summary,
        risk_profile=risk_profile,
        horizon=horizon,
        coder_context=coder_context,
    )

    # Writer
    writer_report = _run_writer(
        analyst_text=analyst_text,
        risk_profile=risk_profile,
        horizon=horizon,
        context=researcher_summary.get("_context", ""),
    )

    # Judge
    judged_report = _run_judge(
        final_report=writer_report,
        context=researcher_summary.get("_context", ""),
    )

    # PDF
    images_by_ticker = _collect_images(coder_results)
    pdf_path = ""
    pdf_warnings: List[str] = []
    cleaned_text = _dedupe_headings(judged_report)
    cleaned_text = _dedupe_sections(cleaned_text)
    cleaned_text = _strip_tables(cleaned_text)
    safe_text = _sanitize_for_pdf(cleaned_text, max_len=60)
    try:
        pdf_path = create_pdf_report(
            tickers=tickers,
            final_text=safe_text,
            images_by_ticker=images_by_ticker,
            output_dir=REPORTS_ROOT,
        )
    except Exception as exc:
        pdf_warnings.append(f"[PDF] No se pudo generar el PDF: {exc}")

    # Limpieza de charts
    cleanup_warnings = _cleanup_charts(CHARTS_ROOT)

    short_message = _build_short_message(tickers, pdf_path) if pdf_path else "Análisis completado (sin PDF por error)."

    out: Dict[str, Any] = {
        "final_report": short_message,
        "pdf_path": pdf_path or None,
    }

    if debug:
        trace_items = [
            {"agent": "Researcher", "model": "deepseek-r1:8b", "content": researcher_summary.get("ALL", "")},
            {"agent": "Analyst", "model": "ministral-3:8b", "content": analyst_text},
            {"agent": "Writer", "model": "qwen3:8b", "content": writer_report},
            {"agent": "Judge", "model": "qwen2.5:7b", "content": judged_report},
            {"agent": "Context", "model": "input", "content": researcher_summary.get("_context", "")},
            {"agent": "Coder", "model": "pipeline", "content": coder_context},
        ]
        api_lines: List[str] = []
        for t in tickers:
            raw = raw_snapshots.get(t, {})
            fmp_w = (raw.get("fmp") or {}).get("warning")
            alpha_w = (raw.get("alpha") or {}).get("warning")
            quote_w = (raw.get("finnhub_quote") or {}).get("warning")
            earn_w = (raw.get("finnhub_earnings") or {}).get("warning")
            warnings = [w for w in (fmp_w, alpha_w, quote_w, earn_w) if w]
            if warnings:
                api_lines.append(f"[{t}] Warnings APIs:")
                for w in warnings:
                    api_lines.append(f"  - {w}")
                api_lines.append("")
        if api_lines:
            trace_items.append({"agent": "APIs", "model": "fuentes", "content": "\n".join(api_lines).strip()})
        if persist_warnings:
            trace_items.append({"agent": "Persistencia", "model": "pgvector", "content": "\n".join(persist_warnings)})
        coder_warns: List[str] = []
        for t, res in coder_results.items():
            for w in res.warnings:
                coder_warns.append(f"[{t}] {w}")
            for m in res.models:
                for w in m.warnings:
                    coder_warns.append(f"[{t}] {m.name}: {w}")
        if coder_warns:
            trace_items.append({"agent": "Coder warnings", "model": "pipeline", "content": "\n".join(coder_warns)})
        if pdf_warnings:
            trace_items.append({"agent": "PDF", "model": "fpdf2", "content": "\n".join(pdf_warnings)})
        if cleanup_warnings:
            trace_items.append({"agent": "Cleanup", "model": "fs", "content": "\n".join(cleanup_warnings)})
        out["trace"] = trace_items
        out["snapshots_by_ticker"] = snapshots_by_ticker
        out["rag_docs_by_ticker"] = rag_docs_by_ticker
        if persistent_docs_by_ticker:
            out["persistent_docs_by_ticker"] = persistent_docs_by_ticker
        if persist_warnings:
            out["persistent_warnings"] = persist_warnings
        out["coder_results"] = coder_context

    return out
