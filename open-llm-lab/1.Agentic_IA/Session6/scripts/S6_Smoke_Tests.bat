@echo off
setlocal
cd /d "%~dp0.."
if not exist ..\.venv\Scripts\activate.bat (
  echo [.venv no encontrado]
  exit /b 1
)
call ..\.venv\Scripts\activate.bat >nul 2>&1
python -m pytest -q || exit /b 1
echo Smoke tests OK.
endlocal
