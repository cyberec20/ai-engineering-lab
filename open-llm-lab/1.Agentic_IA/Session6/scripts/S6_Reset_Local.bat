@echo off
setlocal
cd /d "%~dp0.."
del /q logs\runtime.jsonl 2>nul
for /f "delims=" %%F in ('dir /b logs\smoke\*.jsonl 2^>nul') do del "logs\smoke\%%F"
rd /s /q __pycache__ 2>nul
for /f "delims=" %%D in ('dir /s /b __pycache__ 2^>nul') do rd /s /q "%%D" 2>nul
echo Limpieza completada.
endlocal
