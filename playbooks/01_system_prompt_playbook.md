# System Prompt / Project Context Playbook (v1)
## Marco genérico para arrancar proyectos con Codex/VS Code + ChatGPT Web

Este documento es un **molde reutilizable** para crear “System Prompts” (o “Project Contexts”) ejecutables:
un artefacto único que combina **objetivo**, **arquitectura mínima**, **reglas**, **contratos**, **comandos** y **criterios verificables**.
El fin es **reducir iteraciones**, evitar ambigüedad y asegurar trazabilidad.

> Principio: **guía contractual mínima, no camisa de fuerza**.  
> Estandariza lo importante; deja espacio para lo específico del proyecto.

---

## 1) Estructura recomendada
El documento debe tener **dos zonas** claramente separadas:

### A) INMUTABLE (Contrato)
Lo que **no debe cambiar** en cada iteración (o cambia rarísimo y con versión mayor):
- Entorno y restricciones (OS, puertos, local/cloud, rutas base, herramientas permitidas)
- Objetivo y no-goals (qué sí y qué no)
- Arquitectura mínima (módulos, boundaries, responsabilidades)
- Contratos de interfaces (APIs, tools, schemas, formatos guía)
- Logging / observabilidad (qué se loggea y cómo)
- Reglas de seguridad/robustez (errores explícitos, fallback)
- Guardrails (no reescribir, no introducir deps innecesarias, compatibilidad)
- Criterios de éxito finales (definition of done)

### B) MUTABLE (Estado)
Lo que **sí cambia** con frecuencia (cada iteración):
- Estado actual (checklist de progreso)
- Decisiones recientes (y por qué)
- Bugs conocidos / riesgos / deuda
- Backlog inmediato (top 5 / top 10)
- Comandos canónicos (setup/run/test/inspect/reset) si evolucionan

---

## 2) Plantilla base (copiar/pegar)
> Ajusta los headings al gusto, pero conserva la separación INMUTABLE vs MUTABLE.

```md
# SYSTEM PROMPT / PROJECT CONTEXT — <Proyecto> (vX)
## <Tagline corto> · <Stack> · <Puerto> · <Local/Cloud>

> Nota: Esto es una guía contractual mínima. No es camisa de fuerza.

---

## 0) Versionado y trazabilidad
- Documento: <nombre>
- Versión: vX
- Base: v(X-1) (si aplica)
- Fecha: YYYY-MM-DD (TZ)
- Cambios vs v(X-1):
  - ...
  - ...

---

## 1) INMUTABLE — Contexto fijo (NO MODIFICAR)
### 1.1 Entorno
- OS: <Windows/Linux/Mac>
- Root/Workspace: <ruta>
- Puerto(s): <lista>
- Modo: <local-only / cloud / híbrido>
- Runtime: <python/node/...> + versión
- Package manager: <uv/pip/npm/...>
- Restricciones: <sin APIs externas, sin GPU, etc.>

### 1.2 Rol del asistente
Eres el orquestador técnico. Prioriza ejecución end-to-end, trazabilidad y reproducibilidad.
No inventes requisitos. No silencien errores.

---

## 2) INMUTABLE — Objetivo técnico
### 2.1 Objetivo
Construir <X> que haga <Y> para <Z>.

### 2.2 No-goals
- ...
- ...

---

## 3) INMUTABLE — Arquitectura mínima obligatoria (GUÍA)
```text
<estructura de carpetas propuesta>
```
Reglas:
- Se permite añadir archivos.
- No mezclar responsabilidades (UI vs lógica, adapters vs core, etc.).

---

## 4) INMUTABLE — Interfaces / Contratos
### 4.1 Endpoints / Tools / APIs (guía)
- <endpoint/tool>: request/response (JSON guía)
- <endpoint/tool>: ...

### 4.2 Reglas de compatibilidad
- Cambios aditivos.
- No romper payloads existentes sin bump mayor y plan de migración.

---

## 5) INMUTABLE — Observabilidad (logging/tracing)
- Formato: JSONL / structured logs
- Campos mínimos: event, timestamp, status, details
- Carpetas: logs/runtime, logs/tests, ...
- No silenciar excepciones: log + devolver error explícito.

---

## 6) INMUTABLE — Guardrails (para converger rápido)
1. No romper lo que ya funciona: extiende lo mínimo.
2. Evitar dependencias nuevas sin necesidad.
3. Preferir lo simple y estándar.
4. Errores explícitos y temprano.
5. Separación de responsabilidades.
6. Compatibilidad y rollback plan.

---

## 7) INMUTABLE — Smoke tests / Acceptance checks (OBLIGATORIOS)
- <check verificable 1>
- <check verificable 2>
- ...
(“verificable” = se puede probar con comando o request real)

---

## 8) MUTABLE — Estado del proyecto (EDITABLE)
- Estado actual:
  - [ ] ...
  - [ ] ...
- Decisiones recientes:
  - ...
- Bugs/riesgos:
  - ...
- Backlog inmediato (Top 5):
  1) ...
  2) ...
  3) ...
  4) ...
  5) ...

---

## 9) MUTABLE — Comandos canónicos (EDITABLE)
Setup:
- ...
Run:
- ...
Test/Smoke:
- ...
Inspect/Debug:
- ...
Reset local (seguro):
- ...

---

## 10) INMUTABLE — Criterio de éxito (Definition of Done)
- ...
- ...
```

---

## 3) Elementos “de alto impacto” (para bajar iteraciones)
Estos son los que más ayudan a que Codex/VS Code converja rápido:

### 3.1 Guardrails explícitos
Evitan que el asistente “se vaya de viaje”:
- “Si algo ya funciona, **no lo reescribas**: añade lo mínimo.”
- “No agregues dependencias si no son imprescindibles.”
- “No mezcles UI con core; no mezcles adapters con lógica.”
- “Falla rápido con mensajes claros; no adivines estados.”

### 3.2 Comandos canónicos
Un bloque pequeño, pero crítico:
- setup
- run
- test/smoke
- inspect/debug
- reset local (seguro)

### 3.3 Acceptance checks verificables
No basta “funciona”: define pruebas concretas:
- “`GET /health` responde 200”
- “`POST /evaluate` produce JSON con campos X/Y”
- “Los logs JSONL contienen `event=tool_call`”
- “El inspector lista tools y ejecuta una tool”

### 3.4 Contratos de payload como “guía mínima”
Incluye ejemplos **cortos** de request/response para:
- dar forma al API
- permitir UI/smoke tests
- mantener compatibilidad

> Regla: ejemplos cortos + campos clave. No sobre-especificar.

### 3.5 Arquitectura mínima con responsabilidades
No un diagrama bonito: **carpetas y roles** (qué vive dónde).

---

## 4) Reset local (seguro) — recomendación
Si vas a crear `Reset.bat` o equivalente:
- **NO** usar `docker system prune`
- **NO** tocar volúmenes globales
- Solo limpiar artefactos del proyecto:
  - logs temporales
  - caches del proyecto
  - outputs generados

---

## 5) Rollback / “No romper lo que funciona”
Añade un mini plan:
- Si un cambio rompe X, volver a v(N-1) o revertir commit Y
- Cambios **aditivos** por defecto
- Si rompes compatibilidad: bump mayor + migración

---

## 6) Checklist final (para evaluar si tu System Prompt está “listo”)
- [ ] Separación INMUTABLE vs MUTABLE clara
- [ ] Objetivo y no-goals explícitos
- [ ] Arquitectura mínima con responsabilidades
- [ ] Contratos de interfaces con ejemplos guía
- [ ] Guardrails escritos (no reescribir, no deps extra)
- [ ] Comandos canónicos completos
- [ ] Smoke/acceptance checks verificables
- [ ] Logging/tracing definido (JSONL, campos mínimos)
- [ ] Reset local seguro definido
- [ ] Definition of Done claro

---

## 7) Cómo usar este playbook en tu flujo
1) Copia la plantilla base.
2) Completa INMUTABLE primero (contrato).
3) Completa MUTABLE con backlog y comandos.
4) Pasa el System Prompt a Codex y ejecuta en iteraciones cortas.
5) Cada iteración: actualiza solo MUTABLE (estado/bugs/backlog).

---

**Playbook v1**
