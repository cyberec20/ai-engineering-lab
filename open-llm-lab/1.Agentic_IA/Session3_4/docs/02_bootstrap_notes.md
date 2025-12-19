# Prompt de inicio (para ti mismo) - Sesion 3.4

1) Rutas y entorno
- Trabajo en: `C:\IA_Local\scripts\Agentic_AI\Session3_4`.
- Entorno virtual: `C:\IA_Local\scripts\Agentic_AI\.venv`.
- Endpoints FastAPI en `main.py` (versión 3.4).

2) Lee primero (contexto clave)
- `changelog.md`: resumen 3.3/3.4 y problemas conocidos.
- `system_prompt_3.4.md`: flujo multiagente y roles.
- `crew/stock_picker.py`: orquestación (RAG, Coder, Analyst, Writer, Judge) y prompts actuales.
- `crew/coder.py`: pipeline cuant (yfinance, ARIMA/Prophet/GARCH).
- `crew/pdf_report.py`: generador PDF con reportlab.
- `STATUS.md`: estado y fallas conocidas.

3) Qué hace el proyecto
- Flujo multiagente para análisis de acciones: Researcher (RAG persistente pgvector), Coder (yfinance + modelos), Analyst multimodal, Writer, Judge.
- Genera PDF por ticker en `Session3_4/crew/reports/`; imágenes temporales en `Session3_4/crew/charts/` (deduplicadas, se limpian).
- RAG: Researcher ingesta y lee; Analyst/Judge leen; Coder/Writer no.

4) Configuración/Servicios esperados
- `.env` con `PG_CONN` apuntando a `stocks_rag` (pgvector).
- Modelos locales: deepseek-r1:8b, qwen2.5-coder, ministral-3:8b, qwen3:8b, qwen2.5:7b, mxbai-embed-large.
- Dependencias clave: pandas/numpy, yfinance, pmdarima/statsmodels/arch/prophet, matplotlib/seaborn, reportlab, psycopg2-binary.

5) Problemas pendientes conocidos
- Writer/Judge deben seguir evitando tablas Markdown y duplicados; revisa prompts si reaparece texto repetido.
- PDF: ahora usa reportlab con Markdown básico; si falla, validar texto e imágenes reales.

6) Para probar rápido
- Activar venv: `& ..\.venv\Scripts\Activate.ps1`.
- Smoke test: `python -m pytest Session3_4/tests/test_coder_smoke.py`.
- Flujo real: levantar uvicorn y POST a `/crew/stock-picker-rag` con `debug=true`; revisar PDF en `crew/reports/` y cleanup de `charts/`.

7) No hagas
- No tocar DB (solo lectura) salvo instrucción expresa.
- No reinstalar deps fuera del venv.
