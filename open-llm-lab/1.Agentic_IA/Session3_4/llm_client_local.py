import httpx
from typing import List, Dict, Any, Optional

# Modelo por defecto que tengas en Ollama
# Puedes cambiarlo si quieres otro por defecto.
DEFAULT_MODEL = "qwen2.5:7b"


def call_llm_local(
    model: Optional[str],
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 512,
    base_url: str = "http://localhost:11434",
    timeout: float = 120.0,
) -> str:
    """
    Llama a un modelo local expuesto por Ollama usando la API /api/chat.

    Parámetros:
    - model: nombre del modelo en Ollama, ej. "qwen2.5:7b".
             Si es None o cadena vacía, se usa DEFAULT_MODEL.
    - messages: lista de mensajes en formato OpenAI:
        [{"role": "system"|"user"|"assistant", "content": "texto"}, ...]
    - temperature: controla la "creatividad" del modelo (0 = determinista).
    - max_tokens: máximo de tokens que el modelo podrá generar (num_predict).
    - base_url: URL base de Ollama (normalmente http://localhost:11434).
    - timeout: tiempo máximo en segundos para esperar la respuesta.

    Retorna:
    - El contenido de la respuesta del asistente como string.

    Lanza:
    - RuntimeError si hay problemas de red o formato de respuesta.
    """
    if not model:
        model = DEFAULT_MODEL

    # Payload según la API de Ollama /api/chat
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,  # queremos la respuesta completa, no en streaming
        "options": {
            # Estos nombres son los que Ollama reconoce
            "temperature": float(temperature),
            "num_predict": int(max_tokens),
        },
    }

    url = f"{base_url.rstrip('/')}/api/chat"

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.RequestError as e:
        # Error de conexión / red
        raise RuntimeError(f"Error de red al contactar Ollama: {e}") from e
    except httpx.HTTPStatusError as e:
        # Status HTTP inesperado
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
