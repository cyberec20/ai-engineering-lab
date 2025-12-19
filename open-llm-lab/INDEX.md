# Index

This index maps the portfolio track and its deliverables: **roadmaps, runnable sessions, and architectural experiments**.
It is designed to be read **top-down**, following the evolution from **local LLM foundations** to **agentic systems** and finally to **MCP as an architectural layer**.

This is **not a collection of isolated demos**. Each section builds on the previous one and captures **decisions, tradeoffs, and lessons learned** during real experimentation.

---

## Open-source LLMs — Foundations Track (A → E)

📁 **Purpose**
Establishes a solid, local-first foundation: understanding models, tooling, performance, and early RAG patterns before introducing agents.

📌 **What this section demonstrates**

* Comfort working with **local LLM stacks** (LM Studio, Ollama).
* Benchmarking and model comparison (not just “it runs”).
* Early RAG workflows and document pipelines.
* Transition from raw experimentation to structured flows (Flowise).

🔗 **Navigation**

* [Open-source LLMs (A → E roadmap)](0.Open-source_LLMs/README.md)

  * [General roadmap (HTML)](0.Open-source_LLMs/0_General-Roadmap.html)

---

## Agentic IA — Systems & Orchestration Track

📁 **Purpose**
Moves from single-model usage to **multi-agent reasoning**, orchestration, observability, and system design.

This track intentionally evolves through **multiple frameworks and approaches**, not to chase trends, but to **understand their tradeoffs**.

🔗 **Entry point**

* [Agentic IA overview](1.Agentic_IA/README.md)

---

### Session 1 — Local LLM Basics (Execution, not theory)

📌 **Focus**

* Hardware awareness.
* Local inference basics.
* Minimal client code.
* First reproducible runs.

🔗 [Session 1](1.Agentic_IA/Session1/README.md)

---

### Session 2 — Manual Agent Routing

📌 **Focus**

* Explicit agent roles.
* Router logic.
* Tool calling without abstraction layers.
* Understanding failure modes early.

🔗 [Session 2](1.Agentic_IA/Session2/README.md)

---

### Session 3 — Agent Collaboration

📌 **Focus**

* Multi-agent coordination.
* Shared state.
* Role specialization.
* Early orchestration patterns.

🔗 [Session 3](1.Agentic_IA/Session3/README.md)

---

### Session 3.4 — RAG + Agents (Hybrid Phase)

📌 **Focus**

* RAG integrated into agent workflows.
* Persistence and retrieval tradeoffs.
* Early testing and smoke tests.
* First signs of “system thinking”.

🔗 [Session 3.4](1.Agentic_IA/Session3_4/README.md)

---

### Session 4 — Research Operator (LangGraph + Observability)

📌 **Focus**

* LangGraph as a reasoning backbone.
* Explicit state schemas.
* Observability via LangSmith / LangFuse.
* Debuggability over cleverness.

🔗 [Session 4](1.Agentic_IA/Session4/README.md)

---

### Session 5 — AutoGen-based Research Operator

📌 **Focus**

* Framework-driven agent creation.
* Comparing manual orchestration vs AutoGen.
* Understanding abstraction cost.
* When “automation” helps — and when it doesn’t.

🔗 [Session 5](1.Agentic_IA/Session5/README.md)

---

### Session 5.1 — CrewAI Compatibility Layer

📌 **Focus**

* YAML-driven agent definitions.
* Framework interoperability.
* Evaluating CrewAI vs previous approaches.
* Extracting conclusions even from partial or failed runs.

🔗 [Session 5.1](1.Agentic_IA/Session5_1/README.md)

---

### Session 6 — MCP Trading Desk (Architectural Layer)

📌 **Focus**

* Model Context Protocol (MCP) as a **decoupling layer**.
* Separating:

  * backend logic
  * agent reasoning
  * tool exposure
* MCP tools as reusable, portable interfaces.
* Real-world constraints (MT5 push, stubs, latency, observability).

📌 **Why this matters**
This session is not about trading.
It is about **architecture**: how to expose system capabilities cleanly so **any MCP-capable client** can consume them.

🔗 [Session 6](1.Agentic_IA/Session6/README.md)

---

## How to Read This Repository

* If you are **learning**: follow the order.
* If you are **evaluating skills**: jump to Sessions 4–6.
* If you care about **architecture**: focus on Session 6 + playbooks.
* If you care about **local-first AI**: start at Open-source LLMs.

---

## Final Note

This repository intentionally favors:

* **Runnable systems over toy examples**
* **Clear structure over clever shortcuts**
* **Recorded decisions over polished outcomes**

Each session is an **artifact of thinking**, not a marketing demo.
