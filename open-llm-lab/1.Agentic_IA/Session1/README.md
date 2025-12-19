# Session 1 ? Laboratorio local: endpoint `/chat` con Ollama

## Objetivo
Montar un endpoint local sencillo para consumir modelos de Ollama desde FastAPI y validar que el hardware permite un flujo estable de inferencia local.

## Que hay en esta sesion
- `1_config_hardware.md`: perfil de hardware y limites practicos para LLMs locales.
- `llm_client_local.py`: cliente Python que llama a la API de Ollama (`/api/chat`).
- `main.py`: API FastAPI con endpoint `/chat` y `/health`.
- `PENSUM_IA.html`: guia general del programa.

## Requisitos
- Python 3.11+
- Ollama instalado y corriendo
- Paquetes Python: `fastapi`, `uvicorn`, `requests`, `httpx`, `pydantic`

## Como ejecutar
1) Asegura que Ollama esta activo:
```
ollama run qwen2.5:7b
```

2) Instala dependencias:
```
pip install fastapi uvicorn requests httpx pydantic
```

3) Inicia el servidor:
```
uvicorn main:app --reload --port 8000
```

## Uso rapido
Request JSON esperado por `/chat`:
```json
{
  "model": "qwen2.5:7b",
  "messages": [
    {"role": "user", "content": "Hola, ?me puedes resumir este texto?"}
  ],
  "temperature": 0.7,
  "max_tokens": 512
}
```

## Notas
- `main.py` usa `OLLAMA_BASE_URL = "http://127.0.0.1:11434"`.
- El modelo por defecto es `qwen2.5:7b`; cambialo si lo necesitas.
