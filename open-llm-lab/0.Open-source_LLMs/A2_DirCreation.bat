@echo off
REM Crea la estructura de carpetas para IA Local

REM Carpeta raíz
mkdir "C:\IA_Local"

REM Subcarpetas de modelos LLM
mkdir "C:\IA_Local\models_llm"
mkdir "C:\IA_Local\models_llm\qwen"
mkdir "C:\IA_Local\models_llm\deepseek"
mkdir "C:\IA_Local\models_llm\llama"
mkdir "C:\IA_Local\models_llm\otros"

REM Subcarpetas de modelos de imagen
mkdir "C:\IA_Local\models_img"
mkdir "C:\IA_Local\models_img\sdxl"
mkdir "C:\IA_Local\models_img\controlnet"
mkdir "C:\IA_Local\models_img\loras"

REM Subcarpetas de modelos de video
mkdir "C:\IA_Local\models_video"
mkdir "C:\IA_Local\models_video\wan"
mkdir "C:\IA_Local\models_video\wanGP"

REM Otras carpetas de trabajo
mkdir "C:\IA_Local\comfyui"
mkdir "C:\IA_Local\ollama"
mkdir "C:\IA_Local\scripts"
mkdir "C:\IA_Local\docs"

echo Estructura de C:\IA_Local creada (o ya existía).
pause
