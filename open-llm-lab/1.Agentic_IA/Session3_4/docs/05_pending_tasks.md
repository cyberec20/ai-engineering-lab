# Tareas Pendientes - Stock Picker 3.4

## ??? Completadas

- [x] Corregir error de sintaxis en `WRITER_SYSTEM` (stock_picker.py:443-450)
- [x] Verificar que el m??dulo se importa correctamente (con entorno .venv)

---

## ??? Pendientes

### Fase 1: Validaci??n de Servicios
- [ ] Verificar conexi??n PostgreSQL (solo lectura - SELECT)
- [ ] Verificar extensi??n `pgvector` instalada
- [ ] Verificar Ollama corriendo en localhost:11434
- [ ] Listar modelos necesarios:
  - deepseek-r1:8b
  - qwen2.5-coder
  - ministral-3:8b
  - qwen3:8b
  - qwen2.5:7b
  - mxbai-embed-large

### Fase 2: Smoke Tests
- [ ] Ejecutar `pytest tests/test_coder_smoke.py -v`
- [ ] Validar que ambos tests pasan

### Fase 3: Prueba Real
- [ ] Iniciar servidor: `uvicorn main:app --reload`
- [ ] Ejecutar POST a `/crew/stock-picker-rag`:
  ```json
  {
    "tickers": ["TSLA"],
    "debug": true
  }
  ```
- [ ] Monitorear logs del servidor
- [ ] Capturar respuesta completa

### Fase 4: Verificaci??n de Resultados
- [ ] Verificar PDF generado en `crew/reports/`
- [ ] Verificar gr??ficos generados en `crew/charts/`
- [ ] Confirmar que gr??ficos se borraron despu??s (cleanup)
- [ ] Abrir y validar contenido del PDF

### Fase 5: Validacion de PDF (estado parcial)
- [x] Sanitizacion y dedupe en `stock_picker.py` (texto y secciones) antes del PDF.
- [x] Migracion a reportlab en `pdf_report.py` con normalizacion a ASCII y escalado de imagenes.
- [ ] Capturar texto exacto que causa el error (si aparece en ejecucion real).
- [ ] Verificar dimensiones de imagenes reales generadas por el Coder.
- [ ] Ajustar reglas de limpieza si reportlab falla con texto largo o URLs sin espacios.

---

## ???? Restricciones Importantes

- ??? **NO modificar la base de datos** (solo consultas SELECT)
- ??? **NO instalar dependencias** sin verificar primero
- ??? **Usar entorno virtual existente**: `C:\IA_Local\scripts\Agentic_AI\.venv`
- ??? **Directorio de trabajo**: `C:\IA_Local\scripts\Agentic_AI\Session3_4`

---

## ???? Comandos ??tiles

### Activar entorno virtual (PowerShell):
```powershell
& C:\IA_Local\scripts\Agentic_AI\.venv\Scripts\Activate.ps1
```

### Verificar m??dulo:
```bash
python -c "from crew import stock_picker; print('OK')"
```

### Ejecutar smoke tests:
```bash
pytest tests/test_coder_smoke.py -v
```

### Iniciar servidor:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Verificar PostgreSQL (solo lectura):
```bash
$env:PGPASSWORD$env:PGPASSWORD='YOUR_DB_PASSWORD'
psql -U rag_user -d stocks_rag -h localhost -p 5432 -c "SELECT 'OK' AS status;"
```

### Verificar Ollama:
```bash
curl http://localhost:11434/api/tags
```

