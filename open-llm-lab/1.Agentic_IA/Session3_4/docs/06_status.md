# Estado de la sesion 3.4 (stock picker)

## Que hace el programa
- Flujo multiagente: Researcher (RAG persistente en pgvector), Coder (yfinance + ARIMA/Prophet/GARCH), Analyst multimodal (`ministral-3:8b`), Writer, Judge.
- Coder: descarga OHLCV (2 anos por defecto, modo largo 5 anos), split 70/30, forecast 60–90 dias, genera PNG en `charts/`.
- RAG: Researcher ingesta/consulta pgvector; Analyst/Judge leen RAG; Coder/Writer no.
- PDF: Judge compila informe y graficas en `reports/`, luego limpia `charts/`; respuesta /stocks-rag es breve + `pdf_path`; debug solo en la respuesta (no en el PDF).

## Fallas actuales observadas
- PDF: el generador actual es reportlab. El error previo de fpdf2 ya no aplica, pero queda pendiente validar en ejecucion real que reportlab no falle con texto largo, URLs sin espacios o imagenes con dimensiones anómalas.
- Writer: aun puede salir texto duplicado (riesgos/notas/acciones) si el Analyst repite bloques; guardrail agregado, falta validar en flujo real.

## Sugerencias para depurar
- Capturar el texto final que se pasa al PDF (ya limpiado) y las rutas de imagenes reales del run que falla.
- Verificar que las imagenes existan y tengan dimensiones razonables antes de insertarlas en reportlab.
- Revisar el output del Analyst/Writer para detectar duplicados antes de pasar al Judge/PDF.
