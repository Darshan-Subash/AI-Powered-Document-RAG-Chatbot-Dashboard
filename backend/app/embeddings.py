"""
Embedding provider abstraction.

- "local"        : sentence-transformers, runs fully on your machine, free,
                   no API key. First run downloads the model (~80MB) -
                   needs internet once. Produces 384-dim vectors.
- "openai"       : calls OpenAI's direct embeddings API (needs
                   OPENAI_API_KEY). 1536-dim for text-embedding-3-small.
- "azure_openai" : calls your Azure-hosted embedding deployment (needs
                   AZURE_OPENAI_EMBEDDING_DEPLOYMENT + endpoint/key).
                   Same dimension as whichever model you deployed there
                   (1536 for text-embedding-3-small/-ada-002, 3072 for
                   text-embedding-3-large).
"""
from app.config import (
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_EMBEDDING_ENDPOINT,
    AZURE_OPENAI_EMBEDDING_API_KEY,
    AZURE_OPENAI_EMBEDDING_API_VERSION,
)

_local_model = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
    return _local_model


def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in resp.data]


def _embed_azure_openai(texts: list[str]) -> list[list[float]]:
    from openai import AzureOpenAI
    if not (AZURE_OPENAI_EMBEDDING_ENDPOINT and AZURE_OPENAI_EMBEDDING_API_KEY and AZURE_OPENAI_EMBEDDING_DEPLOYMENT):
        raise RuntimeError(
            "Azure embeddings are not fully configured. Set "
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT (and either reuse "
            "AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_KEY or set the "
            "AZURE_OPENAI_EMBEDDING_ENDPOINT/_API_KEY overrides) in .env."
        )
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_EMBEDDING_ENDPOINT,
        api_key=AZURE_OPENAI_EMBEDDING_API_KEY,
        api_version=AZURE_OPENAI_EMBEDDING_API_VERSION,
    )
    # On Azure, `model` must be the deployment name you gave the embedding
    # model when you deployed it (e.g. "my-embedding-3-small"), not the
    # base model id like "text-embedding-3-small" itself.
    resp = client.embeddings.create(model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT, input=texts)
    return [item.embedding for item in resp.data]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if EMBEDDING_PROVIDER == "openai":
        return _embed_openai(texts)

    if EMBEDDING_PROVIDER == "azure_openai":
        return _embed_azure_openai(texts)

    # default: local, free
    model = _get_local_model()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
