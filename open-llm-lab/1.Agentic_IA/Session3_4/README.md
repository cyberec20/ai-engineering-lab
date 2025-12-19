# Session 3.4 ? Crew financiero con RAG persistente + cuant + PDF

## Objetivo
Evolucionar el crew de analisis de acciones con:
- RAG persistente en Postgres + pgvector
- Capa cuantitativa (yfinance + ARIMA/Prophet/GARCH)
- Analisis multimodal con graficos
- Generacion de PDF por ticker

## Que hay en esta sesion
- `main.py`: API FastAPI con comandos `/stocks` y `/stocks-rag` y endpoints directos.
- `crew/stock_picker.py`: orquestacion multiagente (Researcher, Coder, Analyst, Writer, Judge).
- `crew/`: codigo de RAG, cuant, reportes y prompts.
- `docs/01_system_prompt.md`: especificacion completa del flujo y roles.
- `changelog.md`: cambios 3.3 y 3.4 + problemas conocidos.
- `docs/03_db_setup_pgvector.md`: guia de Postgres + pgvector y configuracion de `PG_CONN`.
- `docs/06_status.md`: estado actual y fallas observadas.
- `docs/05_pending_tasks.md`: checklist de validacion.
- `tests/`: smoke tests del Coder.
- `Session3_4_Roadmap_RAG_Crew.html`: guia de la evolucion 3.1/3.2.

## Arquitectura (resumen)
Flujo multiagente:
1) Researcher: APIs financieras + RAG persistente (pgvector)
2) Coder: OHLCV con yfinance + modelos cuant (ARIMA/Prophet/GARCH) + graficos
3) Analyst (multimodal): analiza texto y graficos
4) Writer: estructura el informe
5) Judge: valida, genera PDF y limpia imagenes temporales

## Endpoints
- `GET /` health + lista de endpoints
- `POST /sdr/email`, `POST /sdr/chat`, `GET /sdr/chat-ui` (heredado de Session 2)
- `POST /crew/stock-picker` (analisis numerico)
- `POST /crew/stock-picker-rag` (numerico + RAG persistente + PDF)

## Comandos de chat
- ` /stocks AAPL, NVDA, TSLA [debug]`
- ` /stocks-rag AAPL, NVDA, TSLA [debug]`

## Requisitos
- Python 3.11+
- Ollama con modelos locales necesarios
- Postgres con extension `pgvector`
- Paquetes: `fastapi`, `uvicorn`, `requests`, `httpx`, `pydantic`, `yfinance`, `python-dotenv`, `psycopg2-binary`, `reportlab`, `pmdarima`, `statsmodels`, `arch`, `prophet`, `matplotlib`

## Configuracion
- Archivo `.env.example` con `PG_CONN` (conexion a `stocks_rag` con `rag_user`).
- Base Postgres y tabla `documents` segun `docs/03_db_setup_pgvector.md`.

## Como ejecutar
1) Inicia Ollama y verifica modelos:
```
ollama list
```

2) Activa el venv e instala dependencias (si aplica):
```
# ejemplo
pip install -r requirements.txt
```

3) Levanta el servidor:
```
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

4) Prueba por chat:
```
/stocks AAPL, NVDA, TSLA
/stocks-rag AAPL, NVDA, TSLA debug
```

## Troubleshooting
- PDF: si aparece \"Not enough horizontal space\", captura el texto final y rutas de imagenes; revisa URLs largas y caracteres no ASCII antes del PDF.
- Imagenes: valida que existan y tengan dimensiones razonables antes de insertarlas en el PDF.
- Duplicados: si Writer repite secciones, revisa el output del Analyst y los guardrails de deduplicacion.
- RAG: si no hay contexto, confirma PG_CONN y que documents tenga contenido.
- Modelos: si falla un rol, verifica con ollama list que los modelos requeridos esten instalados.
## Docs
- docs/01_system_prompt.md
- docs/02_bootstrap_notes.md
- docs/03_db_setup_pgvector.md
- docs/04_code_review.md
- docs/05_pending_tasks.md
- docs/06_status.md
## Notas
- El PDF final se guarda en `crew/reports/` y las imagenes temporales en `crew/charts/`.
- `docs/06_status.md` y `changelog.md` documentan fallas conocidas y decisiones recientes.
- Este flujo es educativo; no da recomendaciones de inversion.


