# crew/stock_picker.py

"""
Flujo "Stock Picker" educativo para la Sesión 3.

Arquitectura:
- Researcher  (qwen3:8b + yfinance)  -> contexto cualitativo p/ cada ticker.
- Analyst     (deepseek-r1:8b)       -> pros, contras, riesgos, lectura básica.
- Writer      (llama3.1:8b)          -> informe entendible para usuario final.
- Judge       (qwen2.5:7b, opcional) -> revisión y conclusión final.

Nota:
- No da recomendaciones financieras reales; es un ejercicio didáctico.
- Usa yfinance como fuente ligera (Yahoo Finance).
"""

from typing import List, Dict, Any

import yfinance as yf

from llm_client_local import call_llm_local


def _fetch_ticker_snapshot(ticker: str) -> str:
    """
    Obtiene un snapshot simple de información de mercado usando yfinance.

    Devuelve un texto en español que describe:
    - nombre,
    - sector / industria,
    - país (si está disponible),
    - algunos campos básicos.
    """
    ticker = ticker.upper()
    try:
        obj = yf.Ticker(ticker)
        info = obj.info or {}
    except Exception as exc:
        return (
            f"[DATA_ERROR] No pude obtener datos para {ticker}. "
            f"Detalle técnico: {exc}"
        )

    name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector", "Desconocido")
    industry = info.get("industry", "Desconocida")
    country = info.get("country", "Desconocido")

    # Datos numéricos opcionales (si existen)
    pe = info.get("trailingPE")
    fwd_pe = info.get("forwardPE")
    mkt_cap = info.get("marketCap")

    lines = [
        f"TICKER: {ticker}",
        f"Nombre: {name}",
        f"País: {country}",
        f"Sector: {sector}",
        f"Industria: {industry}",
    ]

    if pe is not None:
        lines.append(f"PER (trailingPE): {pe}")
    if fwd_pe is not None:
        lines.append(f"PER esperado (forwardPE): {fwd_pe}")
    if mkt_cap is not None:
        lines.append(f"Capitalización de mercado (aprox.): {mkt_cap}")

    return "\n".join(lines)


def _run_researcher_qwen3(
    tickers: List[str],
    risk_profile: str,
    horizon: str,
) -> Dict[str, str]:
    """
    Researcher (qwen3:8b):
    - Lee snapshots de yfinance.
    - Produce un resumen de alto nivel por ticker.

    Retorna:
    - dict ticker -> resumen (str)
    """
    snapshots: Dict[str, str] = {}
    for t in tickers:
        snapshots[t] = _fetch_ticker_snapshot(t)

    # Construimos un único prompt para todos los tickers
    raw_context_lines: List[str] = []
    for t in tickers:
        raw_context_lines.append(f"=== {t} ===")
        raw_context_lines.append(snapshots[t])
        raw_context_lines.append("")

    raw_context = "\n".join(raw_context_lines)

    system = (
        "Eres un analista de investigación de mercados (Researcher). "
        "Tu tarea es entender, de forma cualitativa y descriptiva, "
        "qué hace cada empresa y en qué contexto opera.\n"
        "No des recomendaciones de inversión; solo describe.\n"
        "Responde SIEMPRE en español."
    )

    user = (
        "Tengo el siguiente contexto para una lista de tickers. "
        "Para cada uno, quiero un resumen breve (3-5 frases) que incluya:\n"
        "- Qué hace la empresa (si se puede deducir).\n"
        "- Sector / industria.\n"
        "- Cualquier rasgo llamativo.\n\n"
        "Perfil de riesgo de referencia del usuario: "
        f"{risk_profile}\n"
        "Horizonte temporal de referencia: "
        f"{horizon}\n\n"
        "Contexto crudo por ticker:\n"
        f"{raw_context}\n\n"
        "Devuelve tu respuesta en formato legible, separando cada ticker con '=== TICKER ==='."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    researcher_summary = call_llm_local(
        model="qwen3:8b",
        messages=messages,
        temperature=0.4,
        max_tokens=800,
    )

    return snapshots, researcher_summary


def _run_analyst_deepseek(
    tickers: List[str],
    snapshots: Dict[str, str],
    researcher_summary: str,
    risk_profile: str,
    horizon: str,
) -> str:
    """
    Analyst (deepseek-r1:8b):
    - Toma snapshots + resumen del Researcher.
    - Saca pros, contras y riesgos por ticker.
    """
    system = (
        "Eres un analista de renta variable (equity analyst). "
        "Tu tarea es tomar descripciones de empresas, datos básicos y un resumen previo, "
        "y elaborar un análisis cualitativo sencillo:\n"
        "- Puntos fuertes.\n"
        "- Riesgos.\n"
        "- Cómo podría encajar (a nivel muy general) con un perfil de riesgo dado.\n"
        "No des recomendaciones tajantes de 'compra' o 'venta'; sé prudente.\n"
        "Responde SIEMPRE en español."
    )

    snapshot_block_lines: List[str] = []
    for t in tickers:
        snapshot_block_lines.append(f"=== {t} ===")
        snapshot_block_lines.append(snapshots.get(t, "Sin datos."))
        snapshot_block_lines.append("")

    snapshot_block = "\n".join(snapshot_block_lines)

    user = (
        "A continuación tienes datos básicos de mercado para varios tickers, seguidos "
        "del resumen producido por un analista de investigación (Researcher).\n\n"
        "Datos crudos por ticker:\n"
        f"{snapshot_block}\n\n"
        "Resumen del Researcher:\n"
        f"{researcher_summary}\n\n"
        f"Perfil de riesgo declarado del usuario: {risk_profile}\n"
        f"Horizonte temporal declarado: {horizon}\n\n"
        "Tarea:\n"
        "- Para cada ticker, elabora un análisis con:\n"
        "  * Puntos fuertes.\n"
        "  * Riesgos.\n"
        "  * Comentario general sobre adecuación para ese perfil/horizonte (sin dar órdenes de inversión).\n"
        "- Estructura tu respuesta por ticker, usando '=== TICKER ===' como separador."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    analyst_view = call_llm_local(
        model="deepseek-r1:8b",
        messages=messages,
        temperature=0.5,
        max_tokens=1200,
    )

    return analyst_view


def _run_writer_llama(
    tickers: List[str],
    researcher_summary: str,
    analyst_view: str,
    risk_profile: str,
    horizon: str,
) -> str:
    """
    Writer (llama3.1:8b):
    - Toma lo del Researcher + Analyst.
    - Lo transforma en un informe legible para usuario final.
    """
    system = (
        "Eres un redactor financiero que prepara informes para inversores particulares. "
        "Tu objetivo es convertir análisis técnicos en un texto claro, equilibrado y fácil de leer.\n"
        "Responde SIEMPRE en español."
    )

    user = (
        "Tengo el siguiente material sobre una lista de acciones:\n\n"
        "1) Resumen de investigación (Researcher):\n"
        f"{researcher_summary}\n\n"
        "2) Análisis cualitativo (Analyst):\n"
        f"{analyst_view}\n\n"
        f"Perfil de riesgo del lector: {risk_profile}\n"
        f"Horizonte temporal: {horizon}\n\n"
        "Tarea:\n"
        "- Prepara un informe estructurado con:\n"
        "  * Introducción breve.\n"
        "  * Un apartado por ticker, con resumen, puntos fuertes y riesgos.\n"
        "  * Una sección final con recordatorios de que esto NO es asesoría financiera.\n"
        "- Usa un tono equilibrado y educativo.\n"
        "- No incluyas disclaimers legales pesados; con 2-3 frases claras al final basta."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    writer_report = call_llm_local(
        model="llama3.1:8b",
        messages=messages,
        temperature=0.5,
        max_tokens=1600,
    )

    return writer_report


def _run_judge_qwen25(
    writer_report: str,
    risk_profile: str,
    horizon: str,
) -> str:
    """
    Judge (qwen2.5:7b):
    - Revisa el informe redactado.
    - Ajusta tono, resalta riesgos clave y cierra con una conclusión final.
    """
    system = (
        "Eres un estratega de portafolio senior. "
        "Lees informes preparados por analistas y redactores, y los ajustas para que "
        "sean coherentes con el perfil de riesgo del lector.\n"
        "Responde SIEMPRE en español."
    )

    user = (
        "A continuación tienes un informe redactado para un inversor particular:\n\n"
        f"{writer_report}\n\n"
        f"Perfil de riesgo del lector: {risk_profile}\n"
        f"Horizonte temporal: {horizon}\n\n"
        "Tarea:\n"
        "- Revisa el informe y:\n"
        "  * Ajusta el tono si es necesario (por ejemplo, si suena demasiado agresivo).\n"
        "  * Asegúrate de que los riesgos están claramente mencionados.\n"
        "  * Añade una breve conclusión final con 2-3 mensajes clave para el lector.\n"
        "- Devuelve el informe completo ya ajustado (no solo comentarios)."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    judged_report = call_llm_local(
        model="qwen2.5:7b",
        messages=messages,
        temperature=0.4,
        max_tokens=1600,
    )

    return judged_report


def run_stock_picker(
    tickers: List[str],
    risk_profile: str = "moderado",
    horizon: str = "mediano",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Función principal para la Sesión 3.

    - Orquesta el flujo: Researcher -> Analyst -> Writer -> Judge.
    - Usa modelos locales distintos para cada rol.
    - Devuelve:
        {
          "final_report": str,
          "trace": [
            {"agent": "...", "model": "...", "content": "..."},
            ...
          ]
        }
    """
    # Normalizamos tickers
    tickers = [t.strip().upper() for t in tickers if t.strip()]

    if not tickers:
        return {
            "final_report": (
                "No se proporcionaron tickers válidos. "
                "Ejemplo de uso: /stocks AAPL, NVDA, TSLA"
            ),
            "trace": [],
        }

    trace: List[Dict[str, str]] = []

    # 1) Researcher (qwen3:8b)
    snapshots, researcher_summary = _run_researcher_qwen3(
        tickers=tickers,
        risk_profile=risk_profile,
        horizon=horizon,
    )
    trace.append(
        {
            "agent": "Researcher",
            "model": "qwen3:8b",
            "content": researcher_summary,
        }
    )

    # 2) Analyst (deepseek-r1:8b)
    analyst_view = _run_analyst_deepseek(
        tickers=tickers,
        snapshots=snapshots,
        researcher_summary=researcher_summary,
        risk_profile=risk_profile,
        horizon=horizon,
    )
    trace.append(
        {
            "agent": "Analyst",
            "model": "deepseek-r1:8b",
            "content": analyst_view,
        }
    )

    # 3) Writer (llama3.1:8b)
    writer_report = _run_writer_llama(
        tickers=tickers,
        researcher_summary=researcher_summary,
        analyst_view=analyst_view,
        risk_profile=risk_profile,
        horizon=horizon,
    )
    trace.append(
        {
            "agent": "Writer",
            "model": "llama3.1:8b",
            "content": writer_report,
        }
    )

    # 4) Judge (qwen2.5:7b) - opcional pero activado por defecto
    final_report = _run_judge_qwen25(
        writer_report=writer_report,
        risk_profile=risk_profile,
        horizon=horizon,
    )
    trace.append(
        {
            "agent": "Judge",
            "model": "qwen2.5:7b",
            "content": final_report,
        }
    )

    result: Dict[str, Any] = {
        "final_report": final_report,
        "trace": trace if debug else [],
    }
    return result
