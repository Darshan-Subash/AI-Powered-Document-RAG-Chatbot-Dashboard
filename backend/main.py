import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.config import CORS_ORIGINS
from app.routers import documents, chat, dashboard
from app import vector_store

app = FastAPI(title="Docuery API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
vector_store.init_vector_store()

# API Endpoints
@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(dashboard.router)

# Locate Frontend Folder Across Local & Cloud Environments
CURRENT_FILE = Path(__file__).resolve()
POSSIBLE_FRONTEND_DIRS = [
    CURRENT_FILE.parent.parent / "frontend",          # local: repo_root/frontend
    CURRENT_FILE.parent / "frontend",                 # backend/frontend
    Path("/opt/render/project/src/frontend"),        # Render standard path
    Path("frontend").resolve(),                       # current working directory
]

FRONTEND_DIR = None
for candidate in POSSIBLE_FRONTEND_DIRS:
    if candidate.is_dir() and (candidate / "index.html").exists():
        FRONTEND_DIR = candidate
        break

if FRONTEND_DIR:
    # Explicit root route to guarantee index.html loads on Render
    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(FRONTEND_DIR / "index.html")

    # Mount remaining static assets (styles.css, app.js, icons)
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    async def missing_frontend():
        return {"error": "Frontend directory could not be located on server"}
