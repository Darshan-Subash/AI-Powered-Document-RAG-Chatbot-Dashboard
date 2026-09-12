import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.config import CORS_ORIGINS
from app.routers import documents, chat, dashboard
from app import vector_store

app = FastAPI(title="Document RAG Chatbot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
vector_store.init_vector_store()

# 1. API Endpoints & Routers (Must come first)
@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(dashboard.router)

# 2. Root Static Mount (Must come last)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")