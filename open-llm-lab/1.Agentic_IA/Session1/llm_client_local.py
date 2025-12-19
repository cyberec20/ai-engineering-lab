import httpx
from typing import List, Dict, Any


# Modelo por defecto que tengas en Ollama
DEFAULT_MODEL = "qwen2.5:7b"  # cámbialo si usas otro, p.ej. "llama3.2:3b"


def call_llm_local(
    model: str,
    messages: List[Dict[str, Any]],
    base_url: str = "http://localhost:11434",
    timeout: float = 120.0,
) -> str:
    """
    Llama a un modelo local expuesto por Ollama usando la API /api/chat.

    Parameters
    ----------
    model : str
        Nombre del modelo en Ollama (ej. "qwen2.5:7b").
    messages : list[dict]
        Lista de mensajes estilo OpenAI:
        [{"role": "user"|"system"|"assistant", "content": "texto"}]
    base_url : str
        URL base donde escucha Ollama.
    timeout : float
        Timeout en segundos para la petición HTTP.

    Returns
    -------
    str
        Contenido de la respuesta del asistente.
    """
    url = f"{base_url}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # para simplificar, respuesta completa en una sola pieza
    }

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.RequestError as e:
        raise RuntimeError(f"Error de red al contactar Ollama: {e}") from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Ollama devolvió un status HTTP inesperado: {e.response.status_code}"
        ) from e

    data = response.json()

    # Formato típico de /api/chat:
    # {"message": {"role": "assistant", "content": "..."}, ...}
    try:
        return data["message"]["content"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Formato de respuesta inesperado de Ollama: {data}") from e
