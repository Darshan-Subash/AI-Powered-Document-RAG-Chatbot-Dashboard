"""
Thin wrapper around Supabase Storage for the original uploaded files.
Files are never written to local disk, so there's nothing to lose when
a host like Render spins the service down or redeploys it.
"""
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET

_client = None


def get_client():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY are not set. Copy "
                "backend/.env.example to backend/.env and fill them in from "
                "your Supabase project's API settings."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def upload_bytes(storage_path: str, data: bytes, content_type: str = "application/octet-stream"):
    client = get_client()
    client.storage.from_(SUPABASE_BUCKET).upload(
        storage_path, data, {"content-type": content_type, "upsert": "true"}
    )


def download_bytes(storage_path: str) -> bytes:
    client = get_client()
    return client.storage.from_(SUPABASE_BUCKET).download(storage_path)


def delete_object(storage_path: str):
    client = get_client()
    client.storage.from_(SUPABASE_BUCKET).remove([storage_path])
