"""Lightweight PDF document classifier.

Decides whether a PDF is a Romanian academic Fișa Disciplinei (FD) or a
Plan de Învățământ (PI), so the /parse route can dispatch to a fast
deterministic parser instead of paying for Claude.

Pure heuristic — no Claude calls.
"""
from __future__ import annotations

import io
import re
from typing import Literal

import pdfplumber


DocumentKind = Literal["fd", "pi", "unknown"]


_FD_HEADER_RE = re.compile(r"FI[ȘŞS]A\s+DISCIPLINEI", re.IGNORECASE)
_FD_SECTION1_RE = re.compile(
    r"^\s*1\.\s*Date\s+despre\s+program", re.IGNORECASE | re.MULTILINE
)
_PI_HEADER_RE = re.compile(r"PLAN\s+DE\s+[ÎI]NV[ĂA][ȚŢT][ĂA]M[ÂA]NT", re.IGNORECASE)
_PI_PROGRAM_RE = re.compile(r"Programul\s+de\s+studii", re.IGNORECASE)
_PI_TABLE_HEADER_RE = re.compile(
    r"\bSemestrul\s+I\b.*\bSemestrul\s+II\b", re.IGNORECASE | re.DOTALL
)


def classify(pdf_bytes: bytes) -> DocumentKind:
    """Return ``"fd"``, ``"pi"``, or ``"unknown"`` for the given PDF bytes.

    Inspects only the first few pages so it stays fast even for big bundles.
    """
    if not pdf_bytes:
        return "unknown"

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return _classify(pdf)
    except Exception:
        return "unknown"


def _classify(pdf) -> DocumentKind:
    page_count = len(pdf.pages)
    if page_count == 0:
        return "unknown"

    head_text_parts: list[str] = []
    for i in range(min(3, page_count)):
        head_text_parts.append(pdf.pages[i].extract_text() or "")
    head_text = "\n".join(head_text_parts)

    head_lines = [ln for ln in head_text.split("\n")[:12] if ln.strip()]
    head_block = "\n".join(head_lines)

    # FD detection requires both anchors to avoid false positives.
    if _FD_HEADER_RE.search(head_block) and _FD_SECTION1_RE.search(head_block):
        return "fd"

    if _PI_HEADER_RE.search(head_block):
        return "pi"
    if _PI_PROGRAM_RE.search(head_block):
        for i in range(min(page_count, 12)):
            text = pdf.pages[i].extract_text() or ""
            if _PI_TABLE_HEADER_RE.search(text):
                return "pi"

    return "unknown"

