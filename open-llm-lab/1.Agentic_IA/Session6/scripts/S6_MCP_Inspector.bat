@echo off
setlocal
cd /d "%~dp0.."
set "HOST="
set "PORT="
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /r "^[Hh][Oo][Ss][Tt]= ^[Pp][Oo][Rr][Tt]=" .env 2^>nul`) do (
  if /I "%%A"=="HOST" set "HOST=%%B"
  if /I "%%A"=="PORT" set "PORT=%%B"
)
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=8100"
set "CFG=%CD%\scripts\mcp-inspector.json"
(
  echo {
  echo   "mcpServers": {
  echo     "local-mt5": {
  echo       "type": "streamable-http",
  echo       "url": "http://%HOST%:%PORT%/mcp/",
  echo       "note": "Session6 MCP server (local)"
  echo     }
  echo   }
  echo }
) > "%CFG%"
echo Lanzando MCP Inspector con config "%CFG%" (server local-mt5) ...
call npx -y @modelcontextprotocol/inspector --config "%CFG%" --server local-mt5
if errorlevel 1 (
  echo MCP Inspector retorno un error.
) else (
  echo MCP Inspector finalizo correctamente.
)
:end
echo.
echo Inspector finalizado. Presiona cualquier tecla para cerrar...
pause >nul
endlocal
