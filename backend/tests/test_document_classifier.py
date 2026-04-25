"""Tests for the FD/PI document classifier."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.document_classifier import classify


_DATA = Path(__file__).resolve().parent.parent / "mock-data"


def _read(rel: str) -> bytes:
    return (_DATA / rel).read_bytes()


def test_classifies_fd_bundle_as_fd():
    assert classify(_read("pdf-ia-matching/FD_RO_IA_I.pdf")) == "fd"


def test_classifies_pi_as_pi():
    assert classify(_read("pdf-ia-matching/PI_Informatica_aplicata_2025_2028.pdf")) == "pi"


def test_classifies_legacy_pi_as_unknown_when_scanned():
    # The legacy plan_invatamant.pdf is image-only (scanned) — pdfplumber
    # extracts no text, so the fast classifier must return "unknown" and
    # let the route fall through to Claude Vision.
    assert classify(_read("plan_invatamant.pdf")) == "unknown"


def test_classifies_legacy_fd_as_fd():
    assert classify(_read("fisa_disciplina-1-7.pdf")) == "fd"


def test_empty_bytes_unknown():
    assert classify(b"") == "unknown"


def test_garbage_bytes_unknown():
    assert classify(b"not a pdf") == "unknown"
