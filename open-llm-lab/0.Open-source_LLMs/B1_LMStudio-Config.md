---

## 1️⃣ Pantalla “Nice! Let’s get your first model”

Lo que ves es la sugerencia de LM Studio para bajar:

> `openai / gpt-oss-20b` (20B, 12.11 GB)

Para tu plan y para empezar:

* **NO** vamos a descargar ese como primero.

  * Es grande (20B), pesado en VRAM y disco.
  * Queremos empezar con Qwen / DeepSeek más ligeros y versátiles.

### Qué hacer aquí:

1. **Desmarca** la casilla de abajo si está marcada:

   * `Enable local LLM service on login`
   * Así LM Studio **no** levanta servicios al inicio de Windows sin que tú lo decidas.
2. Arriba a la derecha, pulsa **“Skip →”** (O “Omitir” si te sale en español).

Con eso entras al interfaz principal de LM Studio sin descargar aún este modelo.

---

## 2️⃣ Abrir configuración básica (Settings)

Una vez dentro:

1. Busca el **icono de engranaje** ⚙️ (normalmente arriba a la derecha).
2. Ábrelo → se abre el panel de **Settings**.

Nos importan tres cosas ahora: **GPU**, **VRAM** y **servidor local**.

---

## 3️⃣ Ajustar el uso de GPU (muy importante)

En Settings:

1. Ve a la sección tipo **“Compute” / “Performance” / “Hardware”** (según versión).
2. Asegúrate de que esté seleccionado como dispositivo:

   * Algo como **“NVIDIA RTX 5060 Ti (CUDA)”** o similar.
3. Si hay opción de **“Prefer GPU / Prefer CUDA”**, actívala.

👉 Esto garantiza que los modelos corran **en tu tarjeta gráfica** y no solo en CPU.



Perfecto Franklin.
**Esa es EXACTAMENTE la pantalla correcta** para configurar el GPU en LM Studio.
Estás en:
➡️ *Mission Control → Hardware → System Resources*

Vamos a verificar punto por punto y ajustar lo necesario.

---

# ✅ **Paso 3 — Confirmar GPU**

En tu captura veo:

* **NVIDIA GeForce RTX 5060 Ti** detectada correctamente
* Con icono **CUDA**
* VRAM: **15.93 GB** (perfecto)

👉 **Esto confirma que LM Studio está usando tu GPU real.**
No falta nada aquí.

---

# ✅ **Paso 3.1 — Ajustes recomendados en esta pantalla**

Ahora revisamos lo que debes activar/desactivar:

---

## 🔹 1. **“Limit Model Offload to Dedicated GPU Memory”**

**OFF**

### ¿Por qué?

* OFF = más flexible
* Permite que parte del modelo pase temporalmente a RAM si hace falta
* Evita errores de “out of memory” cuando cargas modelos 14B o superiores

Si lo activaras ON, serías más estricto y podrías impedir cargar modelos que sí caben combinando VRAM+RAM.

---

## 🔹 2. **NVIDIA GPU:**

**ON** Switch encendido (azul).

---

## 🔹 3. “Offload KV Cache to GPU Memory”

**ON** es el ajuste ideal para rendimiento:

* Hace más rápido el inference
* Usa tu VRAM de forma eficiente
* Si Tu GPU tiene 16 GB, no hay problema

---

## 🔹 4. “Guardrails”

Por default puede estar en:

> `Strict (Strong precautions against overload)`

Lo ideal para tu plan de aprendizaje es:

👉 **Cambiarlo a “Balanced” o “Relaxed”**

### ¿Por qué?

* *Strict* evita cargar modelos grandes (muy conservador)
* *Balanced* protege tu sistema pero permite más modelos
* *Relaxed* te deja cargar casi cualquier GGUF que entre en VRAM+RAM

**Recomendación personalizada:**
➡️ **Balanced** (mejor balance)

Haz clic en el menú y cambia a “Balanced”.

---

# 🟢 **En resumen, basado en tu captura:**

Aquí está tu configuración óptima:

| Opción                             | Estado recomendado    | Tu estado actual        |
| ---------------------------------- | --------------------- | ----------------------- |
| **NVIDIA GPU**                     | ON                    | ✔ Correcto              |
| **Offload KV Cache to GPU Memory** | ON                    | ✔ Correcto              |
| **Limit Model Offload to GPU**     | OFF                   | ✔ Correcto              |
| **Guardrails**                     | Balanced                | ❗ Actualmente en Strict |

Solo necesitas cambiar **Strict → Balanced**.

---

## 4️⃣ Opciones de arranque / servidor

---

> **Local LLM Services**
> `[ ] Enable local LLM service`

Ese **es** el interruptor que antes estaba en “General”.

---

# 📌 **¿Qué hacer con este ajuste?**

**DESACTIVADO**
**No lo marques.**

### ¿Por qué?

* Si lo activas, LM Studio levantará un servidor local **cada vez que abras la app**.
* Todavía **no** queremos que se ejecute como servicio permanente.
* Más adelante, cuando conectes LM Studio con:

  * scripts Python
  * RAG local
  * extensiones de VS Code
  * aplicaciones que llamen a LM Studio como API

…entonces lo activaremos intencionadamente.

| Ajuste                          | Ubicación                | Estado  |
| ------------------------------- | ------------------------ | ------- |
| **Enable Local LLM Services**   | App Settings → Developer | **OFF** |
| **Auto-start server on login**  | (ya no existe en 0.3.32) | —       |
| **Auto-start server on launch** | (ya no existe en 0.3.32) | —       |
| **Server port**                 | (panel ya no existe aún) | —       |

✨ La versión 0.3.32 simplificó el servidor local; solo hay un switch ahora.

---

## 5️⃣ Opciones de arranque / servidor

En otra sección (a veces “Server” o “Advanced”):

* Si ves algo como **“Start local LLM server on launch / on login”**:

  * Déjalo **desactivado** por ahora.
  * Más adelante, cuando integremos LM Studio con otras apps, podemos decidir si quieres que el servidor se encienda siempre.

---

## 6️⃣ Guardar cambios

La mayoría de opciones en LM Studio se guardan **automáticamente** al cambiar el valor.

Solo verifica que:

* La GPU seleccionada sea la NVIDIA.
* No se está autoejecutando nada que no quieras.

---

## 7️⃣ Siguiente paso: descargar **el primer modelo correcto**

Desde la pantalla principal de LM Studio:

1. Ve a la pestaña **“Discover”** o **“Models”**.

2. En la barra de búsqueda, escribe:

   **`qwen 2.5 7b instruct`**

3. Elige la variante **Instruct** (no la base) y en formato **GGUF** si te deja elegir.

4. Descárgala y, cuando termine, abre un chat con ese modelo.

Primera prueba:

* Pregúntale algo sencillo de tu día (“ayúdame a organizar mi tarde con bloques de trabajo y descanso”) para comprobar que todo fluye.

---

# 🟣 **Por qué este Qwen2.5-7B-Instruct-GGUF es el correcto**

Vamos línea por línea para que tengas claridad total:

* ✔ **Q4_K_M** (mejor cuantización para empezar)
* ✔ **Versión Instruct**
* ✔ **7B** (tamaño ideal para tu GPU de 16GB VRAM)
* ✔ **Long context 128k tokens** (ultra poderoso)
* ✔ **Repositorio confiable (lmstudio-community)**

Este modelo es **perfecto como tu primer modelo base**.

### ✔ Nombre:

**Qwen2.5-7B-Instruct-GGUF**
→ Coincide exactamente con lo que buscamos.

### ✔ Cuantización disponible:

**Q4_K_M (4.68 GB)**
→ super liviano, rápido y con excelente calidad.
→ carga sin problemas incluso en GPUs de 8GB.
→ tú tienes 16GB, así que corre como avión.

### ✔ Fuente:

**lmstudio-community**
→ significa que fue adaptado por LM Studio mismo
→ mayor compatibilidad
→ no necesitas buscar versiones externas de bartowski o triangle104
→ todo funciona out-of-the-box

### ✔ Soporte 128k tokens

→ Esto lo vuelve ideal para:

* análisis de PDFs grandes
* documentos largos
* programar
* resúmenes extensos
* prompts complejos

Pocos modelos 7B tienen 128k context → este sí.

---

# 🟢 **¿Qué hacer? (paso preciso)**

### 1. Haz clic en el botón verde:

```
Download (4.68 GB)
```

### 2. Espera a que el modelo termine de bajar.

### 3. Dale “Load Model”.

### 4. Se abrirá una ventana de chat usando este modelo.

### 5. Prueba escribiendo:

```
Hola, soy User. Por favor confirma qué modelo eres,
cuál es tu contexto máximo, y cuál es tu cuantización.
```

Debe responder rápido y claro.

---

# 🧠 **Resultado final esperado**

Cuando cargues este modelo:

* LM Studio usará tu GPU NVIDIA automáticamente
* Offload KV estará ON
* Guardrails “Balanced” te permitirá cargar sin advertencias
* La inferencia será rápida (especialmente en Q4_K_M)
* Ya tendrás tu **entorno local funcional** y listo para seguir con el pensum

---

### **DeepSeek-R1-Distill-Qwen-7B-GGUF (Q4_K_M)**

Repositorio: `lmstudio-community/DeepSeek-R1-Distill-Qwen-7B-GGUF`

✔ Es el **modelo oficial distilado por DeepSeek**
✔ La cuantización fue hecha por **bartowski** (el más confiable en GGUF)
✔ Es **Q4_K_M** → la cuantización que tú sí puedes correr con calidad
✔ Es compatible con tu **RTX 4060 Ti 16GB** (sobra VRAM)
✔ Es la versión exacta para comparar contra **Qwen2.5-7B-Instruct**

👉 **Sí, es ese**. Descárgalo.

---

