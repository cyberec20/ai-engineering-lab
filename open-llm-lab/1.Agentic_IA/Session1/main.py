from fastapi import FastAPI
from pydantic import BaseModel
import requests

OLLAMA_BASE_URL = "http://127.0.0.1:11434"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = 0.7
    max_tokens: int | None = 512

app = FastAPI(title="Local LLM API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(req: ChatRequest):
    model_name = req.model or "qwen2.5:7b"  # <- modelo por defecto

    payload = {
        "model": model_name,
        "messages": [m.dict() for m in req.messages],
        "stream": False,
        "options": {
            "temperature": req.temperature,
            "num_predict": req.max_tokens,
        },
    }

    r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
    r.raise_for_status()
    data = r.json()

    content = data["message"]["content"] if "message" in data else ""
    return {"model": model_name, "reply": content}
