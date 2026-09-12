"""
Vector store using the pgvector extension inside the same Supabase Postgres
database as the metadata tables - no separate vector DB service, no local
disk. Requires the "vector" extension, which init_vector_store() enables
(Supabase permits this for the default postgres role).
"""
from app.database import get_conn, _lock
from app.config import EMBEDDING_DIM


def init_vector_store():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                doc_name TEXT NOT NULL,
                page INTEGER,
                content TEXT NOT NULL,
                embedding VECTOR({EMBEDDING_DIM}) NOT NULL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id);")


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def add_chunks(chunks: list[dict], embeddings: list[list[float]]):
    if not chunks:
        return
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        for chunk, embedding in zip(chunks, embeddings):
            cur.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, doc_name, page, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    doc_name = EXCLUDED.doc_name,
                    page = EXCLUDED.page,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding
                """,
                (
                    chunk["chunk_id"],
                    chunk["doc_id"],
                    chunk["doc_name"],
                    chunk["page"],
                    chunk["text"],
                    _vector_literal(embedding),
                ),
            )


def query(embedding: list[float], top_k: int = 5):
    vector_str = _vector_literal(embedding)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT chunk_id, doc_id, doc_name, page, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_str, vector_str, top_k),
        )
        rows = cur.fetchall()
    return [
        {
            "chunk_id": r["chunk_id"],
            "text": r["content"],
            "doc_id": r["doc_id"],
            "doc_name": r["doc_name"],
            "page": r["page"],
            "score": float(r["similarity"]),
        }
        for r in rows
    ]


def delete_document_chunks(doc_id: str):
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM chunks WHERE doc_id=%s", (doc_id,))
