"""
Metadata store using Supabase Postgres (via psycopg2 - plain SQL, no ORM).
"""
import threading
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from app.config import DATABASE_URL

_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
            "and paste your Supabase Postgres connection string into DATABASE_URL."
        )
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing',
                num_chunks INTEGER DEFAULT 0,
                error_message TEXT,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New chat',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json JSONB DEFAULT '[]',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


# ---------------- Documents ----------------

def create_document_with_id(doc_id, filename, file_type, storage_path):
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documents (id, filename, file_type, storage_path, status, uploaded_at) "
            "VALUES (%s, %s, %s, %s, 'processing', now())",
            (doc_id, filename, file_type, storage_path),
        )
    return doc_id


def update_document_status(doc_id, status, num_chunks=None, error_message=None):
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        if num_chunks is not None:
            cur.execute(
                "UPDATE documents SET status=%s, num_chunks=%s, error_message=%s WHERE id=%s",
                (status, num_chunks, error_message, doc_id),
            )
        else:
            cur.execute(
                "UPDATE documents SET status=%s, error_message=%s WHERE id=%s",
                (status, error_message, doc_id),
            )


def list_documents():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("uploaded_at"):
                r["uploaded_at"] = r["uploaded_at"].isoformat()
        return rows


def get_document(doc_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM documents WHERE id=%s", (doc_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def delete_document(doc_id):
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))


# ---------------- Chats ----------------

def create_chat(title="New chat"):
    chat_id = new_id()
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chats (id, title, created_at) VALUES (%s, %s, now())",
            (chat_id, title),
        )
    return chat_id


def list_chats():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM chats ORDER BY created_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        return rows


def rename_chat_if_default(chat_id, first_question):
    title = (first_question[:50] + "...") if len(first_question) > 50 else first_question
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title FROM chats WHERE id=%s", (chat_id,))
        row = cur.fetchone()
        if row and row["title"] == "New chat":
            cur.execute("UPDATE chats SET title=%s WHERE id=%s", (title, chat_id))


def add_message(chat_id, role, content, sources=None):
    import json
    msg_id = new_id()
    with _lock, get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (id, chat_id, role, content, sources_json, created_at) "
            "VALUES (%s, %s, %s, %s, %s, now())",
            (msg_id, chat_id, role, content, json.dumps(sources or [])),
        )
    return msg_id


def list_messages(chat_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM messages WHERE chat_id=%s ORDER BY created_at ASC", (chat_id,))
        out = []
        for r in cur.fetchall():
            d = dict(r)
            d["sources"] = d.pop("sources_json") or []
            if d.get("created_at"):
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


def dashboard_stats():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, num_chunks FROM documents")
        docs = cur.fetchall()
        total_docs = len(docs)
        processed = sum(1 for d in docs if d["status"] == "processed")
        processing = sum(1 for d in docs if d["status"] == "processing")
        failed = sum(1 for d in docs if d["status"] == "failed")
        total_chunks = sum(d["num_chunks"] or 0 for d in docs)

        cur.execute("SELECT COUNT(*) AS c FROM messages WHERE role='user'")
        total_questions = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM chats")
        total_chats = cur.fetchone()["c"]

    return {
        "total_documents": total_docs,
        "processed": processed,
        "processing": processing,
        "failed": failed,
        "total_chunks": total_chunks,
        "total_questions": total_questions,
        "total_chats": total_chats,
    }