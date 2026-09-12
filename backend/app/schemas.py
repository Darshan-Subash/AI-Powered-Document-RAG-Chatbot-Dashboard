from pydantic import BaseModel
from typing import Optional, List


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    num_chunks: int
    error_message: Optional[str] = None
    uploaded_at: str


class ChatOut(BaseModel):
    id: str
    title: str
    created_at: str


class SourceOut(BaseModel):
    doc_name: str
    page: Optional[int] = None


class MessageOut(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    sources: List[SourceOut] = []
    created_at: str


class AskRequest(BaseModel):
    question: str


class DashboardStats(BaseModel):
    total_documents: int
    processed: int
    processing: int
    failed: int
    total_chunks: int
    total_questions: int
    total_chats: int
