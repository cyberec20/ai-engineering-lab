@echo off
setlocal
cd /d "%~dp0\.."
set "PY=..\.venv\Scripts\python.exe"
set "PYTHONPATH=%CD%"
echo Using python: "%PY%"
echo Running from: "%CD%"
"%PY%" -m pytest -q
echo.
echo Done. Press any key to close...
pause >nul
