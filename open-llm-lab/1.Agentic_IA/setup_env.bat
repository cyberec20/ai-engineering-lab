@echo off
REM Activa el entorno del proyecto Agentic_AI y te deja en la carpeta raíz

set "BASE=C:\IA_Local\scripts\Agentic_AI"

cd /d "%BASE%"

REM Activa el entorno virtual
call .venv\Scripts\activate.bat

echo.
echo Entorno activado en %BASE%.
echo Ahora puedes entrar a la sesión que quieras, por ejemplo:
echo   cd Session1
echo   cd Session2
echo   cd Session3
echo.
echo Para lanzar el server FastAPI (según la sesión):
echo   uvicorn main:app --reload --host 0.0.0.0 --port 8100
echo.

cmd /k
