"""Look at the resume FILE itself, the way ATS parsers see it.

Real ATS software (Taleo, Workday, Greenhouse...) often mis-reads resumes that use:
  * two or more columns (text from both columns gets mixed together)
  * tables or text boxes for layout
  * pictures, icons, charts or a photo (ATS cannot read text inside images)
  * contact details in the page header/footer (often skipped)
  * scanned pages (no real text at all)
  * many decorative fonts or very small text
This module measures those things from the actual PDF or Word file.

PDFs are read with PyMuPDF (pdfplumber is used as a fallback). Both are turned into the
same simple structure, so the analysis below is the same for either library.
"""
import re
from collections import Counter
from pathlib import Path

CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d -]{8,14}\d")


# --------------------------------------------------------------------------- reading the file
def _pdf_pages_pymupdf(path):
    import pymupdf
    pages = []
    with pymupdf.open(path) as doc:
        for page in doc:
            words = [{"x0": w[0], "top": w[1], "x1": w[2], "bottom": w[3], "text": w[4]}
                     for w in page.get_text("words")]
            fonts, sizes = Counter(), Counter()
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        n = len(span.get("text", "").strip())
                        if n:
                            fonts[span.get("font", "").split("+")[-1]] += n
                            sizes[round(span.get("size", 0), 1)] += n
            try:
                tables = len(page.find_tables().tables)
            except Exception:
                tables = 0
            pages.append({"width": page.rect.width, "height": page.rect.height, "words": words,
                          "images": len(page.get_images(full=True)), "tables": tables,
                          "fonts": fonts, "sizes": sizes})
    return pages


def _pdf_pages_pdfplumber(path):
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = [{"x0": w["x0"], "top": w["top"], "x1": w["x1"], "bottom": w["bottom"], "text": w["text"]}
                     for w in page.extract_words()]
            fonts, sizes = Counter(), Counter()
            for ch in page.chars:
                fonts[ch.get("fontname", "").split("+")[-1]] += 1
                sizes[round(ch.get("size", 0), 1)] += 1
            try:
                tables = len(page.find_tables())
            except Exception:
                tables = 0
            pages.append({"width": page.width, "height": page.height, "words": words,
                          "images": len(page.images), "tables": tables, "fonts": fonts, "sizes": sizes})
    return pages


def _pdf_pages(path):
    try:
        return _pdf_pages_pymupdf(path)
    except ImportError:
        return _pdf_pages_pdfplumber(path)


# --------------------------------------------------------------------------- measuring
def _lines(words, tolerance=3):
    """Group words into text lines by their vertical position."""
    lines = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tolerance:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def column_score(page):
    """Find an empty vertical strip (a 'gutter') in the middle of the page.
    One-column resumes have full-width lines, so the middle is always covered by text.
    Two-column resumes leave a gap between the columns. Returns 1.0 for a clear gutter, else 0.0."""
    words = page["words"]
    if len(words) < 40:
        return 0.0
    width = page["width"]
    bin_size = 4
    coverage = [0] * (int(width // bin_size) + 1)
    for w in words:
        for b in range(int(w["x0"] // bin_size), int(w["x1"] // bin_size) + 1):
            coverage[min(b, len(coverage) - 1)] += 1
    peak = max(coverage) or 1
    middle = range(int(0.25 * width // bin_size), int(0.75 * width // bin_size))
    gutter = min(middle, key=lambda b: coverage[b])
    if coverage[gutter] > 0.02 * peak:
        return 0.0
    gutter_x = gutter * bin_size
    left = sum(1 for w in words if w["x1"] <= gutter_x)
    right = sum(1 for w in words if w["x0"] >= gutter_x)
    return 1.0 if min(left, right) >= 0.15 * len(words) else 0.0


def analyse_pdf(path):
    pages = _pdf_pages(path)
    words = [w for p in pages for w in p["words"]]
    chars = sum(len(w["text"]) for w in words)
    fonts, sizes = Counter(), Counter()
    for p in pages:
        fonts.update(p["fonts"])
        sizes.update(p["sizes"])
    families = {re.split(r"[-,]", f)[0] for f, n in fonts.items() if n > 20}
    body_size = sizes.most_common(1)[0][0] if sizes else 0
    edge_contact = False
    for p in pages:
        for w in p["words"]:
            if (w["bottom"] < 0.05 * p["height"] or w["top"] > 0.95 * p["height"]) and CONTACT.search(w["text"]):
                edge_contact = True
    return {
        "type": "pdf",
        "pages": len(pages),
        "chars_per_page": chars / max(1, len(pages)),
        "images": sum(p["images"] for p in pages),
        "tables": sum(p["tables"] for p in pages),
        "text_boxes": 0,
        "columns": max((column_score(p) for p in pages), default=0.0),
        "font_families": len(families),
        "body_font_size": body_size,
        "contact_in_header_footer": edge_contact,
    }


def analyse_docx(path):
    import docx
    document = docx.Document(path)
    text = "\n".join(p.text for p in document.paragraphs)
    xml = document.element.xml
    header_footer = " ".join(p.text for s in document.sections for part in (s.header, s.footer) for p in part.paragraphs)
    columns = len(re.findall(r'<w:cols [^>]*w:num="([2-9])"', xml)) > 0
    fonts = set(re.findall(r'w:ascii="([^"]+)"', xml))
    return {
        "type": "docx",
        "pages": max(1, round(len(text.split()) / 500)),        # Word files have no fixed pages; estimate
        "chars_per_page": len(text) / max(1, round(len(text.split()) / 500)),
        "images": len(document.inline_shapes),
        "tables": len(document.tables),
        "text_boxes": xml.count("txbxContent"),
        "columns": 0.5 if columns else 0.0,
        "font_families": len(fonts),
        "body_font_size": 0,
        "contact_in_header_footer": bool(CONTACT.search(header_footer)),
    }


def analyse(path):
    """Return a dict describing the file's layout, or None if it cannot be analysed."""
    path = Path(path or "")
    if not path.exists():
        return None
    try:
        if path.suffix.lower() == ".pdf":
            return analyse_pdf(path)
        if path.suffix.lower() == ".docx":
            return analyse_docx(path)
    except Exception:
        return None
    return None
