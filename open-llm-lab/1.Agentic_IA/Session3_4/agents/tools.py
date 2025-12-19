# agents/tools.py

import textwrap
from typing import Dict
from datetime import datetime, timezone

import requests

from .router import Tool


# =========================
# HERRAMIENTAS DE NEGOCIO
# =========================

def fetch_html(url: str, timeout: float = 10.0) -> str:
    """
    Descarga el HTML de una URL.

    NOTA IMPORTANTE:
    - Esta herramienta usa la conexión de TU PC.
    - El modelo solo "ve" el resultado que devolvemos en texto.
    - Maneja errores básicos de red y HTTP (403, 404, etc.).
    - Si algo falla, devuelve un mensaje que empieza con [WEB_ERROR]
      para que el agente adapte su comportamiento.
    """
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        # Devolvemos el texto crudo (si quieres, puedes recortarlo un poco).
        html = resp.text
        # Evitamos mandar textos gigantescos:
        return summarize_text(html, max_chars=12000)
    except Exception as exc:
        # Mensaje claro para el LLM, con la marca [WEB_ERROR]
        return (
            "[WEB_ERROR] No se pudo acceder a la URL "
            f"{url}. Detalle técnico: {exc}. "
            "Redacta un correo de prospección más genérico apoyándote en "
            "la persona objetivo, el tono y el contexto extra proporcionado. "
            "Menciona brevemente que no pudiste acceder a la web y sugiere al "
            "usuario que comparta otra URL o más detalles sobre la empresa."
        )


def summarize_text(text: str, max_chars: int = 2000) -> str:
    """
    Hace una reducción burda del texto para que no sea demasiado largo.

    OJO:
    - Esto NO es un resumen inteligente; solo recorta.
    - El resumen 'inteligente' lo hará el LLM con este texto recortado.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCADO para el modelo]"


def extract_value_proposition(raw_html: str) -> str:
    """
    Versión simplificada:
    - Elimina un poco de ruido superficial (saltos de línea extra).
    - El objetivo real de 'entender' la propuesta de valor se delega al LLM.
    - Este texto se usará como contexto para el modelo.
    """
    # Quitamos espacios y saltos de línea excesivos.
    compact = " ".join(raw_html.split())
    # Recortamos un poco para no saturar al modelo.
    compact = summarize_text(compact, max_chars=4000)
    return compact


def generate_email_draft(
    company_context: str,
    persona: str = "CTO",
    tone: str = "profesional",
    language: str = "es",
) -> str:
    """
    Genera un "prompt de alto nivel" que el LLM usará para redactar
    un correo de prospección, usando el contexto de la empresa.

    OJO:
    - Esta función no llama al modelo; solo prepara el texto base.
    - El AgentRunner se lo pasará al LLM como parte del diálogo.
    """
    prompt = f"""
    Genera un correo de prospección B2B para un/una {persona}.
    El tono debe ser {tone}.
    El idioma del correo debe ser: {language}.

    Contexto de la empresa (información extraída de su página web o del usuario):
    ---
    {company_context}
    ---

    Requisitos:
    - Un asunto atractivo pero profesional.
    - Un cuerpo breve (3 a 5 párrafos máximo).
    - Mostrar que entendemos la propuesta de valor de la empresa (si se conoce).
    - En caso de no conocer bien la empresa, redactar un correo más genérico
      pero aún relevante para el sector del destinatario.
    - Incluir un llamado a la acción claro (por ejemplo, agendar una llamada).
    """
    return textwrap.dedent(prompt).strip()


def get_current_datetime() -> str:
    """
    Devuelve la fecha y hora actuales en UTC, tanto en formato ISO 8601
    como en un formato humano legible. El modelo puede usar esto para
    redactar correos con referencias temporales realistas.
    """
    now_utc = datetime.now(timezone.utc)
    iso = now_utc.isoformat()
    human = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    return f"Fecha/hora actual:\n- ISO: {iso}\n- Legible: {human}"


# =========================
# REGISTRO DE TOOLS
# =========================

def get_sdr_tools() -> Dict[str, Tool]:
    """
    Devuelve el diccionario de herramientas disponibles para el Agente SDR.

    El AgentRunner usará este diccionario a través de ToolRouter.
    """
    tools: Dict[str, Tool] = {
        "fetch_html": Tool(
            name="fetch_html",
            description=(
                "Usa esta herramienta cuando necesites leer el contenido HTML "
                "de una página web a partir de una URL. Si la salida contiene "
                "la marca [WEB_ERROR], asume que hubo un problema de acceso "
                "(por ejemplo 403/404) y redacta un correo más genérico."
            ),
            func=fetch_html,
        ),
        "summarize_text": Tool(
            name="summarize_text",
            description=(
                "Usa esta herramienta cuando el texto sea muy largo y quieras "
                "recortarlo antes de analizarlo."
            ),
            func=summarize_text,
        ),
        "extract_value_proposition": Tool(
            name="extract_value_proposition",
            description=(
                "Usa esta herramienta para preparar el HTML bruto de una página "
                "web antes de analizar su propuesta de valor."
            ),
            func=extract_value_proposition,
        ),
        "generate_email_draft": Tool(
            name="generate_email_draft",
            description=(
                "Usa esta herramienta cuando quieras generar un prompt detallado "
                "para que el LLM redacte un correo de prospección."
            ),
            func=generate_email_draft,
        ),
        "get_current_datetime": Tool(
            name="get_current_datetime",
            description=(
                "Usa esta herramienta cuando necesites conocer la fecha y hora "
                "actuales para mencionarlas en el correo o ajustar referencias "
                "temporales (por ejemplo 'esta semana', 'durante el próximo mes')."
            ),
            func=get_current_datetime,
        ),
    }
    return tools
