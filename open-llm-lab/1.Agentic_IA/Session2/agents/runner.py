# agents/runner.py

import json
from typing import Any, Dict, List, Optional

from .agent import Agent
from .router import ToolRouter


class AgentRunner:
    """
    Coordina el ciclo de interacción entre:

    - El Agente (Agent: rol, modelo, tools, memoria)
    - El LLM (a través de agent.llm_client)
    - Las herramientas (ToolRouter)

    Implementa un loop del estilo:
        percepción -> pensamiento -> acción (tool) -> reflexión -> respuesta final
    """

    def __init__(self, tool_router: ToolRouter) -> None:
        self.tool_router = tool_router

    def _build_system_prompt(self, agent: Agent) -> str:
        """
        Construye el system prompt para el agente, incluyendo:

        - Descripción de su rol.
        - Instrucciones de uso de herramientas.
        - Formato de JSON para tool-calls.
        """
        tool_descriptions = []
        for tool in self.tool_router.tools.values():
            tool_descriptions.append(f"- {tool.name}: {tool.description}")

        tools_block = "\n".join(tool_descriptions)

        system_prompt = f"""
        Eres un agente llamado '{agent.name}'.

        Rol:
        {agent.role}

        Tienes acceso a las siguientes herramientas. Cuando consideres que
        una herramienta es útil, debes devolver EXCLUSIVAMENTE un JSON con este formato:

        {{
          "tool": "nombre_de_la_herramienta",
          "args": {{ "param1": "valor1", "param2": "valor2" }}
        }}

        Herramientas disponibles:
        {tools_block}

        Si ya tienes suficiente información para dar una respuesta final al usuario,
        responde en lenguaje natural, SIN JSON.
        """
        return "\n".join(line.strip() for line in system_prompt.splitlines() if line.strip())

    def _parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Intenta interpretar el contenido del modelo como un tool-call en JSON.

        Estrategia sencilla:
        - Si el contenido empieza con '{' y termina con '}', intentamos json.loads.
        - Si viene dentro de ```json ... ```, lo recortamos.
        """
        text = content.strip()

        # Manejo básico de bloques ```json ... ```
        if text.startswith("```"):
            # eliminamos posibles fences
            text = text.strip("`")
            # a veces viene como "json{...}" o "json\n{...}"
            if text.lower().startswith("json"):
                text = text[4:].strip()

        if not (text.startswith("{") and text.endswith("}")):
            return None

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None
        if "tool" not in data or "args" not in data:
            return None

        return data

    def run(
        self,
        agent: Agent,
        user_input: str,
        max_steps: int = 5,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> str:
        """
        Ejecuta el ciclo del agente hasta obtener una respuesta final.

        Parámetros:
        - agent: instancia de Agent (con modelo, rol, tools, llm_client)
        - user_input: instrucción inicial del usuario (ej: "Analiza esta URL...")
        - max_steps: número máximo de interacciones LLM/tool para evitar loops
        """
        # Construimos el system prompt dinámicamente
        system_prompt = self._build_system_prompt(agent)

        # Inicializamos el historial de mensajes para esta ejecución
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Agregamos la memoria previa del agente (si queremos "persistencia").
        messages.extend(agent.memory)

        # Finalmente, el input actual del usuario
        messages.append({"role": "user", "content": user_input})

        for step in range(1, max_steps + 1):
            # Llamamos al LLM local usando el cliente del agente
            assistant_content = agent.llm_client(
                model=agent.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Guardamos la respuesta cruda en memoria
            messages.append({"role": "assistant", "content": assistant_content})
            agent.add_to_memory("assistant", assistant_content)

            # Intentamos interpretar la respuesta como un tool-call
            maybe_tool_call = self._parse_tool_call(assistant_content)

            if maybe_tool_call is None:
                # No es un tool-call: asumimos que es la respuesta final.
                return assistant_content

            # Es un tool-call -> ejecutamos herramienta
            tool_name = maybe_tool_call["tool"]
            tool_args = maybe_tool_call.get("args", {})

            try:
                tool_result = self.tool_router.call_tool(tool_name, tool_args)
            except Exception as exc:
                tool_result = f"[ERROR al ejecutar herramienta '{tool_name}']: {exc}"

            # Insertamos el resultado de la herramienta como un nuevo mensaje
            tool_msg = (
                f"Resultado de la herramienta '{tool_name}' "
                f"con args={tool_args}:\n{tool_result}"
            )
            # Lo agregamos como mensaje 'user' para que el modelo lo trate
            # como información nueva que el usuario le proporciona.
            messages.append({"role": "user", "content": tool_msg})
            agent.add_to_memory("user", tool_msg)

        # Si se alcanzó max_steps sin respuesta final, devolvemos algo seguro.
        return (
            "He alcanzado el número máximo de pasos sin llegar a una respuesta final. "
            "Es posible que la tarea requiera más iteraciones o ajustes en las herramientas."
        )
