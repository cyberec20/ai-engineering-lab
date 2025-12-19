@echo off
setlocal
cd /d "%~dp0\.."
set "PY=..\.venv\Scripts\python.exe"
set "PYTHONPATH=%CD%"
echo Using python: "%PY%"
echo Running from: "%CD%"
"%PY%" -m uvicorn app.main:app --reload --port 8100
echo.
echo Done. Press any key to close...
pause >nul

