@echo off
setlocal
cd /d "%~dp0\.."
set RUN_LANGSMITH_SMOKE=1
set PYTHONPATH=%CD%
set REPO_ROOT=%CD%\..
set PY=%REPO_ROOT%\.venv\Scripts\python.exe
if not exist "%PY%" (
  echo ERROR: No se encontro Python del venv en: "%PY%"
  echo Verifica que .venv exista al mismo nivel que Session4.
  goto :done
)
echo Using python: "%PY%"
echo Running from: "%CD%"
"%PY%" -m pytest -q -rs tests\test_langsmith_integration.py
:done
echo.
echo Done. Press any key to close...
pause >nul
