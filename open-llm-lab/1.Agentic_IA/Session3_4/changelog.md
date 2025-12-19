# Changelog - Version 3.4

## Resumen / Avances (3.4)
- Coder cuant: yfinance (ventana 2 anos por defecto, modo largo 5 anos), split 70/30, forecast 60ƒ?"90 dias; modelos ARIMA/Prophet/GARCH con fallbacks; graficos PNG en `charts/` (deduplicados por ticker).
- RAG persistente (pgvector): Researcher ingesta/lee; Analyst/Judge reciben docs; Coder/Writer no leen RAG.
- Analyst multimodal actualizado a `ministral-3:8b` y recibe rutas de imagenes.
- PDF: migrado a reportlab; parseo de Markdown basico (headings, **negritas**, bullets, separadores), normalizacion a ASCII, validacion de imagenes; respuesta /stocks-rag es breve + `pdf_path`; debug solo en la respuesta (PDF limpio).
- Prompts Analyst/Writer/Judge reforzados: Analyst describe cada grafica/modelo con metricas; Writer evita tablas Markdown, deduplica secciones y usa las descripciones del Analyst; Judge corrige duplicados/formato y agrega contexto breve si faltan descripciones de graficas/modelos.
- Deduplicacion de secciones y headings antes del PDF para evitar bloques repetidos en el informe final.

## Problemas conocidos (3.4)
- PDF: el generador actual es reportlab; el error previo de fpdf2 ya no aplica. Pendiente validar en ejecucion real que reportlab no falle con texto largo, URLs sin espacios o imagenes con dimensiones anómalas.
- Writer: puede duplicar bloques (riesgos/notas/acciones) si el Analyst repite; guardrail anadido, pendiente verificar en flujo real.

# Changelog - Version 3.3

## Resumen
Esta version anade RAG persistente con Postgres + pgvector, mejora la visibilidad de debug y ajusta las fuentes de datos para trabajar con los planes free vigentes.

## Cambios principales
- Persistencia: los documentos RAG (news, descripciones) se ingestan en pgvector y se recuperan en llamadas siguientes. En `debug` se muestran los documentos persistentes y las advertencias.
- Carga de `.env`: se carga automaticamente al iniciar para tomar `PG_CONN` y otras variables.
- Alpha Vantage: se usa el endpoint gratuito `TIME_SERIES_DAILY` en lugar de `TIME_SERIES_DAILY_ADJUSTED` (premium), eliminando el warning de "Information/premium".
- Fallback FMP: si FMP falla (403 en plan free/legacy), se usa Finnhub `/stock/profile2` para sector/industria/market cap; se anota en el snapshot.
- Trace enriquecido: en modo `debug`, el trace incluye warnings de APIs y persistencia.

## Notas sobre FMP
- El endpoint `/api/v3/profile` y `key-metrics` muestran 403 en cuentas free nuevas (legacy). Para perfil/ratios completos, se requiere plan de pago o proveedor alternativo; mientras tanto, el fallback de Finnhub cubre perfil basico.

## Limitaciones de las APIs free
- FMP: sin `v3/profile` ni `key-metrics` en free/legacy.
- Alpha Vantage: `TIME_SERIES_DAILY_ADJUSTED` y `outputsize=full` son premium; en free usar `TIME_SERIES_DAILY` con `outputsize=compact`.
- Finnhub: sin `/stock/candle` en free; solo `quote`, `company-news`, `profile2`.

## Plan para velas (Sesion 3.4)
- Usar **yfinance** para OHLC diarios (e intradia limitado); fuente no oficial sujeta a cambios/throttling.

## Decisiones recientes de diseno
- RAG accesible a todos los agentes salvo Coder/Writer; se comparten contextos persistentes y del Researcher.
- Modelos cuant: ARIMA/SARIMA, GARCH, Prophet como complemento.
- Entregable 3.4: PDF por ticker con graficos, tablas/metricas, analisis multimodal, escenarios y riesgos; Writer edita; Judge valida y limpia imagenes.

## Requisitos/Entorno
- Postgres con extension `vector` y tabla `documents` (VECTOR(1024), mxbai-embed-large).
- Usuario `rag_user` con permisos sobre `stocks_rag`.
- Variables en `.env`: `PG_CONN`, `FMP_API_KEY`, `ALPHAVANTAGE_API_KEY`, `FINNHUB_API_KEY`.
