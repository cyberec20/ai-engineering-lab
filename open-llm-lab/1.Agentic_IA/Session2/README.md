# Session 2 ? Agente SDR local con runtime de herramientas

## Objetivo
Construir un agente SDR local que use herramientas y se exponga por API y una UI de chat, manteniendo memoria por sesion.

## Que hay en esta sesion
- `main.py`: API FastAPI con endpoints `/sdr/email`, `/sdr/chat` y `/sdr/chat-ui`.
- `llm_client_local.py`: cliente para llamar a Ollama via `/api/chat`.
- `agents/`: runtime de agentes (Agent, Runner, ToolRouter, tools).
- `sdr_chat.html`: interfaz de chat simple conectada al endpoint.
- `Session2_Roadmap_SDR.html`: guia visual de la sesion.

## Arquitectura (resumen)
- **Agent**: mantiene rol, memoria y herramientas.
- **ToolRouter**: enruta la llamada a herramientas por nombre.
- **AgentRunner**: ciclo de ejecucion que decide cuando usar tools y cuando responder.
- **Ollama**: modelo local por defecto `qwen2.5:7b`.

## Endpoints
- `GET /` health basico.
- `POST /sdr/email` genera un correo SDR (agente efimero).
- `POST /sdr/chat` chat con memoria por `session_id`.
- `GET /sdr/chat-ui` devuelve la UI HTML.

## Requisitos
- Python 3.11+
- Ollama instalado y corriendo
- Paquetes: `fastapi`, `uvicorn`, `requests`, `httpx`, `pydantic`

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
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

4) Abre la UI:
```
http://localhost:8100/sdr/chat-ui
```

## Ejemplo rapido
Request a `/sdr/chat`:
```json
{
  "session_id": "demo",
  "message": "Quiero que actues como SDR y analices https://ejemplo.com"
}
```

## Ejemplos
### /sdr/email
`json
{
  "url": "https://ejemplo.com",
  "persona": "CTO",
  "tone": "profesional",
  "language": "es",
  "extra_context": "Somos una startup B2B con enfoque en automatizacion."
}
`

### /sdr/chat
`json
{
  "session_id": "demo",
  "message": "Quiero que actues como SDR y analices https://ejemplo.com"
}
`

## Diagrama de flujo
`
Usuario -> /sdr/chat
   |-> si mensaje activa SDR
   |      -> AgentRunner -> ToolRouter -> tools -> respuesta
   |-> si no activa SDR
          -> respuesta directa (sin tools)

Usuario -> /sdr/email
   -> Agent efimero -> ToolRouter -> tools -> correo
`
## Notas
- El rol del agente esta definido en `SDR_ROLE` dentro de `main.py`.
- El modo SDR solo se activa si el usuario lo pide explicitamente.
- Si `fetch_html` falla, el agente debe responder con un correo generico y preguntas de seguimiento.

