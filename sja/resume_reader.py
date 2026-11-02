"""Lesson 2: get the text out of a resume (PDF or Word)."""
import re
from pathlib import Path

import docx   # python-docx: reads Word (.docx) files


def read_pdf(path):
    """Return all text from a PDF, page by page."""
    try:
        import pymupdf
        text = ""
        with pymupdf.open(path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
        return text
    except ImportError:                       # fallback if PyMuPDF is not installed
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)


def read_docx(path):
    """Return all text from a Word file, including text inside tables."""
    document = docx.Document(path)
    lines = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def clean(text):
    """Trim spaces, tidy bullet symbols and drop empty lines."""
    text = text.replace("\u00a0", " ")                           # non-breaking spaces
    text = re.sub(r"\(cid:\d+\)", "\u2022", text)                 # some PDF tools turn bullets into '(cid:127)'
    text = re.sub(r"[\uf000-\uf0ff\u25aa\u25cf\u25e6]", "\u2022", text)  # other bullet symbols -> •
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def extract_text(path):
    """Main function: give it a resume file, get clean text back."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        raw = read_pdf(path)
    elif ext == ".docx":
        raw = read_docx(path)
    elif ext == ".txt":
        raw = path.read_text(encoding="utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF or DOCX.")
    return clean(raw)


if __name__ == "__main__":
    text = extract_text("data/resume.pdf")
    print(text)
    print("-" * 40)
    print("Lines:", len(text.splitlines()))
    print("Words:", len(text.split()))
