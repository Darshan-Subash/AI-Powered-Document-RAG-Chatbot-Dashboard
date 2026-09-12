"""
Orchestrates the full document-side flow:
  get bytes (from upload or Supabase Storage) -> extract -> chunk ->
  embed -> store in pgvector -> update status in Postgres.
Runs in a background thread so the upload endpoint returns immediately and
the dashboard can show a "processing" status.
"""
import traceback
from app import document_processor, chunking, embeddings, vector_store, database, storage


def process_document(doc_id: str, filename: str, file_bytes: bytes, file_type: str):
    try:
        pages = document_processor.extract_text(file_bytes, file_type)
        if not pages:
            database.update_document_status(
                doc_id, "failed", num_chunks=0,
                error_message="No extractable text found in this file."
            )
            return

        chunks = chunking.chunk_document(doc_id, filename, pages)
        if not chunks:
            database.update_document_status(
                doc_id, "failed", num_chunks=0,
                error_message="Text was extracted but chunking produced no chunks."
            )
            return

        vectors = embeddings.embed_texts([c["text"] for c in chunks])
        vector_store.add_chunks(chunks, vectors)

        database.update_document_status(doc_id, "processed", num_chunks=len(chunks))
    except Exception as e:  # noqa: BLE001 - record any failure, don't crash the worker
        database.update_document_status(
            doc_id, "failed", num_chunks=0,
            error_message=f"{type(e).__name__}: {e}"
        )
        traceback.print_exc()


def reprocess_document(doc_id: str):
    doc = database.get_document(doc_id)
    if not doc:
        raise ValueError("Document not found")
    vector_store.delete_document_chunks(doc_id)
    database.update_document_status(doc_id, "processing", num_chunks=0, error_message=None)
    file_bytes = storage.download_bytes(doc["storage_path"])
    process_document(doc_id, doc["filename"], file_bytes, doc["file_type"])
