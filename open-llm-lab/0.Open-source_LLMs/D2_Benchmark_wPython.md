---

## 1️⃣ Crear un environment dedicado

1. Abre **PowerShell**.
2. Crea una carpeta para entornos (si no existe):

```powershell
mkdir C:\IA_Local\envs
```

3. Entra allí:

```powershell
cd C:\IA_Local\envs
```

4. Crea el entorno:

```powershell
python -m venv llm-bench
```

Esto crea `C:\IA_Local\envs\llm-bench\` con su propio Python y pip.

---

## 2️⃣ Activar el environment

En **PowerShell**:

```powershell
C:\IA_Local\envs\llm-bench\Scripts\Activate.ps1
```

* Si ves un error de ejecución de scripts (`ExecutionPolicy`), ejecuta **una sola vez**:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

y luego vuelve a correr:

```powershell
C:\IA_Local\envs\llm-bench\Scripts\Activate.ps1
```

Sabrás que está activo porque el prompt se verá así:

```text
(llm-bench) PS C:\IA_Local\envs>
```

> En CMD sería:
> `C:\IA_Local\envs\llm-bench\Scripts\activate.bat`

---

## 3️⃣ Instalar las dependencias dentro del env

Con el entorno **activo**:

```powershell
pip install requests
```

(En este entorno sólo vamos a usar cosas ligeras: `requests`, y si luego quieres, `pandas`, etc.)

---

## 4️⃣ Ejecutar el benchmark usando ese environment

1. Con el env **llm-bench** aún activo, ve a tu carpeta de scripts:

```powershell
cd C:\IA_Local\scripts
```

2. Lanza el benchmark:

```powershell
python 1_run_benchmark_lmstudio.py
```

* Usará el Python del entorno `llm-bench`.
* Creará el JSON `benchmark_results_qwen_deepseek_scored.json` en `C:\IA_Local\scripts`.

---

## 5️⃣ Cuando termines

Para salir del environment:

```powershell
deactivate
```

Y listo, tu entorno del SaaS y el entorno de **LLM locales** quedan totalmente separados.

Si quieres, después de que esto corra bien, te ayudo a añadir un `requirements.txt` minimal para este env (por ejemplo para que el futuro tú lo pueda recrear con un solo comando).
