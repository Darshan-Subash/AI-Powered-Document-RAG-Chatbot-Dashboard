"""
Central configuration, loaded from environment variables (.env).
Nothing here is a secret default - copy .env.example to .env and fill it in.

This build stores everything in Supabase:
  - Postgres (with the pgvector extension) for document/chat metadata AND
    the chunk embeddings themselves - no local disk, so it survives
    restarts/redeploys/spin-downs on platforms like Render's free tier.
  - Supabase Storage for the original uploaded files.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Supabase Postgres ---
# Get this from Supabase: Project Settings -> Database -> Connection string
# (use the "Session pooler" URI if you're deploying somewhere serverless;
# the direct connection string is fine for a normal always-on server).
DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- Supabase Storage ---
# Project Settings -> API -> Project URL / service_role key.
# The service_role key is required (not the anon key) because the backend
# uploads/downloads files server-side. Never expose it to a frontend.
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "documents")

# --- Embeddings ---
# "local"        -> sentence-transformers, runs on your machine, free, no API key needed (384 dims)
# "openai"       -> direct OpenAI embeddings API, needs OPENAI_API_KEY (1536 dims for text-embedding-3-small)
# "azure_openai" -> Azure-hosted embeddings, needs AZURE_OPENAI_* vars below (1536 dims for text-embedding-3-small)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "azure_openai")
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
# Must match the actual output size of whichever embedding model you use above -
# the pgvector column is created with this fixed dimension.
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

# --- LLM ---
# one of: openai | anthropic | gemini | ollama
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- Azure OpenAI (used when MODEL_PROVIDER=azure_openai) ---
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")       # e.g. https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")   # the deployment name you chose in Azure, not the base model name

# Separate deployment for embeddings (used when EMBEDDING_PROVIDER=azure_openai).
# Usually lives in the same Azure resource as your chat deployment, so this
# falls back to the chat endpoint/key above if not set separately.
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "")
AZURE_OPENAI_EMBEDDING_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT", "") or AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_EMBEDDING_API_KEY = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY", "") or AZURE_OPENAI_API_KEY
AZURE_OPENAI_EMBEDDING_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION", "") or AZURE_OPENAI_API_VERSION

# --- RAG tuning ---
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))          # characters per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))    # overlap between chunks
TOP_K = int(os.getenv("TOP_K", "5"))                      # chunks retrieved per question
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.25"))  # below this -> "not found"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
