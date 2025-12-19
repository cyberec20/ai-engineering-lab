---

# Configuración externa de la base de datos (Postgres + pgvector) – Versión revisada

Objetivo: dejar una base Postgres en Windows lista para RAG con:

* BD: `stocks_rag`
* Extensión: `vector` (pgvector)
* Tabla: `documents`
* Usuario de aplicación: `rag_user`
* Conexión lista para usarse desde el entorno Python en
  `C:\IA_Local\scripts\Agentic_AI\.venv`

---

## 0. Decisiones previas

1. **Modelo de embeddings (para la dimensión del vector)**

   * Usaremos **`mxbai-embed-large` → dimensión = `1024`**.
   * Si en el futuro cambias a `nomic-embed-text`, tendrás que:

     * Usar `VECTOR(768)` en la tabla.
     * Ajustar scripts de carga.

2. **Nombre de la base de datos**

   * Usaremos: `stocks_rag`.

3. **Usuario de aplicación**

   * Usuario superadmin de Postgres: `postgres` (solo para administración).
   * Usuario de app: `rag_user` (con permisos limitados sobre `stocks_rag`).

---

## 1. Verificar instalación de Postgres y `psql` (PATH)

### 1.1. Comprobar `psql` en la consola

Abre **PowerShell** o **CMD** y ejecuta:

```powershell
psql --version
```

* Si ves algo como `psql (PostgreSQL) 16.x` → ✅ `psql` está en el PATH.
* Si obtienes error “psql no se reconoce…”:

  * O bien `psql` no está instalado,
  * o no está en el PATH.

### 1.2. Si `psql` NO se reconoce

* Asegúrate de haber instalado **PostgreSQL para Windows** desde la web oficial.
* Durante la instalación:

  * Incluye **“Command Line Tools”** (psql).
* Si ya lo instalaste pero no aparece, puedes:

  * Reinstalar o modificar la instalación añadiendo los CLI tools.
  * O agregar manualmente al PATH algo como:
    `C:\Program Files\PostgreSQL\16\bin`

*(En tu caso, ya lo tienes funcionando, pero este paso queda documentado.)*

---

## 2. Instalar herramientas oficiales para compilar pgvector (solo una vez)

En Windows, **pgvector no viene de serie ni en StackBuilder**, así que hay que compilarlo **desde su repo oficial**.

### 2.1. Instalar “Build Tools for Visual Studio 2022”

1. Ve a la página oficial de Visual Studio (descargas).

2. En la sección **Tools for Visual Studio** descarga:
   **“Build Tools for Visual Studio 2022”**.

3. Ejecuta `vs_BuildTools.exe`.

4. En la pestaña **Workloads**, marca:

   * ✅ **Desktop development with C++**

5. Pulsa **Install** y espera a que termine.

Esto te instala:

* Compilador C/C++
* `nmake`
* Librerías necesarias para compilar extensiones de Postgres.

### 2.2. Instalar Git para Windows

1. Ve a **git-scm.com**.
2. Descarga **Git for Windows**.
3. Instala aceptando las opciones por defecto.

---

## 3. Compilar e instalar pgvector desde GitHub (oficial)

### 3.1. Abrir la consola correcta

1. Abre el menú Inicio.
2. Busca:
   **“x64 Native Tools Command Prompt for VS 2022”**.
3. Clic derecho → **Ejecutar como administrador**.

Todo lo que sigue va en **esa consola**.

### 3.2. Apuntar a tu instalación de Postgres

Asumiendo ruta estándar:

```bat
set "PGROOT=C:\Program Files\PostgreSQL\16"
```

* Si tu Postgres está en otra ruta, ajusta `PGROOT`.

### 3.3. Clonar y compilar pgvector (repo oficial)

En la **misma consola**:

```bat
cd %TEMP%
git clone --branch v0.8.1 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

Qué hace cada comando:

* `git clone ...` → descarga el código oficial desde GitHub.
* `nmake /F Makefile.win` → compila la extensión para Windows.
* `nmake /F Makefile.win install` → copia:

  * `vector.dll` a `C:\Program Files\PostgreSQL\16\lib`
  * `vector.control` y los `.sql` a `C:\Program Files\PostgreSQL\16\share\extension`

Si termina sin errores, pgvector queda instalado en tu Postgres 16.

### 3.4. (Opcional) Reiniciar el servicio Postgres

Puedes hacerlo desde **Servicios** de Windows o con:

```bat
net stop postgresql-x64-16
net start postgresql-x64-16
```

*(En tu caso funcionó sin reinicio explícito, pero dejamos el paso anotado.)*

---

## 4. Crear la base de datos `stocks_rag`

En **PowerShell o CMD**:

```powershell
psql -U postgres
```

Escribe la contraseña de `postgres` (la que definiste al instalar Postgres).

Dentro de `psql`:

```sql
CREATE DATABASE stocks_rag;
\l      -- (opcional) lista las bases para confirmar que existe
\q      -- salir
```

---

## 5. Habilitar la extensión `vector` (pgvector) en `stocks_rag`

Conéctate a la base:

```powershell
psql -U postgres -d stocks_rag
```

Dentro de `psql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
\dx
```

Debes ver algo como:

```text
  Nombre  | Versión |  Esquema | Descripción
----------+---------+----------+------------------------------------------------------
  plpgsql | 1.0     | pg_catalog | PL/pgSQL procedural language
  vector  | 0.8.1   | public | vector data type and ivfflat and hnsw access methods
```

Eso confirma que **pgvector está operativo en `stocks_rag`**.

---

## 6. Crear tabla `documents` y usuario `rag_user` con permisos

### 6.1. Crear la tabla `documents`

En `psql` conectado a `stocks_rag` como `postgres`:

```sql
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  ticker TEXT,
  hash TEXT UNIQUE,
  content TEXT,
  embedding VECTOR(1024),          -- mxbai-embed-large
  timestamp TIMESTAMPTZ DEFAULT now()
);
```

Notas:

* `VECTOR(1024)` porque usas `mxbai-embed-large`.
* `hash TEXT UNIQUE`:

  * aquí guardarás un hash (ej. SHA256) del **contenido** para evitar duplicados.

### 6.2. Crear el usuario dedicado `rag_user`

Sigue en `psql` como `postgres`:

```sql
CREATE USER rag_user WITH PASSWORD '<RAG_USER_PASSWORD>';
```

> Usa un placeholder tipo `<RAG_USER_PASSWORD>` en la documentación.
> En tu máquina, reemplázalo por una contraseña real, pero **no la copies al documento**.

### 6.3. Conceder permisos sobre la BD, el esquema y la tabla

```sql
GRANT CONNECT ON DATABASE stocks_rag TO rag_user;
GRANT USAGE ON SCHEMA public TO rag_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE documents TO rag_user;
```

### 6.4. Conceder permisos sobre la secuencia `documents_id_seq`

Como `id` es `SERIAL`, existe una secuencia interna que también debe ser accesible:

```sql
GRANT USAGE, SELECT ON SEQUENCE documents_id_seq TO rag_user;
```

Esto evita errores de “permission denied” cuando la app inserte filas nuevas.

### 6.5. Crear un índice vectorial para búsquedas rápidas

En `psql` (puede ser con `postgres`):

```sql
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

ANALYZE documents;
```

* `lists = 100` es un valor razonable de inicio.
* Luego puedes tunearlo según el tamaño de tu dataset.

---

## 7. Pruebas desde `psql` usando `rag_user`

Desde PowerShell o CMD:

```powershell
psql -U rag_user -d stocks_rag -h localhost
```

Escribe la contraseña real de `rag_user`.

Dentro de `psql`:

```sql
-- comprobar usuario y base actual
SELECT current_user, current_database();

-- insertar un registro de prueba
INSERT INTO documents (ticker, hash, content, embedding)
VALUES (
  'TEST',
  'test-hash',
  'documento de prueba',
  '[1,2,3]'::vector
);

-- ver que se insertó bien
SELECT id, ticker, hash FROM documents LIMIT 5;
```

Si esto funciona sin errores:

* El usuario `rag_user` está bien configurado.
* La tabla `documents` acepta vectores.
* El sistema de permisos está OK.

---

## 8. Integración con Python y el entorno `C:\IA_Local\scripts\Agentic_AI\.venv`

Ahora pasamos al entorno de tu proyecto Agentic_AI.

### 8.1. Crear archivo `.env` con la cadena de conexión

En la carpeta:

```text
C:\IA_Local\scripts\Agentic_AI
```

crea un archivo llamado **`.env`** con:

```env
PG_CONN=postgresql://rag_user:<RAG_USER_PASSWORD>@localhost:5432/stocks_rag
```

> De nuevo: en el documento deja `<RAG_USER_PASSWORD>`.
> En tu máquina reemplázalo por la contraseña real de `rag_user`.

### 8.2. Activar el venv e instalar dependencias

En **CMD**:

```bat
cd C:\IA_Local\scripts\Agentic_AI
.\.venv\Scripts\activate
```

Verás algo como:

```text
(.venv) C:\IA_Local\scripts\Agentic_AI>
```

Instala los paquetes necesarios:

```bat
pip install psycopg2-binary python-dotenv
```

### 8.3. Script mínimo de prueba de conexión (`test_pg_conn.py`)

En `C:\IA_Local\scripts\Agentic_AI`, crea `test_pg_conn.py`:

```python
import os

from dotenv import load_dotenv
import psycopg2

# Cargar variables desde .env
load_dotenv()

def get_pg_conn():
    conn_str = os.getenv("PG_CONN")
    if not conn_str:
        raise RuntimeError("PG_CONN no está definido. Revisa tu archivo .env")
    return psycopg2.connect(conn_str)

def main():
    conn = get_pg_conn()
    cur = conn.cursor()

    # Comprobar usuario / base
    cur.execute("SELECT current_user, current_database();")
    user, db = cur.fetchone()
    print("Conectado como:", user, "a la base:", db)

    # Comprobar la tabla documents
    cur.execute("SELECT COUNT(*) FROM documents;")
    count = cur.fetchone()[0]
    print("Filas en documents:", count)

    cur.close()
    conn.close()
    print("Conexión OK y cerrada.")

if __name__ == "__main__":
    main()
```

### 8.4. Ejecutar la prueba

En tu ventana CMD con `(.venv)` activo:

```bat
cd C:\IA_Local\scripts\Agentic_AI
python test_pg_conn.py
```

Si todo está bien, verás algo como:

```text
Conectado como: rag_user a la base: stocks_rag
Filas en documents: X
Conexión OK y cerrada.
```

Con esto confirmas:

* `.env` se lee bien (`PG_CONN` correcto).
* El driver `psycopg2-binary` funciona.
* `rag_user` tiene acceso completo a `documents`.

A partir de aquí, **cualquier script de RAG** puede usar el mismo patrón:

```python
from dotenv import load_dotenv
import os, psycopg2

load_dotenv()
conn = psycopg2.connect(os.getenv("PG_CONN"))
```

y seguir con la lógica de:

* Generar embeddings con `mxbai-embed-large`.
* Guardarlos en `documents.embedding`.
* Consultar similitud con `ORDER BY embedding <-> %s`.

---

## 9. Checklist rápido (para futuro tú / futuras IAs)

1. ✅ `psql --version` funciona.
2. ✅ Build Tools 2022 + Git instalados.
3. ✅ `pgvector` compilado desde GitHub oficial (`nmake /F Makefile.win install`).
4. ✅ BD `stocks_rag` creada.
5. ✅ `CREATE EXTENSION vector;` y `\dx` muestra `vector`.
6. ✅ Tabla `documents` con `VECTOR(1024)` creada.
7. ✅ Usuario `rag_user` con:

   * `CONNECT` sobre `stocks_rag`.
   * `USAGE` sobre `public`.
   * `SELECT/INSERT/UPDATE/DELETE` sobre `documents`.
   * `USAGE/SELECT` sobre `documents_id_seq`.
8. ✅ Índice `ivfflat` creado sobre `embedding`.
9. ✅ Prueba manual con `rag_user` en `psql` (INSERT + SELECT).
10. ✅ `.env` con `PG_CONN=...` configurado.
11. ✅ `test_pg_conn.py` funciona desde `C:\IA_Local\scripts\Agentic_AI\.venv`.
