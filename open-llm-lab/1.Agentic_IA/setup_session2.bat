@echo off
REM === Ajusta esta ruta si tu carpeta base es distinta ===
set "BASE=C:\IA_Local\scripts\Agentic_AI\Session2"

echo Creando estructura de carpetas en:
echo   %BASE%
echo.

REM Carpetas
mkdir "%BASE%" 2>nul
mkdir "%BASE%\agents" 2>nul

REM Archivos Python (si no existen)

REM main.py
if not exist "%BASE%\main.py" (
    echo # Entry point de la API / runtime para Session 2> "%BASE%\main.py"
    echo print("Session 2 - main.py creado")>> "%BASE%\main.py"
)

REM __init__.py
if not exist "%BASE%\agents\__init__.py" (
    echo # Paquete de agentes para Session 2> "%BASE%\agents\__init__.py"
)

REM agent.py
if not exist "%BASE%\agents\agent.py" (
    echo # Definición de clase Agent se implementara aqui> "%BASE%\agents\agent.py"
)

REM runner.py
if not exist "%BASE%\agents\runner.py" (
    echo # Definicion de AgentRunner y loop de agente> "%BASE%\agents\runner.py"
)

REM tools.py
if not exist "%BASE%\agents\tools.py" (
    echo # Tools de negocio para el agente (fetch_html, extract_value_proposition, etc.)> "%BASE%\agents\tools.py"
)

REM router.py
if not exist "%BASE%\agents\router.py" (
    echo # Router de herramientas: interpreta JSON {"tool": ..., "args": {...}}> "%BASE%\agents\router.py"
)

echo.
echo Estructura creada (o ya existia). Revisa:
echo   %BASE%
pause
