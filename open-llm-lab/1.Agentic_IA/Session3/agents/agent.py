# agents/agent.py

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class Agent:
    """
    Representa a un agente 'inteligente' de alto nivel.

    IMPORTANTE:
    - Un Agent NO es un modelo.
    - Es UNA CAPA LÓGICA que envuelve:
        * nombre
        * rol (system prompt)
        * nombre del modelo a usar (ej: 'qwen2.5:7b')
        * herramientas disponibles
        * memoria (historial mínimo de la conversación)
        * una referencia al cliente LLM (call_llm_local)
    """
    name: str
    role: str
    model_name: str
    tools: Dict[str, Any]  # El router manejará estos objetos
    llm_client: Callable[..., str]

    # Memoria simple: historial de mensajes (user/assistant)
    memory: List[Dict[str, str]] = field(default_factory=list)

    def add_to_memory(self, role: str, content: str) -> None:
        """
        Añade un mensaje al historial interno del agente.
        """
        self.memory.append({"role": role, "content": content})

    def reset_memory(self) -> None:
        """
        Limpia la memoria del agente. Útil para "empezar de cero".
        """
        self.memory.clear()
