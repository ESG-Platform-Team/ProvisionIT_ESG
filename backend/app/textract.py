"""
Turning fetched bytes into text a model can read, while keeping the page number.

The locator is the whole point. Without "Gov statement p.12" the evidence trail
is decorative, so text is kept per page rather than as one blob.

OCR is the branch the scorecard mock forced. If a PDF has no text layer it is a
scanned image, and in the AWS design Textract handles it. Locally that is
Tesseract. If Tesseract is not installed the document is marked UNREADABLE,
which is an honest EVIDENCE_GAP rather than a silent zero.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile

from bs4 import BeautifulSoup

MIN_CHARS_FOR_TEXT_LAYER = 200


def extract(doc) -> tuple[str, list[str], str]:
    """Return (full_text, pages, method). pages[i] is page i+1."""
    media = doc.media_type
    if "pdf" in media or doc.url.lower().split("?")[0].endswith(".pdf"):
        return _pdf(doc.content)
    if "html" in media or "xml" in media:
        return _html(doc.content)
    if "text" in media:
        text = doc.content.decode("utf-8", errors="replace")
        return text, [text], "plain"
    return "", [], "unsupported"


def _pdf(data: bytes) -> tuple[str, list[str], str]:
    pages: list[str] = []
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                pages.append(_clean(page.extract_text() or ""))
    except Exception:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = [_clean(p.extract_text() or "") for p in reader.pages]
        except Exception:
            return "", [], "failed"

    full = "\n".join(pages)
    if len(full.strip()) >= MIN_CHARS_FOR_TEXT_LAYER:
        return full, pages, "native"

    ocr_pages = _ocr(data)
    if ocr_pages:
        return "\n".join(ocr_pages), ocr_pages, "ocr"
    return full, pages, "scanned_no_ocr"


def _ocr(data: bytes) -> list[str]:
    """Tesseract fallback. Maps to Amazon Textract in the deployment design."""
    if not shutil.which("tesseract") or not shutil.which("pdftoppm"):
        return []
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = f"{tmp}/in.pdf"
        with open(pdf_path, "wb") as fh:
            fh.write(data)
        try:
            subprocess.run(
                ["pdftoppm", "-r", "200", "-png", pdf_path, f"{tmp}/page"],
                check=True, capture_output=True, timeout=300,
            )
        except (subprocess.SubprocessError, OSError):
            return []
        import glob

        out: list[str] = []
        for img in sorted(glob.glob(f"{tmp}/page-*.png")):
            try:
                res = subprocess.run(
                    ["tesseract", img, "stdout"], capture_output=True, timeout=120
                )
                out.append(_clean(res.stdout.decode("utf-8", errors="replace")))
            except (subprocess.SubprocessError, OSError):
                out.append("")
        return out


def _html(data: bytes) -> tuple[str, list[str], str]:
    soup = BeautifulSoup(data, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    text = _clean(soup.get_text("\n"))
    return text, [text], "html"


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def windows_for(pages: list[str], keywords: list[str], radius: int = 1400,
                max_chars: int = 26000) -> list[tuple[int, str]]:
    """Passages around keyword hits, with the page number kept.

    This exists for two reasons. It cuts the token bill, because sending a
    200 page annual report per principle would burn the free tier quota in one
    company. And it improves extraction, because a model reading four relevant
    passages is more accurate than one skimming a whole report.
    """
    if not keywords:
        return []
    out: list[tuple[int, str]] = []
    budget = max_chars
    lowered = [k.lower() for k in keywords]

    for page_no, page in enumerate(pages, start=1):
        if budget <= 0:
            break
        low = page.lower()
        spans: list[tuple[int, int]] = []
        for kw in lowered:
            start = 0
            while True:
                idx = low.find(kw, start)
                if idx < 0:
                    break
                spans.append((max(0, idx - radius), min(len(page), idx + radius)))
                start = idx + len(kw)
        if not spans:
            continue
        for lo, hi in _merge(spans):
            chunk = page[lo:hi].strip()
            if not chunk:
                continue
            chunk = chunk[:budget]
            budget -= len(chunk)
            out.append((page_no, chunk))
            if budget <= 0:
                break
    return out


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    spans.sort()
    merged: list[tuple[int, int]] = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged
