---

## Mensaje para Codex (VS Code)

Necesito que corrijas un problema conceptual y técnico: **mi servidor NO está exponiendo un MCP Server real**, aunque tiene rutas que se llaman `/mcp/*`. Eso provocó confusión y por eso **MCP Inspector no puede conectarse** (da 404 Not Found al intentar POSTear al endpoint MCP).

### Hallazgos (lo que está pasando hoy)

1. **Lo actual NO es MCP**: tenemos endpoints HTTP normales (FastAPI) con paths tipo:

   * `/mcp/md_get_latest`
   * `/mcp/md_get_ohlc`
   * `/mcp/desk_evaluate`
     pero esos endpoints son **API REST propias**, no implementan el **protocolo MCP** (no hay handshake MCP, no hay listado de tools MCP, no hay transporte MCP streamable-http/SSE real).

2. **MCP Inspector espera un MCP Server real**:

   * Cuando el Inspector conecta, intenta establecer comunicación MCP (handshake + listar tools/resources).
   * En mi caso, al apuntar a `http://127.0.0.1:8100/mcp`, el proxy devuelve:
     `StreamableHTTPError ... 404 Not Found`
   * Eso indica que **no existe endpoint MCP real** o no está montado con el transporte MCP correcto.

3. **Conclusión**: el sistema actual funciona como “Trading Desk + API”, pero **no como MCP Server inspeccionable**. Por eso yo “no veía nada” en MCP Inspector.

---

## Objetivo (intención B)

Quiero que el proyecto tenga **un MCP Server real** (compatible con MCP Inspector) que envuelva lo que ya existe:

* mantener la lógica actual (`MT5Bridge`, cache, `/mt5/push`, `desk_evaluate`, etc.)
* agregar una capa MCP auténtica que exponga herramientas MCP.
* **renombrar** rutas y conceptos para que lo que NO es MCP deje de llamarse MCP.

---

## Requerimiento clave: “No reescribir todo”

No quiero romper el desk que ya funciona. Quiero un wrapper MCP encima.

---

## Tareas concretas para ti (Codex)

### A) Renombrar lo que NO es MCP

1. Renombrar el prefijo `/mcp/*` actual a algo que no confunda, por ejemplo:

   * `/api/md_get_latest`
   * `/api/md_get_ohlc`
   * `/api/desk_evaluate`
     o agruparlo como:
   * `/api/market/latest`
   * `/api/market/ohlc`
   * `/api/desk/evaluate` (este ya existe)
2. Actualizar la UI (si usa esos endpoints) para apuntar a los nuevos paths.
3. Mantener compatibilidad si quieres con redirects temporales, pero el nombre “mcp” debe desaparecer de rutas que no implementan protocolo MCP.

### B) Crear un MCP Server REAL (nuevo endpoint dedicado)

1. Implementar un servidor MCP auténtico usando el SDK MCP (Python) o la implementación estándar recomendada.
2. Debe exponer un endpoint real, por ejemplo:

   * `http://127.0.0.1:8100/mcp` (este sí debe ser MCP real)
3. Debe usar el transporte compatible con Inspector:

   * Streamable HTTP (o SSE, según soporte del SDK actual)
4. Debe permitir que MCP Inspector:

   * conecte sin 404
   * liste tools
   * ejecute tools y vea resultados

### C) Tools MCP mínimos (envolver lo existente)

Exponer estas tools MCP (nombres claros y consistentes):

1. `market.get_latest`

   * input: `{ "symbol": "...", "timeframe": "M1" }`
   * output: snapshot con bid/ask/ts y opcional OHLC reciente
   * debe leer del cache actualizado por `/mt5/push` (o stub si no hay MT5)

2. `market.get_ohlc`

   * input: `{ "symbol": "...", "timeframe": "M1", "bars": 1 | N }`
   * output: OHLC (y si hay bars>1, array)

3. `desk.evaluate`

   * input: `{ "symbol": "...", "timeframe": "...", "notes": "..." }`
   * output: exactamente el JSON final (decision, reasons, market_snapshot, meta, node_outputs)
   * internamente reusa la misma función que usa `/api/desk/evaluate` (no duplicar lógica)

### D) Modo stub (para no depender de MT5)

El MCP Server debe funcionar aun si MT5 no está empujando datos:

* si no hay datos en cache para (symbol,timeframe), retornar un stub determinista (o un error claro “NO_DATA”)
* esto permite correr Inspector + smoke tests sin MT5 abierto.

### E) Smoke tests nuevos (aceptación real)

Agregar tests/chequeos mínimos:

1. “MCP handshake ok” (Inspector o client MCP puede listar tools)
2. “tools list contiene market.get_latest, market.get_ohlc, desk.evaluate”
3. “desk.evaluate responde JSON válido”
4. modo stub funciona sin MT5

### F) Documentación operativa (para mí)

Agregar en README/Session6:

* “API vs MCP”: explicar en 5 líneas que antes había rutas `/mcp/*` que eran REST y se renombraron
* cómo arrancar:

  * server (uv run)
  * EA MT5 push
  * MCP Inspector (y dónde poner el token del proxy)
* cuál URL usar en Inspector:

  * `http://127.0.0.1:8100/mcp` (MCP real)

---

## Nota importante sobre el error actual

En mis logs de Inspector aparece:
`Error POSTing to endpoint ... {"detail":"Not Found"}`

Eso pasa porque:

* o no existe `/mcp`
* o existe pero no implementa el protocolo
* o se montó en otra ruta (ej. `/mcp/` vs `/mcp`) o con otra app/subapp

Tu corrección debe asegurar que **/mcp** exista y sea un MCP server verdadero, no un path REST.

---

## Entregables esperados

1. Rutas REST renombradas (sin prefijo `/mcp`)
2. Endpoint MCP real operativo en `/mcp`
3. Tools MCP visibles en Inspector
4. Smoke test que valide tools list + una ejecución
5. README actualizado con “cómo usar MCP Inspector” y diferencia API vs MCP

---
