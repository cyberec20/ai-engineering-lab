@echo off
setlocal
cd /d "%~dp0\.."
set "PY=..\.venv\Scripts\python.exe"
set "PORT=8200"
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b "PORT=" ".env" 2^>nul`) do set "PORT=%%B"
if not "%~1"=="" set "PORT=%~1"
set "PYTHONPATH=%CD%"
echo Using python: "%PY%"
echo Running from: "%CD%"
echo PYTHONPATH: "%PYTHONPATH%"
echo Port: %PORT%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } catch { }"
"%PY%" -c "import sys,app; import app.main; print('app.__file__ =', app.__file__); print('app.main.__file__ =', app.main.__file__); print('sys.path[:5] =', sys.path[:5])"
"%PY%" -m uvicorn app.main:app --reload --port %PORT% --app-dir "%CD%"
echo.
echo Done. Press any key to close...
pause >nul
