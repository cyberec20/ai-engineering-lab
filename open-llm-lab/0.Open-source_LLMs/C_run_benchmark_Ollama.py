#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Benchmark básico entre modelos locales en Ollama con AUTO-CALIFICACIÓN.

Modelos probados:
- qwen2.5:7b
- deepseek-r1:8b

Requisitos:
1. Tener Ollama instalado y corriendo (ollama serve / app abierta).
2. Tener ya descargados los modelos:
   - ollama pull qwen2.5:7b
   - ollama pull deepseek-r1:8b
3. Python 3.10+ y 'pip install requests' en el environment que uses.

Salida:
- Muestra resultados en consola.
- Guarda todo en: benchmark_results_ollama_qwen_vs_deepseek.json
"""

import json
import time
from dataclasses import dataclass
from typing import List, Dict, Any

import requests

# ---------------------------------------------------------
# CONFIGURACIÓN BÁSICA OLLAMA
# ---------------------------------------------------------

# Endpoint de chat de Ollama (no streaming)
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

MODEL_NAME_QWEN = "qwen2.5:7b"
MODEL_NAME_DEEPSEEK = "deepseek-r1:8b"

# Dimensiones de score
SCORE_DIMENSIONS = [
    ("claridad", "Qué tan clara y comprensible es la respuesta."),
    ("precision", "Qué tan correcta es la información (sin inventar datos)."),
    ("razonamiento", "Qué tan bien justificada y explicada está la respuesta."),
    ("utilidad", "Qué tan útil es la respuesta para aplicar en la práctica."),
    ("estilo", "Qué tan bien se adapta el tono a Franklin (directo, humano, sin relleno)."),
]


# ---------------------------------------------------------
# TESTS
# ---------------------------------------------------------

@dataclass
class TestCase:
    id: int
    name: str
    description: str
    prompt: str


TESTS: List[TestCase] = [
    TestCase(
        1,
        "Razonamiento lógico — tren",
        "Capacidad de seguir un razonamiento paso a paso.",
        "Un tren sale de Ciudad A a las 8:00 a.m. viajando a 80 km/h. "
        "Otro tren sale de Ciudad B (a 300 km de Ciudad A) a las 9:00 a.m. viajando a 100 km/h "
        "en dirección a Ciudad A. ¿A qué hora se encuentran? Explica tu razonamiento paso a paso."
    ),
    TestCase(
        2,
        "Explicación técnica simple",
        "Explicar un concepto técnico en lenguaje sencillo.",
        "Explícame qué es un modelo de lenguaje grande (LLM) como si tuviera 12 años. "
        "Usa ejemplos concretos y evita jerga técnica innecesaria."
    ),
    TestCase(
        3,
        "Programación — función simple",
        "Capacidad de escribir código claro y correcto.",
        "Escribe una función en Python llamada `contar_palabras` que reciba un texto y "
        "devuelva un diccionario con cada palabra como clave y su número de apariciones como valor. "
        "Ignora mayúsculas/minúsculas y signos de puntuación básicos. Luego da un ejemplo de uso."
    ),
    TestCase(
        4,
        "Traducción y matiz",
        "Mantener matices al traducir.",
        "Traduce al inglés esta frase manteniendo el matiz emocional: "
        "\"A veces siento que avanzo lento, pero cuando miro hacia atrás, "
        "veo que realmente he construido mucho más de lo que creía.\" "
        "Luego explica en 2–3 líneas por qué elegiste esa traducción."
    ),
    TestCase(
        5,
        "Mentoría personal / foco",
        "Calidad de consejos personalizados para foco y estrategia.",
        "Imagina que soy Franklin, multifacético, con muchos proyectos de IA y SaaS. "
        "Dame 5 recomendaciones concretas para mantener el foco sin apagar mi curiosidad, "
        "en un tono directo y humano, sin frases vacías."
    ),
]


# ---------------------------------------------------------
# LLAMADAS A LA API DE OLLAMA
# ---------------------------------------------------------

def call_ollama_chat(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    json_mode: bool = False,
) -> Dict[str, Any]:
    """
    Llama a /api/chat de Ollama (sin streaming) y devuelve:
    - content: texto generado
    - elapsed: tiempo en segundos
    - raw: respuesta completa
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    # JSON mode (intenta forzar salida JSON bien formada)
    if json_mode:
        payload["format"] = "json"

    t0 = time.time()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    elapsed = time.time() - t0
    resp.raise_for_status()
    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return {"content": content, "elapsed": elapsed, "raw": data}


def generate_answer(model: str, prompt: str) -> Dict[str, Any]:
    """Primera llamada: respuesta normal al prompt."""
    messages = [
        {
            "role": "system",
            "content": "Eres un asistente útil que responde en español neutro, directo y sin relleno innecesario.",
        },
        {"role": "user", "content": prompt},
    ]
    return call_ollama_chat(model, messages, temperature=0.3, json_mode=False)


def strip_code_fences(text: str) -> str:
    """Quita ```json ...``` o ```...``` si el modelo lo devuelve así."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
    return text


def parse_json_scores(text: str) -> Dict[str, Any]:
    """Intenta parsear el JSON de scores que devuelve el modelo."""
    cleaned = strip_code_fences(text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def ask_self_scores(model: str, test: TestCase, answer_text: str) -> Dict[str, Any]:
    """Segunda llamada: el modelo se auto-califica en varias dimensiones."""
    dims_desc = "\n".join([f"- {k}: {d}" for k, d in SCORE_DIMENSIONS])

    eval_prompt = (
        "Vas a evaluar HONESTAMENTE la calidad de la respuesta que diste.\n\n"
        f"Pregunta original:\n{test.prompt}\n\n"
        f"Tu respuesta fue:\n{answer_text}\n\n"
        "Debes poner una nota de 0 a 10 (pueden ser decimales) en las siguientes dimensiones:\n"
        f"{dims_desc}\n\n"
        "Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:\n\n"
        "{\n"
        '  \"claridad\": number,\n'
        '  \"precision\": number,\n'
        '  \"razonamiento\": number,\n'
        '  \"utilidad\": number,\n'
        '  \"estilo\": number,\n'
        '  \"comentario_general\": \"texto breve con tu reflexión honesta\"\n'
        "}\n\n"
        "NO añadas explicación fuera del JSON, no añadas texto antes ni después."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Eres un evaluador estricto y honesto. Tu tarea es puntuar tu respuesta anterior "
                "de forma objetiva, sin intentar quedar bien."
            ),
        },
        {"role": "user", "content": eval_prompt},
    ]

    res = call_ollama_chat(model, messages, temperature=0.0, json_mode=True)
    scores = parse_json_scores(res["content"])
    return {"raw_text": res["content"], "scores": scores, "elapsed": res["elapsed"]}


# ---------------------------------------------------------
# LÓGICA DE BENCHMARK
# ---------------------------------------------------------

def run_benchmark_for_model(model_name: str) -> Dict[int, Dict[str, Any]]:
    results: Dict[int, Dict[str, Any]] = {}

    print("\n==============================")
    print(f"Benchmark para modelo (Ollama): {model_name}")
    print("==============================\n")

    for test in TESTS:
        print(f"▶ Test {test.id} — {test.name}")
        print(f"  Descripción: {test.description}")

        # 1) Respuesta normal
        ans = generate_answer(model_name, test.prompt)
        answer_text = ans["content"]
        print(f"  Tiempo respuesta: {ans['elapsed']:.2f} s")

        # 2) Auto-evaluación
        eval_res = ask_self_scores(model_name, test, answer_text)
        scores = eval_res["scores"]
        if scores:
            print(
                "  Scores auto-evaluados: "
                + ", ".join(
                    [f"{k}={scores.get(k, 'NA')}" for k, _ in SCORE_DIMENSIONS]
                )
            )
        else:
            print("  ⚠ No se pudo parsear JSON de scores; se dejan vacíos.")

        results[test.id] = {
            "test_id": test.id,
            "test_name": test.name,
            "prompt": test.prompt,
            "description": test.description,
            "answer": {
                "text": answer_text,
                "elapsed_seconds": ans["elapsed"],
            },
            "self_eval": {
                "scores": scores,
                "raw_eval_text": eval_res["raw_text"],
                "elapsed_seconds": eval_res["elapsed"],
            },
        }

        print("")

    return results


def compute_averages(all_results: Dict[int, Dict[str, Any]]) -> Dict[str, float]:
    sums = {key: 0.0 for key, _ in SCORE_DIMENSIONS}
    counts = {key: 0 for key, _ in SCORE_DIMENSIONS}

    for res in all_results.values():
        scores = res.get("self_eval", {}).get("scores", {})
        for key, _ in SCORE_DIMENSIONS:
            val = scores.get(key)
            if isinstance(val, (int, float)):
                sums[key] += float(val)
                counts[key] += 1

    averages: Dict[str, float] = {}
    for key, _ in SCORE_DIMENSIONS:
        if counts[key] > 0:
            averages[key] = round(sums[key] / counts[key], 2)
        else:
            averages[key] = None
    return averages


def print_summary(model_name: str, averages: Dict[str, float]):
    print(f"\nResumen de promedios para: {model_name}")
    print("------------------------------------")
    for key, desc in SCORE_DIMENSIONS:
        val = averages.get(key)
        txt = f"{val:.2f}" if isinstance(val, (int, float)) and val is not None else "sin datos"
        print(f"{key:13s}: {txt}")
    print("")


def main():
    # Ejecutar benchmark para ambos modelos
    qwen_results = run_benchmark_for_model(MODEL_NAME_QWEN)
    deepseek_results = run_benchmark_for_model(MODEL_NAME_DEEPSEEK)

    # Calcular promedios
    qwen_avg = compute_averages(qwen_results)
    deepseek_avg = compute_averages(deepseek_results)

    # Imprimir resumen comparativo
    print("\n================ RESUMEN GLOBAL (OLLAMA) ================")
    print_summary(MODEL_NAME_QWEN, qwen_avg)
    print_summary(MODEL_NAME_DEEPSEEK, deepseek_avg)

    # Guardar JSON completo
    all_results = {
        "qwen_model": MODEL_NAME_QWEN,
        "deepseek_model": MODEL_NAME_DEEPSEEK,
        "score_dimensions": [d[0] for d in SCORE_DIMENSIONS],
        "qwen": qwen_results,
        "deepseek": deepseek_results,
        "qwen_averages": qwen_avg,
        "deepseek_averages": deepseek_avg,
    }

    out_file = "benchmark_results_ollama_qwen_vs_deepseek.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n📁 Resultados detallados guardados en {out_file}")


if __name__ == "__main__":
    main()
