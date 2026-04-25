"""Tests for the deterministic FD fast parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.fd_bundle_splitter import split_fd_bundle
from services.fd_fast_parser import parse_fd


_DATA = Path(__file__).resolve().parent.parent / "mock-data"


def _field(doc, key):
    for f in doc.fields:
        if f.key == key:
            return f.value
    return None


def test_parse_first_fd_in_ia_bundle():
    raw = (_DATA / "pdf-ia-matching/FD_RO_IA_I.pdf").read_bytes()
    slices = split_fd_bundle(raw)
    assert slices, "expected at least one FD slice in the bundle"

    first = slices[0]
    doc = parse_fd(first.pdf_bytes)
    assert doc is not None, "fast parser should succeed on a single FD"

    assert doc.source_route == "fast_pdfplumber"
    assert doc.document_type == "fisa_disciplinei"

    # First IA-I FD is "Analiză matematică", 6 credits.
    assert _field(doc, "denumirea_disciplinei") == "Analiză matematică"
    assert _field(doc, "numarul_de_credite") == 6.0
    assert _field(doc, "anul_de_studiu") in ("1", 1)
    assert _field(doc, "semestrul") in ("1", 1)
    assert _field(doc, "tipul_de_evaluare") == "E"
    assert _field(doc, "regimul_disciplinei_continut") == "DC"


def test_returns_none_on_garbage():
    assert parse_fd(b"") is None
    assert parse_fd(b"not a pdf") is None
