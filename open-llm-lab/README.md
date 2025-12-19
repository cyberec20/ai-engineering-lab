---

## AI Engineering Lab

**Local LLMs · Agentic Systems · MCP · Real Projects**

This repository is a **hands-on engineering lab** focused on building **local-first AI systems** and **agentic architectures** with real, runnable projects.

It is **not a collection of toy demos** or generic tutorials.
Each folder represents an exercise designed to mirror real-world constraints: architecture decisions, tradeoffs, observability, and iteration.

You’ll find:

* Local LLM experimentation (Ollama, LM Studio, benchmarks)
* Agentic systems (LangGraph, AutoGen-style patterns)
* RAG pipelines and research operators
* MCP (Model Context Protocol) servers exposing tools cleanly
* Observability with LangSmith / LangFuse
* Interactive HTML roadmaps and checklists

---

## 📍 How to navigate this repo

This repo is organized into **two main learning tracks**, designed to be explored progressively or independently.

### 1️⃣ Open LLM Lab (Foundations)

Path: `open-llm-lab/0.Open-source_LLMs/`

Focus:

* Running and comparing open-source LLMs locally
* Benchmarks, embeddings, RAG basics
* Flowise, Ollama, LM Studio
* Practical tooling and environment setup

This track answers:
**“How do I work seriously with local LLMs?”**

---

### 2️⃣ Agentic AI Lab (Systems & Architecture)

Path: `open-llm-lab/1.Agentic_IA/`

Focus:

* Multi-agent systems
* Orchestration patterns
* LangGraph-based pipelines
* AutoGen-style agents
* MCP servers exposing tools
* Observability and debugging

This track answers:
**“How do I design AI systems that behave like software, not prompts?”**

---

## 🗺️ Start here (recommended)

* **Overview & map of the entire lab:**
  👉 `open-llm-lab/INDEX.md`

* **If you want to run something quickly:**
  Pick any session inside `1.Agentic_IA/` and open its `README.md`.
  Each session includes:

  * Roadmap (often HTML)
  * Setup instructions
  * Runnable scripts
  * Clear learning outcome

---

## 🧪 About the exercises

These are called “sessions”, but they are **engineering exercises**, not classroom lessons.

They are:

* Runnable
* Imperfect by design
* Iterative
* Focused on learning through building

Examples:

* A research operator that doesn’t “do everything”, but shows how to structure one
* A trading desk that doesn’t trade, but exposes decision pipelines via MCP
* Agent systems that evolve across sessions instead of being rewritten

Each session leaves **valid architectural conclusions**.

---

## 🧰 Requirements (general)

Most exercises assume:

* Python 3.10+
* Node.js (for MCP Inspector / tooling)
* Ollama or LM Studio
* Local environment (Windows-focused, but adaptable)

Session-specific requirements are documented **inside each session folder**.

---

## 🎯 Who this repo is for

* Engineers exploring **local AI systems**
* Practitioners designing **agentic architectures**
* Technical leaders evaluating **AI engineering maturity**
* Learners who want **project-grade guidance**, not slides

---

## 📌 Final note

This repository is meant to be **extended**, not consumed passively.

Fork it. Modify it. Replace models. Break things.
That’s the point.

---
