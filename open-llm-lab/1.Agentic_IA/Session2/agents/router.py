# agents/router.py

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class Tool:
    """
    Representa una herramienta que el LLM puede invocar.

    Atributos:
    - name: nombre único que el modelo usará en el JSON ("fetch_html", "summarize", etc.)
    - description: explicación corta para el modelo de CUÁNDO usar esta herramienta.
    - func: función Python que se ejecutará cuando el modelo la invoque.
    """
    name: str
    description: str
    func: Callable[..., Any]


class ToolRouter:
    """
    Se encarga de mapear nombres de herramientas a funciones Python reales.

    El LLM devolverá algo como:
        {"tool": "fetch_html", "args": {"url": "https://..."}}

    El router:
        - Busca la Tool con ese nombre.
        - Llama a la función real de Python.
        - Devuelve el resultado al AgentRunner.
    """

    def __init__(self, tools: Dict[str, Tool]) -> None:
        self.tools = tools

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Ejecuta la herramienta solicitada por el LLM.

        Args:
            tool_name: nombre de la herramienta (string)
            args: diccionario de argumentos para la función Python

        Returns:
            Lo que devuelva la función Python (texto, dict, etc.)

        Raises:
            KeyError si la herramienta no existe.
        """
        if tool_name not in self.tools:
            raise KeyError(f"Herramienta '{tool_name}' no registrada.")

        tool = self.tools[tool_name]
        return tool.func(**args)
