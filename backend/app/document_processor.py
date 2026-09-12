"""
Extracts clean text from PDF / DOCX / TXT files, page by page where
possible. Works entirely on in-memory bytes (via BytesIO) since files live
in Supabase Storage, not on local disk.
Returns a list of dicts: [{"page": <int|None>, "text": <str>}, ...]
"""
import re
import io
from pypdf import PdfReader
import docx


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(data: bytes):
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = _clean(text)
        if text:
            pages.append({"page": i, "text": text})
    return pages


def extract_docx(data: bytes):
    # python-docx has no native page numbers (pagination is a rendering
    # concern in Word), so we treat each top-level section (split on the
    # document's own heading paragraphs) as a pseudo "page" for citation
    # purposes, falling back to a single block if no headings are found.
    d = docx.Document(io.BytesIO(data))
    sections = []
    current_heading = None
    current_text = []

    def flush():
        text = _clean("\n".join(current_text))
        if text:
            sections.append({"page": current_heading or (len(sections) + 1), "text": text})

    for para in d.paragraphs:
        if para.style.name.lower().startswith("heading") and current_text:
            flush()
            current_text = []
        if para.text.strip():
            current_text.append(para.text)
    flush()

    if not sections:
        return []
    return [{"page": idx + 1, "text": s["text"]} for idx, s in enumerate(sections)]


def extract_txt(data: bytes):
    text = _clean(data.decode("utf-8", errors="ignore"))
    return [{"page": None, "text": text}] if text else []


def extract_text(data: bytes, file_type: str):
    file_type = file_type.lower()
    if file_type == ".pdf":
        return extract_pdf(data)
    if file_type == ".docx":
        return extract_docx(data)
    if file_type == ".txt":
        return extract_txt(data)
    raise ValueError(f"Unsupported file type: {file_type}")
