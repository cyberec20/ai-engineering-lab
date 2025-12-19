---

# ✅ **CHECKLIST DE INSTALACIÓN — SESIÓN 1**

**LM Studio + Ollama + Estructura de Carpetas (Optimizado para RTX 5060 Ti 16 GB)**

---

# 📂 **A. Crear la estructura base en tu PC**

Crea esta carpeta raíz:

```
C:\IA_Local\
```

Dentro, crea:

```
C:\IA_Local\
   ├── models_llm\
   │      ├── qwen\
   │      ├── deepseek\
   │      ├── llama\
   │      └── otros\
   ├── models_img\
   │      ├── sdxl\
   │      ├── controlnet\
   │      └── loras\
   ├── models_video\
   │      ├── wan\
   │      └── wanGP\
   ├── comfyui\
   ├── ollama\
   ├── scripts\
   └── docs\
```

Esto te permitirá crecer sin caos conforme avances.

---

# 🧰 **B. Instalaciones necesarias**

## 1. **Actualizar Drivers NVIDIA**

Asegúrate de estar en **Game Ready Driver / Studio Driver** más reciente.

### Descarga:

[https://www.nvidia.com/Download/index.aspx](https://www.nvidia.com/Download/index.aspx)

---

## 2. **Instalar Python 3.11**

Usaremos Python más adelante para scripts y RAG.

Descarga aquí:
[https://www.python.org/downloads/release/python-3110/](https://www.python.org/downloads/release/python-3110/)

✔ Marca **"Add Python to PATH"** al inicio.

---

## 3. **Instalar Git**

Para clonar repos y mantener proyectos limpios:

[https://git-scm.com/download/win](https://git-scm.com/download/win)

*(Puedes no usar Git al inicio, pero será esencial a partir de mes 2).*

---

# 🧠 **C. LM Studio — Instalación y Configuración Inicial**

## 1. Descarga LM Studio

[https://lmstudio.ai](https://lmstudio.ai)

✔ Instala la versión Windows (EXE).
✔ No requiere configuración avanzada.

---

## 2. Configuración inicial

Dentro de LM Studio:

### 🔧 Preferencias recomendadas:

* **Compute Device:** selecciona tu **RTX (NVIDIA CUDA)**
* **Max VRAM Usage:** 90%
* **Threading:** Auto
* **Context Length:** 8192 o más, según modelo

Esto te da un rendimiento perfecto con tu GPU sin “comerse” toda la memoria.

---

# 🧠 **Modelos recomendados para LM Studio (primeros 3 días)**

*Todos funcionan PERFECTO en 16 GB VRAM.*

## ⭐ **1. Modelo General (Chat / Ideas / Vida diaria / Explicaciones)**

### ✅ **Qwen 2.5 – 7B Instruct (GGUF recommended)**

**Por qué:**

* Balance espectacular entre velocidad y calidad.
* Estable, lógico, preciso.

**Búscala en LM Studio:**
`qwen-2.5-7b-instruct-q4_k_m.gguf`
(Usa Q4_K_M para mejor equilibrio)

---

## ⭐ **2. Modelo de Razonamiento (matemática, análisis técnico, lógica)**

### ✅ **DeepSeek R1 - 8B / 14B (Distilled)**

**Por qué:**

* Tiene razonamiento tipo “o1-style”, pero local.
* Resuelve tareas complejas paso a paso.

**En LM Studio**
Busca:
`deepseek-r1-distill-7b` o `deepseek-r1-distill-14b`
Si no hay 14B, instala el 7B que funciona excelente.

---

## ⭐ **3. Modelo de Programación (MQL5, Python, Flutter)**

### ✅ **Qwen 2.5 – Coder 7B (o 14B si lo encuentras)**

**Por qué:**

* Extraordinario en explicaciones de código.
* Muy bueno para depuración, refactorización y lógica.
* Se lleva bien con tus proyectos (MQL5, Flutter, Python).

**Nombre típico:**
`qwen2.5-coder-7b-instruct`

---

## ⭐ **4. Modelo alternativo para español / redacción**

### ✅ **Llama 3.1 – 8B Instruct**

**Por qué:**

* Muy fluido en español.
* Seguro y estable.
* Excelente para escribir, corregir textos, contenido, documentos.

**Nombre en LM Studio:**
`llama-3.1-8b-instruct-q4_k_m.gguf`

---

# 🚀 **Plan de descarga en orden**

### ✔ 1

* Qwen 2.5 7B Instruct
* Llama 3.1 8B

### ✔ 2

* DeepSeek R1 (distill) 7B
* Qwen2.5 Coder 7B

### ✔ 3

* Opcional: algún 14B (si quieres probar modelos grandes)
  Recomiendo: **Qwen 2.5 14B Instruct** (Q4_K_M)

---

# 🟦 **D. OLLAMA — Instalación y Configuración**

## 1. Descarga

[https://ollama.com/download](https://ollama.com/download)

## 2. Instalación

Siguiente → siguiente → listo.

---

## 3. Verificar instalación

Abre PowerShell:

```
ollama --version
```

---

## 4. Probar un modelo en 10 segundos

```
ollama run qwen2:7b
```

o mejor:

```
ollama run deepseek-r1:7b
```

---

# 🧠 **Modelos recomendados para Ollama**

*(Versión CLI)*

**Primero descarga:**

```
ollama pull qwen2.5:7b
ollama pull deepseek-r1:7b
```

**Opcionales robustos:**

```
ollama pull qwen2.5:14b
ollama pull llama3.1:8b
```

**Y un modelo de coder:**

```
ollama pull qwen2.5-coder:7b
```

---

# 💻 **E. Scripts Básicos para SESIÓN 1**

📌 Crea un archivo `script_chat.py` en:

```
C:\IA_Local\scripts\
```

Contenido:

```python
import requests

prompt = "Explica como organizar mi día de forma clara y práctica."

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:7b",
        "prompt": prompt
    },
    stream=False
)

print(response.json()['response'])
```

Correr:

```
python script_chat.py
```

— Con esto ya puedes **llamar tu modelo local desde Python**.
Es justo el puente para tus apps, tu EA o cualquier cosa que construyas.

---

# 🧩 **¿Qué sigue?**

Cuando tú digas, preparo:

### 🔵 **Sesión 2 – Prompt Engineering**

Tu set completo de prompts maestros, listos para usar.

### 🟠 **Sesión 3 – RAG con tus documentos (PDF, Word, notas, EAs, etc.)**

---
