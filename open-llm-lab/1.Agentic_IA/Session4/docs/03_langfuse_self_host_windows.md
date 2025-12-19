---

# Langfuse Self-Host en Windows (Docker Desktop) — Guía ridícula, “no me hagas pensar”

## 0) Requisitos (1 minuto)

* Docker Desktop instalado ✅

### 0.1) Paso que se te pasó (y que te rompió todo): **Docker debe estar corriendo**

1. Abre **Docker Desktop**
2. Espera a ver abajo “**Engine running**”
3. Verifica con:

```powershell
docker version
```

Si eso falla, NO sigas.

---

# 1) Descarga Langfuse (2 opciones)

## Opción A (recomendada): usar el repo oficial

```powershell
cd C:\IA_Local\scripts\Agentic_AI\Session4
git clone https://github.com/langfuse/langfuse.git
cd .\langfuse\
```

## Opción B: ya lo tienes clonado

Entra a la carpeta donde está tu `docker-compose.yml`:

```powershell
cd C:\IA_Local\scripts\Agentic_AI\Session4\langfuse
dir
```

Confirma que existe el archivo `docker-compose.yml` (o `compose.yml`).

---

# 2) Crea el archivo `.env` (EN LA RAÍZ) con secretos seguros

En la **misma carpeta** donde está el `docker-compose.yml`, crea `.env` con este bloque PowerShell:

```powershell
# En la carpeta raíz del docker-compose.yml
$NEXTAUTH_SECRET = [guid]::NewGuid().ToString("N")
$SALT           = [guid]::NewGuid().ToString("N")
$ENCRYPTION_KEY = -join ((48..57 + 97..102) | Get-Random -Count 64 | % {[char]$_})  # 64 hex chars

# Passwords (cámbialos si quieres, pero que no sean "postgres" y "myredissecret")
$POSTGRES_PASSWORD = [guid]::NewGuid().ToString("N")
$REDIS_AUTH        = [guid]::NewGuid().ToString("N")
$CLICKHOUSE_PASSWORD = [guid]::NewGuid().ToString("N")
$MINIO_ROOT_PASSWORD = [guid]::NewGuid().ToString("N")

@"
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=$NEXTAUTH_SECRET

SALT=$SALT
ENCRYPTION_KEY=$ENCRYPTION_KEY

POSTGRES_USER=postgres
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=postgres

REDIS_AUTH=$REDIS_AUTH

CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD

MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD
"@ | Set-Content -Encoding UTF8 .\.env

Write-Host "OK: .env creado en $(Get-Location)\.env"
```

✅ Esto reemplaza el paso manual de “inventar claves” a mano.

---

# 3) Arregla el problema típico: puertos ocupados (5432/6379)

Como tú ya tenías **Postgres local** usando 5432 (y a veces Redis 6379), lo correcto es **cambiar el puerto HOST**, no el interno del contenedor.

En `docker-compose.yml`:

### 3.1) Postgres

Busca:

```yaml
ports:
  - 127.0.0.1:5432:5432
```

Cámbialo por:

```yaml
ports:
  - 127.0.0.1:55432:5432
```

(Opción más segura: elimina el `ports:` completo si no necesitas acceder desde tu PC.)

### 3.2) Redis

Busca:

```yaml
ports:
  - 127.0.0.1:6379:6379
```

Cámbialo por:

```yaml
ports:
  - 127.0.0.1:56379:6379
```

📌 Importante: **Dentro de Docker** sigue siendo `postgres:5432` y `redis:6379`.
Estos cambios son solo para evitar choque en tu Windows.

---

# 4) Levanta Langfuse (la forma que NO falla)

En esa misma carpeta:

```powershell
docker compose up -d
docker compose ps
```

Si algo sale “Exited”, mira logs del web (lo principal):

```powershell
docker compose logs -n 200 langfuse-web
```

---

# 5) Abre la interfaz

En el navegador:

* **[http://localhost:3000](http://localhost:3000)**

Ahí:

1. Creas usuario
2. Organización
3. Proyecto

---

# 6) Ahora sí: API keys para que tus scripts envíen trazas

En Langfuse UI:

* **Project → Settings → API Keys → Create Key**

Te dará:

* `LANGFUSE_PUBLIC_KEY=pk-lf-...`
* `LANGFUSE_SECRET_KEY=sk-lf-...`

⚠️ Estas llaves **NO aparecen antes**. Aparecen **después** de que el servidor esté arriba y tú crees el proyecto.

---

# 7) Configura tu app/script (Session4) para enviar trazas

En el `.env` de TU APP (no el del compose), pon:

```env
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-PEGA_AQUI
LANGFUSE_SECRET_KEY=sk-lf-PEGA_AQUI
```

---

# 8) Mini test (para confirmar que estás mandando eventos)

1. Abre tu app y ejecuta una corrida.
2. En la UI de Langfuse, ve a **Traces** y deberías ver eventos nuevos.

---

# 9) Comandos útiles (operación diaria)

Parar:

```powershell
docker compose down
```

Ver estado:

```powershell
docker compose ps
```

Ver logs:

```powershell
docker compose logs -f langfuse-web
```

Reset total (borra datos):

```powershell
docker compose down -v
docker compose up -d
```

---

## Checklist final (lo mínimo para no fallar)

* [ ] Docker Desktop abierto y “Engine running”
* [ ] `.env` creado en la misma carpeta del compose
* [ ] Puertos host cambiados (si 5432/6379 están ocupados)
* [ ] `docker compose ps` muestra todo “Up”
* [ ] UI abre en `http://localhost:3000`
* [ ] Creaste Project y sacaste API Keys
* [ ] Tu app usa `LANGFUSE_HOST` + keys correctas

---
