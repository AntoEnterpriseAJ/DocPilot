"""Tests for UC 1.2 numeric consistency checker."""

from __future__ import annotations

from schemas.extraction import ExtractedDocument, ExtractedField
from services.numeric_consistency import check_fd_numeric_consistency


def _fd(**numbers: float) -> ExtractedDocument:
    fields = [
        ExtractedField(key=k, value=float(v), field_type="number")
        for k, v in numbers.items()
    ]
    return ExtractedDocument(
        document_type="FIȘA DISCIPLINEI",
        source_route="text_pdf",
        summary="",
        fields=fields,
    )


def test_consistent_fd_passes_all_checks():
    fd = _fd(
        ore_curs_pe_saptamana=2,
        ore_seminar_laborator_proiect_pe_saptamana=2,
        numar_ore_pe_saptamana_total=4,
        total_ore_curs=28,
        total_ore_seminar_laborator_proiect=28,
        total_ore_plan_invatamant=56,
        total_ore_studiu_individual=94,
        total_ore_pe_semestru=150,
        numarul_de_credite=6,
    )
    report = check_fd_numeric_consistency(fd)
    assert report.issues == []
    assert report.passed == report.total_checks == 6


def test_weekly_sum_mismatch_is_flagged():
    fd = _fd(
        ore_curs_pe_saptamana=2,
        ore_seminar_laborator_proiect_pe_saptamana=2,
        numar_ore_pe_saptamana_total=5,  # claims 5 but 2+2=4
    )
    report = check_fd_numeric_consistency(fd)
    codes = {i.code for i in report.issues}
    assert "weekly_sum_mismatch" in codes


def test_semester_total_mismatch_is_flagged():
    fd = _fd(
        total_ore_curs=28,
        total_ore_seminar_laborator_proiect=28,
        total_ore_plan_invatamant=70,  # 28+28=56, not 70
    )
    report = check_fd_numeric_consistency(fd)
    codes = {i.code for i in report.issues}
    assert "semester_total_mismatch" in codes


def test_credits_out_of_range_is_flagged():
    fd = _fd(numarul_de_credite=42)
    report = check_fd_numeric_consistency(fd)
    codes = {i.code for i in report.issues}
    assert "credits_out_of_range" in codes


def test_ects_hours_mismatch_is_flagged():
    fd = _fd(
        numarul_de_credite=6,
        total_ore_pe_semestru=50,  # should be ~150 for 6 credits
    )
    report = check_fd_numeric_consistency(fd)
    codes = {i.code for i in report.issues}
    assert "ects_hours_mismatch" in codes


def test_no_fields_no_checks():
    fd = ExtractedDocument(
        document_type="FIȘA DISCIPLINEI",
        source_route="text_pdf",
        summary="",
        fields=[],
    )
    report = check_fd_numeric_consistency(fd)
    assert report.total_checks == 0
    assert "insuficiente" in report.summary
