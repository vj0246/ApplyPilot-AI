"""
resume_service.py
------------------
Saves uploaded resume files and pulls plain text out of them. The PDF path
has a two-step fallback because PyMuPDF occasionally comes back nearly
empty on resumes exported from certain design tools (Canva-built resumes
in particular) — pdfminer catches some of what PyMuPDF misses.
"""
import uuid
from pathlib import Path
from app.core.config import settings

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}
ALLOWED_EXT = {".pdf", ".docx", ".doc", ".txt"}


def get_mime(filename: str, content_type: str = "") -> str:
    # browsers send inconsistent content-type headers for office docs, so
    # trust the extension first and fall back to content_type
    ext = Path(filename).suffix.lower()
    return {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc":  "application/msword",
        ".txt":  "text/plain",
    }.get(ext, content_type or "application/octet-stream")


def save_file(data: bytes, filename: str, user_id: str) -> str:
    folder = Path(settings.UPLOAD_DIR) / "resumes" / user_id
    folder.mkdir(parents=True, exist_ok=True)
    ext  = Path(filename).suffix or ".pdf"
    path = folder / f"{uuid.uuid4()}{ext}"
    path.write_bytes(data)
    return str(path)


def extract_text(file_path: str, mime_type: str) -> str:
    p = Path(file_path)

    if mime_type == "application/pdf":
        try:
            import fitz
            doc  = fitz.open(str(p))
            text = "\n".join(page.get_text("text") for page in doc)
            # Resumes usually hide the real URL behind clickable text like
            # "LinkedIn" or "GitHub" — the target lives in the PDF's link
            # annotations, not in the text layer, so without this the
            # parser never sees the actual profile URLs.
            links: list[str] = []
            for page in doc:
                for lnk in page.get_links():
                    uri = (lnk.get("uri") or "").strip()
                    if uri and uri not in links:
                        links.append(uri)
            if links:
                text += (
                    "\n\nHyperlinks embedded in the document, these are the real clickable "
                    "link targets, exactly as they appear in the file:\n"
                    + "\n".join(links)
                )
            if len(text.strip()) > 80:
                return text
        except Exception:
            pass
        try:
            from pdfminer.high_level import extract_text as pm
            text = pm(str(p))
            if text and len(text.strip()) > 80:
                return text
        except Exception:
            pass
        raise ValueError("Could not extract text from PDF.")

    if "word" in mime_type or p.suffix.lower() in (".docx", ".doc"):
        # python-docx only reads paragraph text, not tables or text boxes —
        # fine for the vast majority of resumes which are paragraphs + bullets
        import docx as dx
        doc  = dx.Document(str(p))
        text = "\n".join(par.text for par in doc.paragraphs if par.text.strip())
        if not text:
            raise ValueError("DOCX file appears empty.")
        return text

    if mime_type == "text/plain" or p.suffix.lower() == ".txt":
        return p.read_text(encoding="utf-8", errors="replace")

    raise ValueError(f"Unsupported file type: {mime_type}")
