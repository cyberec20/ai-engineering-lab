@echo off
REM === Ajusta esta ruta si tu carpeta base es distinta ===
set "BASE=C:\IA_Local\scripts\Agentic_AI\Session3"

echo Creando estructura de carpetas en:
echo   %BASE%
echo.

REM Carpetas base
mkdir "%BASE%" 2>nul
mkdir "%BASE%\crew" 2>nul
mkdir "%BASE%\crew\config" 2>nul

REM ============================
REM Archivos Python (stubs)
REM ============================

REM main.py (FastAPI para Sesion 3 + endpoints de CrewAI)
if not exist "%BASE%\main.py" (
    echo # main.py - FastAPI para Sesion 3 (CrewAI) > "%BASE%\main.py"
    echo # Aqui conectaremos endpoints que llamen a los crews de la carpeta 'crew'.>> "%BASE%\main.py"
)

REM llm_client_local.py (cliente LLM local - se sobreescribira con el de Session2)
if not exist "%BASE%\llm_client_local.py" (
    echo # llm_client_local.py - cliente LLM local para Ollama (copiar desde Session2)>> "%BASE%\llm_client_local.py"
)

REM __init__ de crew
if not exist "%BASE%\crew\__init__.py" (
    echo # Paquete 'crew' para la Sesion 3> "%BASE%\crew\__init__.py"
)

REM crew\stock_picker.py - flujo principal tipo "Stock Picker"
if not exist "%BASE%\crew\stock_picker.py" (
    echo # Script principal para el crew tipo "Stock Picker".> "%BASE%\crew\stock_picker.py"
    echo # Aqui definiremos el Crew, los agentes y el metodo de ejecucion.>> "%BASE%\crew\stock_picker.py"
)

REM crew\crew_runtime.py - capa para ejecutar crews desde FastAPI
if not exist "%BASE%\crew\crew_runtime.py" (
    echo # Funciones helpers para ejecutar crews (por ejemplo, run_stock_picker).> "%BASE%\crew\crew_runtime.py"
)

REM Config de CrewAI
if not exist "%BASE%\crew\config\__init__.py" (
    echo # Paquete de configuraciones (agents.yaml, tasks.yaml)> "%BASE%\crew\config\__init__.py"
)

if not exist "%BASE%\crew\config\agents.yaml" (
    echo # agents.yaml - definicion de agentes CrewAI para la Sesion 3> "%BASE%\crew\config\agents.yaml"
)

if not exist "%BASE%\crew\config\tasks.yaml" (
    echo # tasks.yaml - definicion de tareas/flows para la Sesion 3> "%BASE%\crew\config\tasks.yaml"
)

echo.
echo Estructura base de Session3 creada (o ya existia).
echo Archivos clave:
echo   %BASE%\main.py
echo   %BASE%\llm_client_local.py
echo   %BASE%\crew\stock_picker.py
echo   %BASE%\crew\crew_runtime.py
echo   %BASE%\crew\config\agents.yaml
echo   %BASE%\crew\config\tasks.yaml
echo.
pause
