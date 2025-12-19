# crew/rag_store.py
"""
Capa de RAG persistente (Postgres + pgvector) para la sesión 3.3.

Responsabilidades:
- Conexión a Postgres usando cadena PG_CONN (en .env).
- Asegurar extensión pgvector y tabla documents.
- Ingestar documentos con hash SHA256 (evita duplicados) y embeddings Ollama.
- Recuperar documentos relevantes por ticker mediante búsqueda vectorial.

Nota: Requiere psycopg2 o psycopg (psycopg3). Si no está instalado,
lanza RuntimeError con mensaje claro.
"""

from __future__ import annotations

import os
import hashlib
from typing import Iterable, List, Dict, Any, Tuple, Optional

import requests


def _load_pg_driver():
    """
    Intenta importar psycopg2 o psycopg (psycopg3). Lanza RuntimeError si falla.
    """
    for name in ("psycopg2", "psycopg"):
        try:
            module = __import__(name)
            return module
        except ImportError:
            continue
    raise RuntimeError(
        "No se encontró un driver de Postgres (psycopg2 o psycopg). "
        "Instala psycopg2-binary o psycopg para habilitar el RAG persistente."
    )


def _get_pg_conn():
    pg_conn = os.getenv("PG_CONN")
    if not pg_conn:
        raise RuntimeError("Falta la variable de entorno PG_CONN con la URL de Postgres.")
    drv = _load_pg_driver()
    # psycopg2 usa connect(conninfo=...), psycopg3 usa connect(dsn=...)
    if hasattr(drv, "connect"):
        try:
            return drv.connect(pg_conn)
        except TypeError:
            return drv.connect(dsn=pg_conn)
    raise RuntimeError("Driver de Postgres no soportado.")


def ensure_schema() -> None:
    """
    Crea extensión vector y tabla documents si no existen.
    """
    conn = _get_pg_conn()
    try:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
              id SERIAL PRIMARY KEY,
              ticker TEXT,
              hash TEXT UNIQUE,
              content TEXT,
              embedding VECTOR(1024),
              timestamp TIMESTAMPTZ DEFAULT now()
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _vector_literal(vec: List[float]) -> str:
    # Formato aceptado por pgvector: '[v1, v2, ...]'
    return "[" + ",".join(f"{x:.10f}" for x in vec) + "]"


def embed_text(text: str, model: str = "mxbai-embed-large", base_url: str = "http://localhost:11434") -> List[float]:
    """
    Obtiene embedding desde Ollama /api/embeddings.
    """
    url = f"{base_url.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": text}
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    emb = data.get("embedding")
    if not isinstance(emb, list):
        raise RuntimeError(f"Respuesta de embeddings inesperada: {data}")
    return [float(x) for x in emb]


def ingest_documents(docs: Iterable[Dict[str, str]], model: str = "mxbai-embed-large") -> Tuple[int, int]:
    """
    Inserta documentos nuevos:
    - Calcula hash.
    - Si ya existe, lo omite.
    - Genera embedding y guarda ticker, contenido, hash, embedding.

    Retorna: (nuevos_insertados, duplicados)
    """
    conn = _get_pg_conn()
    new_count = 0
    dup_count = 0
    try:
        cur = conn.cursor()
        for doc in docs:
            content = (doc.get("content") or "").strip()
            ticker = (doc.get("ticker") or "").strip().upper()
            if not content:
                continue
            h = _hash_content(content)
            # Verificar duplicado
            cur.execute("SELECT 1 FROM documents WHERE hash = %s;", (h,))
            if cur.fetchone():
                dup_count += 1
                continue
            embedding = embed_text(content, model=model)
            cur.execute(
                """
                INSERT INTO documents (ticker, hash, content, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                (ticker, h, content, _vector_literal(embedding)),
            )
            new_count += 1
        conn.commit()
    finally:
        conn.close()
    return new_count, dup_count


def query_similar(
    ticker: Optional[str],
    query: str,
    k: int = 5,
    model: str = "mxbai-embed-large",
) -> List[str]:
    """
    Recupera los k documentos más cercanos al embedding de query.
    Si ticker viene, filtra por ticker.
    """
    q_emb = embed_text(query, model=model)
    q_vec = _vector_literal(q_emb)
    conn = _get_pg_conn()
    rows: List[str] = []
    try:
        cur = conn.cursor()
        if ticker:
            cur.execute(
                """
                SELECT content
                FROM documents
                WHERE ticker = %s
                ORDER BY embedding <-> %s::vector
                LIMIT %s;
                """,
                (ticker.upper(), q_vec, k),
            )
        else:
            cur.execute(
                """
                SELECT content
                FROM documents
                ORDER BY embedding <-> %s::vector
                LIMIT %s;
                """,
                (q_vec, k),
            )
        rows = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    return rows
