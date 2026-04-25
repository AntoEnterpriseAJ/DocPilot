"""Split a multi-FD bundle PDF into individual FD PDFs.

Romanian universities often distribute Fișa Disciplinei sheets as a single
concatenated PDF (one per discipline, ~3-6 pages each). This module detects
each FD's start page by looking for the heading "FIȘA DISCIPLINEI" near the
top of a page, then carves the bundle into per-FD PDFs in memory.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pymupdf


_HEADER_RE = re.compile(r"FI[ȘŞS]A\s+DISCIPLINEI", re.IGNORECASE)
_DATE_PROGRAM_RE = re.compile(r"^\s*1\.\s*Date\s+despre\s+program", re.IGNORECASE | re.MULTILINE)
_COURSE_NAME_RE = re.compile(
    r"2\.1\s*Denumirea\s+disciplinei\s*[:\-]?\s*([^\n\r]+)", re.IGNORECASE
)


@dataclass
class FdSlice:
    """One discipline carved out of a bundle."""
    index: int  # 1-based ordinal within the bundle
    course_name_hint: str | None
    page_start: int  # 1-based, inclusive
    page_end: int    # 1-based, inclusive
    pdf_bytes: bytes


def split_fd_bundle(pdf_bytes: bytes) -> list[FdSlice]:
    """Carve a bundle of concatenated FD sheets into individual PDFs.

    Returns one FdSlice per detected FD. If no FD header is detected,
    returns a single slice containing the whole input.
    """
    if not pdf_bytes:
        return []

    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        starts = _detect_fd_start_pages(src)
        if not starts:
            return [FdSlice(
                index=1,
                course_name_hint=None,
                page_start=1,
                page_end=src.page_count,
                pdf_bytes=pdf_bytes,
            )]

        slices: list[FdSlice] = []
        for i, start in enumerate(starts):
            end = (starts[i + 1] - 1) if i + 1 < len(starts) else (src.page_count - 1)
            name = _extract_course_name(src, start, end)
            sub = pymupdf.open()
            sub.insert_pdf(src, from_page=start, to_page=end)
            buf = sub.tobytes()
            sub.close()
            slices.append(FdSlice(
                index=i + 1,
                course_name_hint=name,
                page_start=start + 1,
                page_end=end + 1,
                pdf_bytes=buf,
            ))
        return slices
    finally:
        src.close()


def _detect_fd_start_pages(doc: "pymupdf.Document") -> list[int]:
    """Return 0-based page indices that start a new FD.

    A page starts an FD when the heading "FIȘA DISCIPLINEI" appears in the
    first 3 non-empty lines AND section "1. Date despre program" appears
    early on the same page. The combined check eliminates false positives
    triggered by mid-FD prose mentioning "Fișa disciplinei".
    """
    starts: list[int] = []
    for i in range(doc.page_count):
        text = doc[i].get_text() or ""
        head_lines = [ln for ln in text.split("\n")[:6] if ln.strip()]
        head_block = "\n".join(head_lines[:3])
        if not _HEADER_RE.search(head_block):
            continue
        # Confirm with the section-1 anchor to drop body-text mentions.
        first_block = "\n".join(text.split("\n")[:8])
        if not _DATE_PROGRAM_RE.search(first_block):
            continue
        starts.append(i)
    return starts


def _extract_course_name(
    doc: "pymupdf.Document", start: int, end: int
) -> str | None:
    """Best-effort: find '2.1 Denumirea disciplinei' on the first page."""
    pages_to_check = min(end - start + 1, 2)
    for offset in range(pages_to_check):
        text = doc[start + offset].get_text() or ""
        m = _COURSE_NAME_RE.search(text)
        if m:
            name = m.group(1).strip()
            # Strip trailing footnote markers and whitespace
            name = re.sub(r"\s+", " ", name).rstrip(" .,;")
            if name:
                return name
    return None
