@echo off
setlocal
cd /d "%~dp0.."
set "PY=..\.venv\Scripts\python.exe"
if not exist %PY% (
  echo [.venv no encontrado]
  exit /b 1
)
set "HOST="
set "PORT="
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /r "^[Hh][Oo][Ss][Tt]= ^[Pp][Oo][Rr][Tt]=" .env 2^>nul`) do (
  if /I "%%A"=="HOST" set "HOST=%%B"
  if /I "%%A"=="PORT" set "PORT=%%B"
)
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=8100"
set "PYTHONPATH=%CD%"
echo Using python: "%PY%"
echo Running from: "%CD%"
echo PYTHONPATH: "%PYTHONPATH%"
echo Host: %HOST%
echo Port: %PORT%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } catch { }"
"%PY%" -c "import sys; import server.app as app_module; print('server.app:', app_module.__file__); print('sys.path[:5]=', sys.path[:5])"
call ..\.venv\Scripts\activate.bat >nul 2>&1
where uv >nul 2>&1
if %errorlevel%==0 (
  echo Iniciando via ^"uv run^" en http://%HOST%:%PORT% ...
  uv run python -m uvicorn server.app:app --host %HOST% --port %PORT%
) else (
  echo Iniciando via python en http://%HOST%:%PORT% ...
  python -m uvicorn server.app:app --host %HOST% --port %PORT%
)
echo.
echo Done. Press any key to close...
pause >nul
endlocal
