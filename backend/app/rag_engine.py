"""
Core RAG logic: embed the question, retrieve the most relevant chunks,
build a strictly-grounded prompt, call the LLM, and return the answer
together with the exact sources used.

Hallucination guardrail strategy (belt and suspenders):
  1. If nothing relevant is retrieved (or best score is below
     MIN_RELEVANCE_SCORE), we skip the LLM entirely and return the
     "not found" message - no chance for the model to improvise.
  2. When we do call the LLM, the system prompt explicitly forbids using
     outside/general knowledge and requires the fixed "not found" phrase
     when the context doesn't answer the question.
  3. Retrieved chunks are numbered [1], [2], ... and the model is asked to
     cite which numbered chunks it used; we map those back to real
     doc name + page for the "Sources" section shown in the UI.
"""
from app import embeddings, vector_store, llm_client
from app.config import TOP_K, MIN_RELEVANCE_SCORE

NOT_FOUND_MESSAGE = (
    "I couldn't find information about this in the uploaded documents."
)

SYSTEM_PROMPT = f"""You are a document question-answering assistant.

Rules you must follow exactly:
1. Answer ONLY using the numbered context chunks provided below. Do not use
   any outside knowledge, assumptions, or information not present in the
   context, even if you believe you know the answer.
2. If the context does not contain enough information to answer the
   question, respond with exactly this sentence and nothing else:
   "{NOT_FOUND_MESSAGE}"
3. When you do answer, be concise and directly address the question.
4. At the end of your answer, on a new line, list which chunk numbers you
   actually used, like: "Used: [1], [3]". If you used none (because you
   returned the not-found message), write "Used: none".
"""


def _build_context_block(chunks):
    lines = []
    for i, c in enumerate(chunks, start=1):
        page_label = f"p.{c['page']}" if c["page"] else "n/a"
        lines.append(f"[{i}] (source: {c['doc_name']}, page {page_label})\n{c['text']}")
    return "\n\n".join(lines)


def _parse_used_indices(answer_text: str, num_chunks: int):
    import re
    match = re.search(r"Used:\s*(.+)$", answer_text.strip(), re.IGNORECASE | re.MULTILINE)
    if not match:
        return list(range(1, num_chunks + 1))  # fallback: cite everything retrieved
    used_str = match.group(1).strip().lower()
    if used_str.startswith("none"):
        return []
    indices = [int(n) for n in re.findall(r"\d+", used_str)]
    return [i for i in indices if 1 <= i <= num_chunks]


def _strip_used_line(answer_text: str) -> str:
    import re
    return re.sub(r"\n?Used:\s*.+$", "", answer_text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def answer_question(question: str):
    query_embedding = embeddings.embed_query(question)
    retrieved = vector_store.query(query_embedding, top_k=TOP_K)

    print("\n--- RETRIEVED CHUNKS ---")
    for r in retrieved:
        print(f"Doc: {r['doc_name']} | Page: {r['page']} | Score: {r['score']:.4f}")
    print("------------------------\n")

    if not retrieved or retrieved[0]["score"] < MIN_RELEVANCE_SCORE:
        print(f"[RAG] Short-circuited by MIN_RELEVANCE_SCORE ({MIN_RELEVANCE_SCORE})")
        return {"answer": NOT_FOUND_MESSAGE, "sources": [], "retrieved": retrieved}

    context_block = _build_context_block(retrieved)
    user_prompt = (
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        f"Answer using only the context above, following all the rules."
    )

    raw_answer = llm_client.generate(SYSTEM_PROMPT, user_prompt)
    used_indices = _parse_used_indices(raw_answer, len(retrieved))
    clean_answer = _strip_used_line(raw_answer)

    sources = []
    seen = set()
    for idx in used_indices:
        chunk = retrieved[idx - 1]
        key = (chunk["doc_name"], chunk["page"])
        if key not in seen:
            seen.add(key)
            sources.append({"doc_name": chunk["doc_name"], "page": chunk["page"]})

    return {"answer": clean_answer, "sources": sources, "retrieved": retrieved}