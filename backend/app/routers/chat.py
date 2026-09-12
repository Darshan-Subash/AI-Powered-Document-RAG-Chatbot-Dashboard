import traceback
from fastapi import APIRouter, HTTPException
from app import database, rag_engine
from app.schemas import AskRequest

router = APIRouter(prefix="/api/chats", tags=["chat"])


@router.post("")
async def create_chat():
    chat_id = database.create_chat()
    return {"id": chat_id, "title": "New chat"}


@router.get("")
async def get_chats():
    return database.list_chats()


@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str):
    return database.list_messages(chat_id)


@router.post("/{chat_id}/messages")
async def ask_question(chat_id: str, body: AskRequest):
    chats = {c["id"] for c in database.list_chats()}
    if chat_id not in chats:
        raise HTTPException(status_code=404, detail="Chat not found")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    database.add_message(chat_id, "user", question)
    database.rename_chat_if_default(chat_id, question)

    try:
        result = rag_engine.answer_question(question)
    except Exception as e:
        traceback.print_exc()  # Prints the full traceback directly to your terminal
        error_text = (
            "Something went wrong while generating the answer "
            f"({type(e).__name__}: {e}). Please check your LLM provider "
            "configuration in .env and try again."
        )
        database.add_message(chat_id, "assistant", error_text, sources=[])
        raise HTTPException(status_code=500, detail=error_text)

    database.add_message(chat_id, "assistant", result["answer"], sources=result["sources"])

    return {
        "answer": result["answer"],
        "sources": result["sources"],
    }