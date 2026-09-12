import os
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from app import database, pipeline, vector_store, storage
from app.config import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/api/documents", tags=["documents"])

_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


@router.post("")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    file_bytes = await file.read()

    doc_id = database.new_id()
    storage_path = f"{doc_id}{ext}"

    try:
        storage.upload_bytes(storage_path, file_bytes, _CONTENT_TYPES.get(ext, "application/octet-stream"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not upload to Supabase Storage: {e}")

    database.create_document_with_id(doc_id, file.filename, ext, storage_path)

    background_tasks.add_task(pipeline.process_document, doc_id, file.filename, file_bytes, ext)

    return {"id": doc_id, "filename": file.filename, "status": "processing"}


@router.get("")
async def get_documents():
    return database.list_documents()


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    vector_store.delete_document_chunks(doc_id)
    try:
        storage.delete_object(doc["storage_path"])
    except Exception:
        pass  # object may already be gone - don't block metadata cleanup
    database.delete_document(doc_id)
    return {"status": "deleted"}


@router.post("/{doc_id}/reprocess")
async def reprocess_document(doc_id: str, background_tasks: BackgroundTasks):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    background_tasks.add_task(pipeline.reprocess_document, doc_id)
    return {"status": "processing"}
