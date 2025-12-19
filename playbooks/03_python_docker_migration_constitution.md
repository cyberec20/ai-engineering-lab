# Constitución de Migración de Proyectos Python a Docker y Producción
Version: 1.0

## Propósito
Este documento define las **reglas, cuidados y procedimientos** para migrar proyectos Python existentes
(no diseñados originalmente para contenedores) hacia **Docker** y posteriormente hacia **servidores de producción (VPS, cloud, on‑prem)**.

Este documento tiene precedencia sobre cualquier System Prompt o Project Context.

Su objetivo es:
- Reducir fricción en migraciones.
- Evitar refactors innecesarios.
- Servir como **especificación complementaria** para System Prompts y generación asistida por IA.
- Establecer un estándar reproducible y portable.

---

## Principio rector
> El proyecto **no vive** en la instalación local de Python.
> Vive en:
> - su código,
> - sus dependencias declaradas,
> - su configuración externa,
> - y su contrato de ejecución.

Docker solo encapsula eso.

---

## Sección A — Cuidados ideales desde el inicio del proyecto (golden rules)

### A1. Dependencias explícitas
- Usar `requirements.txt` o `pyproject.toml`.
- Nunca depender de paquetes “instalados a mano” sin declararlos.

### A2. Configuración externa
- Ninguna clave, endpoint o secreto hardcodeado.
- Todo debe provenir de:
  - variables de entorno,
  - o archivos `.env` / YAML cargados al inicio.

### A3. Rutas portables
- Usar `pathlib`.
- Rutas relativas al proyecto.
- Nunca asumir rutas tipo `C:\Users\...`.

### A4. Punto único de arranque
- El proyecto debe poder iniciarse con **un solo comando**:
  - `python main.py`
  - o `uvicorn app.main:app`.

### A5. Evitar dependencias Windows‑only
- COM, Office, GUI, servicios del sistema.
- Si existen, aislarlos como componentes reemplazables.

---

## Sección B — Migración cuando NO se siguieron las reglas

### B1. Congelar el estado actual
Antes de tocar Docker:
- Verificar que el proyecto corre correctamente en local.
- Documentar:
  - comando de arranque,
  - variables necesarias,
  - archivos que lee/escribe.

### B2. Congelar dependencias
Si no existe:
```bash
pip freeze > requirements.txt
```
Esto crea el primer punto reproducible.

### B3. Centralizar configuración
- Crear `settings.py` o equivalente.
- Mover:
  - claves,
  - URLs,
  - flags,
  - rutas,
  a un solo lugar.

### B4. Normalizar rutas
- Reemplazar rutas absolutas por `Path(__file__).parent`.
- Definir carpetas estándar:
  - `/app/data`
  - `/app/logs`

### B5. Identificar dependencias del SO
Clasificar:
- Puras Python → OK.
- Binarias (opencv, torch) → imagen base adecuada.
- Windows‑only → aislar o reemplazar.

---

## Sección C — Dockerización mínima viable

### C1. Dockerfile base recomendado
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### C2. Uso de docker-compose (si aplica)
Usar cuando exista:
- base de datos,
- redis,
- workers,
- múltiples servicios.

### C3. Variables de entorno
- Usar `.env`.
- Nunca subir `.env` real a repositorios.

---

## Sección D — Migración a servidor (VPS / cloud)

### D1. Con Docker
- Copiar repo o imagen.
- Ejecutar `docker compose up -d`.
- Configurar firewall y puertos.
- (Opcional) agregar reverse proxy.

### D2. Sin Docker
- Instalar Python.
- Crear venv.
- Instalar dependencias.
- Configurar systemd / supervisor.
- Mayor riesgo de divergencias.

**Conclusión:** Docker reduce variabilidad.

---

## Sección E — Señales de alerta (technical debt)

- Rutas absolutas Windows.
- Configuración duplicada.
- Scripts que solo funcionan “en mi máquina”.
- Dependencias sin versión.
- Lógica de negocio mezclada con infraestructura.

Cada una aumenta el costo de migración.

---

## Sección F — Uso con IA / System Prompts

Este documento puede usarse como:
- input obligatorio en prompts de generación de código,
- checklist de validación,
- contrato de arquitectura.

Ejemplo:
> “Genera este proyecto cumpliendo estrictamente la Constitución de Migración Python‑Docker v1.0 adjunta.”

---

## Cierre
Migrar a Docker **siempre es posible**.
La diferencia está en:
- cuánto duele,
- cuánto refactor requiere,
- y cuán predecible es el resultado.

Este documento existe para que ese dolor sea mínimo.
