"""Tests for the FD bundle splitter against the real IA dataset."""
import base64
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from main import app
from services.fd_bundle_splitter import split_fd_bundle


_BUNDLE_PATH = Path(__file__).resolve().parents[1] / "mock-data" / "pdf-ia-matching" / "FD_RO_IA_I.pdf"


@pytest.fixture(scope="module")
def bundle_bytes() -> bytes:
    if not _BUNDLE_PATH.exists():
        pytest.skip(f"Bundle fixture missing: {_BUNDLE_PATH}")
    return _BUNDLE_PATH.read_bytes()


def test_splitter_finds_multiple_fds(bundle_bytes):
    slices = split_fd_bundle(bundle_bytes)
    # Year-I bundle is known to contain ~13 obligatory disciplines;
    # accept anything in [10, 30] to allow for revisions.
    assert 10 <= len(slices) <= 30, f"unexpected slice count: {len(slices)}"


def test_splitter_slices_are_valid_pdfs(bundle_bytes):
    slices = split_fd_bundle(bundle_bytes)
    for s in slices[:3]:
        sub = pymupdf.open(stream=s.pdf_bytes, filetype="pdf")
        try:
            assert sub.page_count >= 1
            assert sub.page_count == s.page_end - s.page_start + 1
        finally:
            sub.close()


def test_splitter_extracts_course_name_hint(bundle_bytes):
    slices = split_fd_bundle(bundle_bytes)
    # The first FD in this bundle is "Analiză matematică".
    assert slices[0].course_name_hint is not None
    assert "analiz" in slices[0].course_name_hint.lower()


def test_splitter_page_ranges_are_disjoint_and_cover_bundle(bundle_bytes):
    slices = split_fd_bundle(bundle_bytes)
    # Each page must belong to exactly one slice.
    last_end = 0
    for s in slices:
        assert s.page_start == last_end + 1, (
            f"gap or overlap: prev_end={last_end}, this_start={s.page_start}"
        )
        assert s.page_end >= s.page_start
        last_end = s.page_end
    src = pymupdf.open(stream=bundle_bytes, filetype="pdf")
    try:
        assert last_end == src.page_count
    finally:
        src.close()


def test_splitter_returns_single_slice_for_unknown_layout():
    # A blank PDF with no FD header → splitter must return the whole input.
    blank = pymupdf.open()
    blank.new_page()
    payload = blank.tobytes()
    blank.close()

    slices = split_fd_bundle(payload)
    assert len(slices) == 1
    assert slices[0].course_name_hint is None
    assert slices[0].page_start == 1
    assert slices[0].page_end == 1


def test_split_fd_bundle_endpoint_returns_base64_pdfs(bundle_bytes):
    client = TestClient(app)
    response = client.post(
        "/api/documents/split-fd-bundle",
        files={"file": ("FD_RO_IA_I.pdf", bundle_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fd_count"] >= 10
    assert len(body["slices"]) == body["fd_count"]
    first = body["slices"][0]
    decoded = base64.b64decode(first["pdf_base64"])
    sub = pymupdf.open(stream=decoded, filetype="pdf")
    try:
        assert sub.page_count >= 1
    finally:
        sub.close()


def test_split_fd_bundle_endpoint_rejects_non_pdf():
    client = TestClient(app)
    response = client.post(
        "/api/documents/split-fd-bundle",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415
