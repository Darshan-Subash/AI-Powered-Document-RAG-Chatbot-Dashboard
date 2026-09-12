"""
Splits extracted page text into overlapping chunks, attaching metadata
(document id/name, page number, chunk id) needed for source citations.
"""
from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def _split_text(text: str, size: int, overlap: int):
    """Sliding-window split on whitespace boundaries (character-budget based,
    but never cuts a word in half)."""
    words = text.split(" ")
    chunks = []
    current = []
    current_len = 0

    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= size:
            chunks.append(" ".join(current))
            # keep the tail of this chunk as the overlap for the next one
            overlap_words = []
            overlap_len = 0
            for w in reversed(current):
                overlap_len += len(w) + 1
                overlap_words.insert(0, w)
                if overlap_len >= overlap:
                    break
            current = overlap_words
            current_len = sum(len(w) + 1 for w in current)

    if current:
        chunks.append(" ".join(current))
    return [c.strip() for c in chunks if c.strip()]


def chunk_document(doc_id: str, doc_name: str, pages: list):
    """
    pages: [{"page": int|None, "text": str}, ...]
    returns: [{"chunk_id": str, "doc_id": str, "doc_name": str,
               "page": int|None, "text": str}, ...]
    """
    chunks = []
    chunk_counter = 0
    for page_info in pages:
        page_num = page_info["page"]
        page_text = page_info["text"]
        for piece in _split_text(page_text, CHUNK_SIZE, CHUNK_OVERLAP):
            chunk_counter += 1
            chunks.append(
                {
                    "chunk_id": f"{doc_id}_chunk_{chunk_counter}",
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "page": page_num,
                    "text": piece,
                }
            )
    return chunks
