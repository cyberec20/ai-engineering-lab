@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Session 4 Scaffold (Research Operator - no RAG, Web tools, UI)
REM  Creates a robust folder structure and empty starter files.
REM  Target root folder: .\Session4  (relative to where you run this)
REM ============================================================

REM ---- Resolve target path (Session4 under current directory)
set "ROOT=%CD%\Session4"

echo.
echo [Session4] Creating project scaffold at:
echo   %ROOT%
echo.

REM ---- Create base folders
for %%D in (
  "app"
  "app\api"
  "app\core"
  "app\orchestrator"
  "app\orchestrator\graphs"
  "app\orchestrator\observability"
  "app\orchestrator\tools"
  "app\orchestrator\schemas"
  "app\orchestrator\utils"
  "app\ui"
  "app\ui\static"
  "app\ui\static\assets"
  "reports"
  "scripts"
  "tests"
  "docs"
) do (
  if not exist "%ROOT%\%%~D" (
    mkdir "%ROOT%\%%~D" >nul 2>&1
    echo  [+] %ROOT%\%%~D
  ) else (
    echo  [=] %ROOT%\%%~D
  )
)

REM ---- Helper: create file if missing
REM Usage: call :touch "relative\path\file.ext" "optional first line"
goto :after_touch

:touch
set "FILE=%~1"
set "LINE=%~2"
if not exist "%ROOT%\%FILE%" (
  if "%LINE%"=="" (
    type nul > "%ROOT%\%FILE%"
  ) else (
    > "%ROOT%\%FILE%" echo %LINE%
  )
  echo  [+] %ROOT%\%FILE%
) else (
  echo  [=] %ROOT%\%FILE%
)
exit /b 0

:after_touch

REM ---- Create starter files (empty / minimal headers)
call :touch ".env.example" "### Copy to .env and fill values as needed"
call :touch "requirements.txt" "### Add/merge your Python deps here"
call :touch "README.md" "# Session4 - Research Operator (No RAG, Web, UI, Observability)"
call :touch "docs\NOTES.md" "# Notes (Session 4)"
call :touch "scripts\run_dev.bat" "@echo off"
call :touch "scripts\run_tests.bat" "@echo off"

REM ---- Python package init files
call :touch "app\__init__.py"
call :touch "app\api\__init__.py"
call :touch "app\core\__init__.py"
call :touch "app\orchestrator\__init__.py"
call :touch "app\orchestrator\graphs\__init__.py"
call :touch "app\orchestrator\observability\__init__.py"
call :touch "app\orchestrator\tools\__init__.py"
call :touch "app\orchestrator\schemas\__init__.py"
call :touch "app\orchestrator\utils\__init__.py"

REM ---- Backend entry + API
call :touch "app\main.py" "# Entry point (FastAPI) - implement in Session 4"
call :touch "app\api\routes_chat.py" "# /chat and /approve endpoints live here"

REM ---- Orchestrator core (LangGraph)
call :touch "app\orchestrator\graphs\state.py" "# Define typed graph state here"
call :touch "app\orchestrator\graphs\nodes.py" "# Implement planner/research/synthesize/reflect/HITL nodes"
call :touch "app\orchestrator\graphs\graph_app.py" "# Build and compile the LangGraph here"

REM ---- Tools (Web)
call :touch "app\orchestrator\tools\web_search.py" "# Web search tool wrapper (implement)"
call :touch "app\orchestrator\tools\web_fetch.py" "# URL fetch + parse tool wrapper (implement)"

REM ---- Observability adapters
call :touch "app\orchestrator\observability\trace_adapter.py" "# Common tracing interface (LangSmith/Langfuse switch)"
call :touch "app\orchestrator\observability\langsmith_adapter.py" "# LangSmith tracing adapter"
call :touch "app\orchestrator\observability\langfuse_adapter.py" "# Langfuse tracing adapter"

REM ---- Schemas / utils
call :touch "app\orchestrator\schemas\contracts.py" "# Pydantic models / TypedDict contracts"
call :touch "app\orchestrator\utils\config.py" "# Read env vars and config safely"
call :touch "app\orchestrator\utils\logging.py" "# Structured logging helpers"

REM ---- UI (simple static chat)
call :touch "app\ui\static\index.html" "<!-- Session4 Chat UI (static) -->"
call :touch "app\ui\static\app.js" "// Session4 Chat UI script"
call :touch "app\ui\static\styles.css" "/* Session4 Chat UI styles */"

REM ---- Reports + tests
call :touch "reports\.gitkeep"
call :touch "tests\test_graph_smoke.py" "# Smoke test for graph execution"

REM ---- Populate scripts with minimal useful content (only if they were newly created)
REM Note: We avoid overwriting if they already exist.
if exist "%ROOT%\scripts\run_dev.bat" (
  for /f %%A in ('powershell -NoProfile -Command "(Get-Item ''%ROOT%\scripts\run_dev.bat'').Length"') do set "LEN=%%A"
  if "!LEN!"=="0" (
    > "%ROOT%\scripts\run_dev.bat" (
      echo @echo off
      echo setlocal
      echo cd /d "%%~dp0.."
      echo echo [run_dev] Starting Session4 backend...
      echo REM Activate venv if you use one, e.g.:
      echo REM call .venv\Scripts\activate
      echo python -m app.main
      echo endlocal
    )
  )
)

if exist "%ROOT%\scripts\run_tests.bat" (
  for /f %%A in ('powershell -NoProfile -Command "(Get-Item ''%ROOT%\scripts\run_tests.bat'').Length"') do set "LEN=%%A"
  if "!LEN!"=="0" (
    > "%ROOT%\scripts\run_tests.bat" (
      echo @echo off
      echo setlocal
      echo cd /d "%%~dp0.."
      echo echo [run_tests] Running tests...
      echo REM Activate venv if you use one, e.g.:
      echo REM call .venv\Scripts\activate
      echo python -m pytest -q
      echo endlocal
    )
  )
)

REM ---- Final message
echo.
echo [OK] Session4 scaffold created.
echo Next steps:
echo  1) Copy .env.example to .env and fill required keys.
echo  2) Add deps into requirements.txt (or keep using your existing one).
echo  3) Implement app\main.py, graph files, tools, and UI.
echo.
pause
endlocal
exit /b 0
