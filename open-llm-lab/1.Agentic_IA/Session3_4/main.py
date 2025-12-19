# main.py

"""
API de la Sesión 2 + 3 (3.2)

- Sesión 2:
    * Agente SDR con herramientas (fetch_html, generate_email_draft, get_current_datetime, etc.).
    * Endpoints:
        - /sdr/email
        - /sdr/chat
        - /sdr/chat-ui

- Sesión 3 (3.1–3.2):
    * Crew de agentes para "stock picker" educativo con modelos locales:
        - Researcher  (qwen3:8b + APIs numéricas + RAG cuando aplica)
        - Analyst     (llama3.1:8b)
        - Writer      (qwen3:8b)
        - Judge       (qwen2.5:7b)

    * Endpoints:
        - /crew/stock-picker      → análisis con capa numérica
        - /crew/stock-picker-rag  → numérico + RAG volátil

    * Comandos en el chat:
        - /stocks AAPL, NVDA, TSLA [debug]
        - /stocks-rag AAPL, NVDA, TSLA [debug]
"""

from typing import Optional, Dict, List, Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Carga automática de variables desde .env (incluye PG_CONN para el RAG persistente)
load_dotenv()

from llm_client_local import call_llm_local

from agents.agent import Agent
from agents.tools import get_sdr_tools
from agents.router import ToolRouter
from agents.runner import AgentRunner

from crew.stock_picker import (
    run_stock_picker,       # Sesión 3.1
    run_stock_picker_rag,   # Sesión 3.2 (numérico + RAG volátil)
)

# =========================
# CONFIGURACIÓN DEL AGENTE SDR (Sesión 2)
# =========================

sdr_tools = get_sdr_tools()
tool_router = ToolRouter(tools=sdr_tools)
agent_runner = AgentRunner(tool_router=tool_router)


SDR_ROLE = """
Eres un Agente SDR (Sales Development Representative) experto en prospección B2B,
pero SOLO debes actuar como SDR cuando el usuario lo indique de forma explícita.

====================
1) COMPORTAMIENTO GENERAL
====================
- Si el usuario hace una pregunta normal (“¿Qué día es hoy?”, “¿qué puedes hacer?”,
  preguntas informativas, aclaraciones, etc.), responde de manera simple y directa.
- No analices empresas, no investigues URLs y no redactes correos a menos que el
  usuario lo pida explícitamente.
- En modo chat normal, no actives comportamiento SDR.

====================
2) USO DE HERRAMIENTAS
====================
- Usa herramientas SOLO cuando aporten valor real.
- Si el usuario pregunta por fecha, hora o tiempo actual:
    1) Invoca SIEMPRE la herramienta `get_current_datetime` (sin argumentos).
    2) Espera su resultado.
    3) Responde usando la fecha/hora exactas, sin inventarlas.
    4) NO mezcles esta respuesta con análisis, correos ni prospección.

- Para tareas SDR (cuando el usuario lo pida):
    * Puedes usar:
        - `fetch_html` para leer páginas web,
        - `summarize_text` si el HTML es muy largo,
        - `extract_value_proposition` para refinar el contenido,
        - `generate_email_draft` para apoyar redacción de correos,
        - `get_current_datetime` para referencias temporales si aplica.

====================
3) ACTIVACIÓN DEL MODO SDR
====================
Activa tu modo SDR SOLO si el usuario menciona algo como:
- analizar una empresa,
- investigar una URL,
- redactar un correo de prospección,
- preparar un mensaje comercial.

En ese caso:
- Usa las herramientas necesarias.
- Redacta correos o análisis según corresponda.
- Mantén tono profesional y orientado a acción.

====================
4) MANEJO DE ERRORES (fetch_html)
====================
- Si el resultado de `fetch_html` comienza con “[WEB_ERROR]”:
    * Menciona brevemente que no pudiste acceder a la web (403/404 u otro error).
    * Continúa con un mensaje o correo SDR genérico basado en la persona objetivo,
      tono, idioma y contexto extra del usuario.
    * Incluye 1–2 preguntas como:
        - “¿Existe otra URL o material que pueda revisar?”
        - “¿A qué área o contacto específico deseas dirigir la propuesta?”

====================
5) ESTILO
====================
- En modo chat normal: conversacional, claro, directo.
- En modo SDR: profesional, breve (3–5 párrafos en correos), preciso y orientado a acción.
- Nunca respondas en formato JSON; tu salida final debe ser lenguaje natural.
""".strip()


def create_sdr_agent() -> Agent:
    """
    Crea una nueva instancia de Agent para el SDR.

    La usamos:
    - De forma efímera en /sdr/email.
    - Per-session en /sdr/chat (clon por session_id).
    """
    return Agent(
        name="SDR Agent Local",
        role=SDR_ROLE,
        model_name="qwen2.5:7b",  # modelo local en Ollama
        tools=sdr_tools,
        llm_client=call_llm_local,
    )


# Diccionario de sesiones de chat: session_id -> Agent con memoria propia
chat_sessions: Dict[str, Agent] = {}


# =========================
# DEFINICIÓN DE LA API
# =========================

app = FastAPI(
    title="Sesión 2+3 - Agente SDR + Crew Stock Picker (3.2)",
    description=(
        "API de ejemplo para:\n"
        "- Sesión 2: Agente SDR con herramientas y modelo local (Ollama).\n"
        "- Sesión 3.1: Crew de agentes para análisis numérico básico de acciones.\n"
        "- Sesión 3.2: Crew con capa RAG volátil y Finhub/Yahoo/Alpha/FMP, etc."
    ),
    version="0.3.2",
)

# --------- Modelos para /sdr/email ---------


class SDREmailRequest(BaseModel):
    url: str
    persona: str = "CTO"
    tone: str = "profesional"
    language: str = "es"
    extra_context: Optional[str] = None


class SDREmailResponse(BaseModel):
    model_used: str
    email_draft: str


# --------- Modelos para /sdr/chat ---------


class SDRChatRequest(BaseModel):
    session_id: str
    message: str


class SDRChatResponse(BaseModel):
    session_id: str
    model_used: str
    reply: str


# --------- Modelos para /crew/stock-picker (Sesión 3) ---------


class StockPickerRequest(BaseModel):
    """
    Petición para el Crew de stock picker.

    - tickers: lista de símbolos (ej: ["AAPL", "NVDA"]).
    - risk_profile: texto libre (ej: "moderado").
    - horizon: horizonte temporal (ej: "mediano plazo").
    - debug: si True, devolver también el detalle por agente.
    """
    tickers: List[str]
    risk_profile: str = "moderado"
    horizon: str = "mediano"
    debug: bool = False


class AgentTrace(BaseModel):
    agent: str
    model: str
    content: str


class StockPickerResponse(BaseModel):
    final_report: str
    pdf_path: Optional[str] = None
    trace: Optional[List[AgentTrace]] = None


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    """
    Endpoint simple para probar que el server está vivo.
    """
    return {
        "message": "Sesión 2+3 (3.2) - SDR Agent + Crew Stock Picker está en línea.",
        "endpoints": [
            "/sdr/email",
            "/sdr/chat",
            "/sdr/chat-ui",
            "/crew/stock-picker",
            "/crew/stock-picker-rag",
        ],
        "chat_commands": [
            "/stocks AAPL, NVDA, TSLA [debug]",
            "/stocks-rag AAPL, NVDA, TSLA [debug]",
        ],
    }


# ------- ENDPOINTS SDR (Sesión 2) -------

@app.post("/sdr/email", response_model=SDREmailResponse)
def generate_sdr_email(req: SDREmailRequest):
    """
    Endpoint clásico de la sesión 2: genera un CORREO de prospección.

    - Usa un agente SDR EFÍMERO (sin memoria entre peticiones).
    - Sigue usando el runtime de herramientas (fetch_html, etc.).
    """
    agent = create_sdr_agent()

    user_input_lines = [
        "Quiero que actúes como un SDR.",
        "",
        "Tarea:",
        f"- Analiza la página web de: {req.url}",
        f"- Persona objetivo: {req.persona}",
        f"- Tono del correo: {req.tone}",
        f"- Idioma del correo: {req.language}",
        "",
        "Instrucciones específicas:",
        f"- Primero, intenta usar la herramienta 'fetch_html' con args={{\"url\": \"{req.url}\"}}.",
        "- Si no puedes acceder a la web y recibes un [WEB_ERROR], sigue igualmente y redacta ",
        "  un correo más genérico como se describe en tu rol.",
        "- Si necesitas referencias temporales reales, puedes usar 'get_current_datetime'.",
    ]

    if req.extra_context:
        user_input_lines.extend(
            [
                "",
                "Información adicional proporcionada por el usuario:",
                req.extra_context,
            ]
        )

    user_input = "\n".join(user_input_lines)

    email_draft = agent_runner.run(
        agent=agent,
        user_input=user_input,
        max_steps=5,
        temperature=0.4,
        max_tokens=800,
    )

    return SDREmailResponse(
        model_used=agent.model_name,
        email_draft=email_draft,
    )


@app.post("/sdr/chat", response_model=SDRChatResponse)
def sdr_chat(req: SDRChatRequest):
    """
    Endpoint de chat con memoria por session_id.

    Comportamiento extra (Sesión 3.x):
    - Si el mensaje empieza por /stocks ...
      → dispara el Crew numérico (run_stock_picker).
    - Si el mensaje empieza por /stocks-rag ...
      → dispara el Crew con capa RAG (run_stock_picker_rag).
    - En cualquier otro caso:
      → Chat normal con el Agente SDR.
    """
    message = req.message.strip()

    # 1) Comandos de stock picker via chat
    if message.lower().startswith("/stocks-rag"):
        return _handle_stocks_command(
            req=req,
            use_rag=True,
        )

    if message.lower().startswith("/stocks"):
        return _handle_stocks_command(
            req=req,
            use_rag=False,
        )

    # 2) Chat SDR normal
    if req.session_id not in chat_sessions:
        chat_sessions[req.session_id] = create_sdr_agent()

    agent = chat_sessions[req.session_id]

    reply = agent_runner.run(
        agent=agent,
        user_input=message,
        max_steps=5,
        temperature=0.5,
        max_tokens=800,
    )

    return SDRChatResponse(
        session_id=req.session_id,
        model_used=agent.model_name,
        reply=reply,
    )


def _handle_stocks_command(req: SDRChatRequest, use_rag: bool) -> SDRChatResponse:
    """
    Rutina interna para manejar /stocks y /stocks-rag desde el chat.
    """
    session_id = req.session_id
    raw = req.message.strip()

    # Quitar el comando principal
    if use_rag:
        payload = raw[len("/stocks-rag"):].strip()
    else:
        payload = raw[len("/stocks"):].strip()

    # Detectar flag debug
    debug = False
    if payload.lower().endswith("debug"):
        debug = True
        payload = payload[:-5].strip()

    # Parsear tickers
    if "," in payload:
        tickers = [t.strip().upper() for t in payload.split(",") if t.strip()]
    else:
        tickers = [t.strip().upper() for t in payload.split(" ") if t.strip()]

    if not tickers:
        reply = (
            "Comando inv?lido.\n"
            "Ejemplos:\n"
            "  /stocks AAPL, NVDA, TSLA\n"
            "  /stocks-rag AAPL NVDA TSLA debug"
        )
        return SDRChatResponse(
            session_id=session_id,
            model_used="crew",
            reply=reply,
        )

    # Llamamos al crew correspondiente
    if use_rag:
        result: Dict[str, Any] = run_stock_picker_rag(
            tickers=tickers,
            risk_profile="moderado",
            horizon="mediano",
            debug=debug,
        )
        mode_label = "Crew Stock Picker (RAG)"
    else:
        result: Dict[str, Any] = run_stock_picker(
            tickers=tickers,
            risk_profile="moderado",
            horizon="mediano",
            debug=debug,
        )
        mode_label = "Crew Stock Picker"

    final_report = result.get("final_report", "")
    pdf_path = result.get("pdf_path")
    trace_data = result.get("trace") or []

    if debug and trace_data:
        debug_lines = ["", "----", "[DEBUG CREW - pasos internos]"]
        for step in trace_data:
            agent_name = step.get("agent", "unknown")
            model_name = step.get("model", "unknown")
            content = step.get("content", "")
            debug_lines.append(f"- {agent_name} ({model_name}):")
            debug_lines.append(f"  {content}")
            debug_lines.append("")
        debug_block = "\n".join(debug_lines)
        reply_text = f"[{mode_label}] An?lisis para: {', '.join(tickers)}\n\n{final_report}"
        if pdf_path:
            reply_text += f"\nPDF: {pdf_path}"
        reply_text += f"\n{debug_block}"
    else:
        reply_text = f"[{mode_label}] An?lisis para: {', '.join(tickers)}\n\n{final_report}"
        if pdf_path:
            reply_text += f"\nPDF: {pdf_path}"

    return SDRChatResponse(
        session_id=session_id,
        model_used="crew",
        reply=reply_text,
    )


@app.get("/sdr/chat-ui", response_class=HTMLResponse)
def sdr_chat_ui():
    """
    Devuelve una página HTML muy simple con interfaz tipo chat.

    El archivo 'sdr_chat.html' debe estar en la misma carpeta que main.py.
    """
    try:
        with open("sdr_chat.html", "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        html = "<h1>ERROR</h1><p>No se encontró sdr_chat.html en la carpeta actual.</p>"

    return HTMLResponse(content=html)


# ------- ENDPOINTS CREW (Sesión 3.x) -------

@app.post("/crew/stock-picker", response_model=StockPickerResponse)
def crew_stock_picker(req: StockPickerRequest):
    """
    Endpoint directo para el Crew de stock picker (versi?n num?rica).
    ?til para probar desde /docs sin pasar por el chat.
    """
    result: Dict[str, Any] = run_stock_picker(
        tickers=req.tickers,
        risk_profile=req.risk_profile,
        horizon=req.horizon,
        debug=req.debug,
    )

    trace = None
    if req.debug and result.get("trace"):
        trace = [
            AgentTrace(
                agent=step.get("agent", "unknown"),
                model=step.get("model", "unknown"),
                content=step.get("content", ""),
            )
            for step in result["trace"]
        ]

    return StockPickerResponse(
        final_report=result.get("final_report", ""),
        pdf_path=result.get("pdf_path"),
        trace=trace,
    )


@app.post("/crew/stock-picker-rag", response_model=StockPickerResponse)
def crew_stock_picker_rag(req: StockPickerRequest):
    """
    Endpoint directo para el Crew de stock picker con RAG persistente y PDF (Sesi?n 3.4).
    """
    result: Dict[str, Any] = run_stock_picker_rag(
        tickers=req.tickers,
        risk_profile=req.risk_profile,
        horizon=req.horizon,
        debug=req.debug,
    )

    trace = None
    if req.debug and result.get("trace"):
        trace = [
            AgentTrace(
                agent=step.get("agent", "unknown"),
                model=step.get("model", "unknown"),
                content=step.get("content", ""),
            )
            for step in result["trace"]
        ]

    return StockPickerResponse(
        final_report=result.get("final_report", ""),
        pdf_path=result.get("pdf_path"),
        trace=trace,
    )
