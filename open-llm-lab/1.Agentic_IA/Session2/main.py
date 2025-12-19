# main.py

"""
API de la Sesión 2: expone un Agente SDR local.

- Usa FastAPI en el puerto 8100.
- Endpoint /sdr/email:
    * Recibe una URL y algunos parámetros.
    * Usa un agente SDR "efímero" para leer la web y generar un correo.

- Endpoint /sdr/chat:
    * Recibe mensajes de chat con un session_id.
    * Mantiene memoria por session_id usando el runtime de agentes.
    * Devuelve la respuesta del agente como texto.

- Endpoint /sdr/chat-ui:
    * Devuelve una página HTML muy simple con interfaz tipo chat.
"""

from typing import Optional, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from llm_client_local import call_llm_local  # :contentReference[oaicite:0]{index=0}

from agents.agent import Agent  # :contentReference[oaicite:1]{index=1}
from agents.tools import get_sdr_tools  # :contentReference[oaicite:2]{index=2}
from agents.router import ToolRouter  # :contentReference[oaicite:3]{index=3}
from agents.runner import AgentRunner  # :contentReference[oaicite:4]{index=4}


# =========================
# CONFIGURACIÓN DEL AGENTE
# =========================

# 1) Creamos las herramientas y el router
sdr_tools = get_sdr_tools()
tool_router = ToolRouter(tools=sdr_tools)

# 2) Creamos el runner (mismo para email y chat)
agent_runner = AgentRunner(tool_router=tool_router)

# 3) System prompt del agente SDR (rol)
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
    title="Sesión 2 - Agente SDR Local",
    description="API de ejemplo para un agente SDR con herramientas y modelo local (Ollama).",
    version="0.2.0",
)


# --------- Modelos para /sdr/email ---------


class SDREmailRequest(BaseModel):
    """
    Payload para pedirle al agente que genere un correo de prospección.
    """
    url: str
    persona: str = "CTO"
    tone: str = "profesional"
    language: str = "es"
    extra_context: Optional[str] = None


class SDREmailResponse(BaseModel):
    """
    Respuesta del endpoint de correo SDR.
    """
    model_used: str
    email_draft: str


# --------- Modelos para /sdr/chat ---------


class SDRChatRequest(BaseModel):
    """
    Petición de chat con memoria por sesión.
    """
    session_id: str
    message: str


class SDRChatResponse(BaseModel):
    """
    Respuesta del agente en modo chat.
    """
    session_id: str
    model_used: str
    reply: str


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    """
    Endpoint simple para probar que el server está vivo.
    """
    return {"message": "Sesión 2 - Agente SDR Local está en línea."}


@app.post("/sdr/email", response_model=SDREmailResponse)
def generate_sdr_email(req: SDREmailRequest):
    """
    Endpoint clásico de la sesión: genera un CORREO de prospección.

    - Usa un agente SDR EFÍMERO (sin memoria entre peticiones).
    - Sigue usando el runtime de herramientas (fetch_html, etc.).
    """
    agent = create_sdr_agent()

    # Construimos el user_input para el agente.
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

    - Si el session_id es nuevo, se crea un Agent nuevo con memoria vacía.
    - Si ya existe, se reutiliza ese Agent, conservando su memoria.
    - El mensaje del usuario se pasa directamente como user_input al runtime.
    """
    # Recuperar o crear agente para esta sesión
    if req.session_id not in chat_sessions:
        chat_sessions[req.session_id] = create_sdr_agent()

    agent = chat_sessions[req.session_id]

    reply = agent_runner.run(
        agent=agent,
        user_input=req.message,
        max_steps=5,
        temperature=0.5,
        max_tokens=800,
    )

    return SDRChatResponse(
        session_id=req.session_id,
        model_used=agent.model_name,
        reply=reply,
    )


@app.get("/sdr/chat-ui", response_class=HTMLResponse)
def sdr_chat_ui():
    """
    Devuelve una página HTML muy simple con interfaz tipo chat.

    El archivo 'sdr_chat.html' debe estar en la misma carpeta que main.py.
    """
    with open("sdr_chat.html", "r", encoding="utf-8") as f:
        return f.read()
