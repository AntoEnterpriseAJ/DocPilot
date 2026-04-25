"""Tests for the deterministic PI fast parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.pi_fast_parser import parse_pi


_DATA = Path(__file__).resolve().parent.parent / "mock-data"


def test_parse_ia_pi():
    raw = (_DATA / "pdf-ia-matching/PI_Informatica_aplicata_2025_2028.pdf").read_bytes()
    doc = parse_pi(raw)
    assert doc is not None
    assert doc.source_route == "fast_pdfplumber"
    assert doc.document_type == "plan_de_invatamant"

    # Expect 3 obligatorii tables (one per year) plus optional/facultative.
    table_names = [t.name for t in doc.tables]
    obligatorii = [n for n in table_names if "obligatorii" in n]
    assert len(obligatorii) == 3, f"expected 3 obligatorii tables, got {table_names}"
    assert any(n.endswith("_anul_i") for n in obligatorii)
    assert any(n.endswith("_anul_ii") for n in obligatorii)
    assert any(n.endswith("_anul_iii") for n in obligatorii)

    # First obligatorii table should contain Analiză matematică with credits 5.
    year1 = next(t for t in doc.tables if t.name.endswith("_obligatorii_anul_i"))
    assert "disciplina" in year1.headers
    assert "s1_cr" in year1.headers
    rows_by_name = {r[1].lower(): r for r in year1.rows}
    assert any("analiză matematică" in name for name in rows_by_name)
    am_row = next(r for n, r in rows_by_name.items() if "analiză matematică" in n)
    cr_idx = year1.headers.index("s1_cr")
    assert am_row[cr_idx] == "5"


def test_returns_none_on_garbage():
    assert parse_pi(b"") is None
    assert parse_pi(b"not a pdf") is None
