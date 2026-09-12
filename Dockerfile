# --- Docuery backend (also serves the static frontend) ---
# No volume needed: Postgres (Supabase) holds metadata + vector embeddings,
# and Supabase Storage holds the uploaded files. This container is fully
# stateless, which is exactly what free-tier PaaS hosts (Render, Railway,
# Fly.io) want - safe to restart, redeploy, or spin down at any time.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ./frontend

EXPOSE 8000

# --workers 1: fine for this evaluation build. Since all state now lives in
# Postgres/Storage (not in-process memory or local disk), scaling to more
# workers/instances is actually straightforward if you need it later -
# there's no shared-file or shared-SQLite constraint anymore.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
