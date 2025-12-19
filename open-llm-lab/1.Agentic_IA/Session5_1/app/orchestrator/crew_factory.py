from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.core.config import AppConfig
from app.orchestrator.crewai_compat import patch_signals_for_windows


class AgentYaml(BaseModel):
    role: str
    goal: str
    backstory: str
    model: str
    tools: list[str] = Field(default_factory=list)


class AgentsYaml(BaseModel):
    agents: list[AgentYaml]


class TaskYaml(BaseModel):
    name: str
    agent_role: str
    description: str
    expected_output: str


class TasksYaml(BaseModel):
    tasks: list[TaskYaml]


class ToolsYaml(BaseModel):
    tools: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class CrewBundle:
    crew: Any
    agents: list[Any]
    tasks: list[Any]
    agents_created: list[dict[str, Any]]


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root in {path}")
    return data


def load_and_validate_configs(base_dir: Path) -> tuple[AgentsYaml, TasksYaml, ToolsYaml]:
    agents_p = base_dir / "agents.yaml"
    tasks_p = base_dir / "tasks.yaml"
    tools_p = base_dir / "tools.yaml"
    if not agents_p.exists() or not tasks_p.exists() or not tools_p.exists():
        raise FileNotFoundError("Missing crew_config YAML files (agents.yaml/tasks.yaml/tools.yaml)")
    agents = AgentsYaml.model_validate(_load_yaml(agents_p))
    tasks = TasksYaml.model_validate(_load_yaml(tasks_p))
    tools = ToolsYaml.model_validate(_load_yaml(tools_p))
    return agents, tasks, tools


def _make_llm(config: AppConfig, model: str) -> Any:
    import logging
    logger = logging.getLogger(__name__)
    
    patch_signals_for_windows()
    from crewai import LLM  # local import

    logger.info(f"Creating LLM for model: {model}, base_url: {config.ollama_base_url}")
    
    # CrewAI uses LiteLLM providers. For Ollama, the common format is "ollama/<model>".
    # Using both base_url and api_base for maximum compatibility
    # Adding explicit timeout and num_retries to prevent long waits
    llm = LLM(
        model=f"ollama/{model}",
        base_url=config.ollama_base_url,
        api_base=config.ollama_base_url,
        temperature=0.2,
        timeout=config.request_timeout_seconds,
        num_retries=1
    )
    
    logger.info(f"LLM created successfully for {model}")
    return llm


def build_crew(
    *,
    config: AppConfig,
    web_tools: dict[str, Any],
) -> tuple[CrewBundle, TasksYaml, ToolsYaml]:
    patch_signals_for_windows()
    from crewai import Agent, Crew, Process, Task  # local import

    crew_cfg_dir = Path(__file__).resolve().parent / "crew_config"
    agents_yaml, tasks_yaml, tools_yaml = load_and_validate_configs(crew_cfg_dir)

    agents_by_role: dict[str, Any] = {}
    agents_created: list[dict[str, Any]] = []
    for a in agents_yaml.agents:
        tools = []
        for tname in a.tools:
            if tname in web_tools:
                tools.append(web_tools[tname])
        agent = Agent(
            role=a.role,
            goal=a.goal,
            backstory=a.backstory,
            tools=tools,
            llm=_make_llm(config, a.model),
            verbose=True,  # Enable verbose for debugging
            allow_delegation=False,
            max_iter=5,  # Reduced from 12 to prevent long loops
        )
        agents_by_role[a.role] = agent
        agents_created.append({"role": a.role, "model": a.model, "tools": list(a.tools)})

    tasks: list[Any] = []
    for t in tasks_yaml.tasks:
        if t.agent_role not in agents_by_role:
            raise ValueError(f"Task {t.name} references missing agent_role={t.agent_role}")
        task = Task(
            name=t.name,
            description=t.description,
            expected_output=t.expected_output,
            agent=agents_by_role[t.agent_role],
        )
        tasks.append(task)

    crew = Crew(agents=list(agents_by_role.values()), tasks=tasks, process=Process.sequential, verbose=True)  # Enable verbose
    bundle = CrewBundle(crew=crew, agents=list(agents_by_role.values()), tasks=tasks, agents_created=agents_created)
    return bundle, tasks_yaml, tools_yaml

