"""Tests for cross-document validation (FD ↔ Plan de Învățământ)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemas.extraction import ExtractedDocument
from services.cross_doc_validator import cross_validate


MOCK_DIR = Path(__file__).parent.parent / "mock-data"


def _load(name: str) -> ExtractedDocument:
    raw = json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))
    raw.setdefault("source_route", "text_pdf")
    return ExtractedDocument(**raw)


@pytest.fixture
def fd() -> ExtractedDocument:
    return _load("fisa_disciplina.parsed.json")


@pytest.fixture
def plan() -> ExtractedDocument:
    return _load("plan_invatamant.full.parsed.json")


def test_cross_validate_finds_matching_course(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    """The mock FD ('Analiză matematică') must be located in the plan tables."""
    result = cross_validate(fd=fd, plan=plan)
    assert result.fd_course_name == "Analiză matematică"
    assert result.plan_match is not None
    assert result.plan_match.course_name.lower().startswith("analiz")
    assert result.plan_match.course_code == "APO01-ID"


def test_cross_validate_admin_fields_align_when_credits_match(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    """When FD credits are aligned with plan (5 + 'E'), no field violations are raised.

    Note: the mock FD as-shipped has credits=6 vs plan=5 (a real extraction
    inconsistency in the source data). Patch credits to 5 to isolate the
    admin-field check.
    """
    for f in fd.fields:
        if f.key == "numarul_de_credite":
            f.value = 5.0

    result = cross_validate(fd=fd, plan=plan)
    assert result.field_violations == []
    assert result.plan_match is not None
    assert result.plan_match.credits == 5.0
    assert result.plan_match.evaluation_form == "E"


def test_cross_validate_detects_credits_mismatch(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    # Tamper FD credits to 7 — plan says 5
    for f in fd.fields:
        if f.key == "numarul_de_credite":
            f.value = 7.0

    result = cross_validate(fd=fd, plan=plan)
    assert result.status == "invalid"
    codes = [v.code for v in result.field_violations]
    assert "credits_mismatch" in codes


def test_cross_validate_detects_evaluation_mismatch(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    # Plan has "E" (examen). Force FD to "C" (colocviu).
    for f in fd.fields:
        if f.key == "tipul_de_evaluare":
            f.value = "C"

    result = cross_validate(fd=fd, plan=plan)
    assert result.status == "invalid"
    codes = [v.code for v in result.field_violations]
    assert "evaluation_form_mismatch" in codes


def test_cross_validate_detects_unknown_competency(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    # Inject a bogus competency code that isn't in the plan
    fd.fields.append(type(fd.fields[0])(
        key="competenta_profesionala_cod_extra",
        value="CP 99",
        field_type="id",
        confidence="high",
    ))

    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.competency_violations]
    assert "competency_not_in_plan" in codes
    assert any("CP99" in v.message or "CP 99" in v.message for v in result.competency_violations)


def test_cross_validate_handles_missing_course_name() -> None:
    fd = ExtractedDocument(document_type="FD", summary="", source_route="text_pdf")
    plan = ExtractedDocument(document_type="plan", summary="", source_route="text_pdf")
    result = cross_validate(fd=fd, plan=plan)
    assert result.status == "no_match"
    assert result.plan_match is None


def test_cross_validate_no_match_when_course_absent(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    for f in fd.fields:
        if f.key == "denumirea_disciplinei":
            f.value = "Curs Inexistent XYZ"

    result = cross_validate(fd=fd, plan=plan)
    assert result.status == "no_match"
    assert result.plan_match is None


def _set(fd: ExtractedDocument, key: str, value) -> None:
    for f in fd.fields:
        if f.key == key:
            f.value = value
            return
    fd.fields.append(type(fd.fields[0])(
        key=key, value=value, field_type="string", confidence="high",
    ))


def test_cross_validate_detects_year_mismatch(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    """FD says it's an Anul II course but the plan places it in Anul I."""
    _set(fd, "anul_de_studiu", "II")
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "year_mismatch" in codes
    assert result.plan_match is not None and result.plan_match.year == 1


def test_cross_validate_detects_semester_mismatch(fd: ExtractedDocument, plan: ExtractedDocument) -> None:
    """Plan has Analiză matematică in sem 1; FD claims sem 2."""
    _set(fd, "semestrul", 2)
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "semester_mismatch" in codes
    assert result.plan_match is not None and result.plan_match.semester == 1


def test_cross_validate_detects_categoria_formativa_mismatch(
    fd: ExtractedDocument, plan: ExtractedDocument
) -> None:
    """Plan classifies Analiză matematică as DC; force FD to DF."""
    _set(fd, "regimul_disciplinei_continut", "DF")
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "categoria_formativa_mismatch" in codes
    assert result.plan_match is not None and result.plan_match.categoria_formativa == "DC"


def test_cross_validate_detects_total_hours_mismatch(
    fd: ExtractedDocument, plan: ExtractedDocument
) -> None:
    """Plan sums to 125 ore for Analiză matematică (42+8+20+0+55).

    Wait — 'si' (study individual) is also in the sum; here we only sum
    instructional columns ai+at+tc+aa = 42+8+20+0 = 70. Force FD to a
    very different total to trigger the violation.
    """
    _set(fd, "total_ore_plan_invatamant", 999.0)
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "total_hours_mismatch" in codes
    assert result.plan_match is not None and result.plan_match.total_hours == 70


def test_cross_validate_detects_program_identity_mismatch(
    fd: ExtractedDocument, plan: ExtractedDocument
) -> None:
    """FD claims to belong to a totally different program than the PI."""
    _set(fd, "programul_de_studii_calificarea", "Pedagogia Învățământului Primar / Profesor")
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "program_identity_mismatch" in codes


def test_cross_validate_program_identity_tolerates_substring(
    fd: ExtractedDocument, plan: ExtractedDocument
) -> None:
    """FD's 'PROGRAM / Calificarea' suffix should not trigger a mismatch."""
    plan_program = next(
        f.value for f in plan.fields
        if f.key in {"programul_de_studii_universitare_de_licenta", "programul_de_studii"}
    )
    _set(fd, "programul_de_studii_calificarea", f"{plan_program} / Licențiat în Informatică")
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "program_identity_mismatch" not in codes


def test_cross_validate_batch_produces_coverage_report(plan: ExtractedDocument) -> None:
    """Batch mode aggregates per-FD results + lists missing courses."""
    from services.cross_doc_validator import cross_validate_batch

    # Build two synthetic FDs: one matches a real plan course, one doesn't.
    matching_fd = ExtractedDocument(
        document_type="FD",
        summary="",
        source_route="text_pdf",
        fields=[
            type_field := plan.fields[0].__class__(
                key="denumirea_disciplinei",
                value="Analiză matematică",
                field_type="string",
                confidence="high",
            ),
        ],
        tables=[],
    )
    bogus_fd = ExtractedDocument(
        document_type="FD",
        summary="",
        source_route="text_pdf",
        fields=[
            type_field.__class__(
                key="denumirea_disciplinei",
                value="Curs Inexistent ZZZ",
                field_type="string",
                confidence="high",
            ),
        ],
        tables=[],
    )

    report = cross_validate_batch(plan=plan, fds=[matching_fd, bogus_fd])

    assert report.fds_uploaded == 2
    assert report.total_plan_courses > 0
    assert report.unmatched_fds == 1
    assert report.aligned + report.inconsistent == 1  # the matching FD lands here
    assert "Analiză matematică" not in report.missing_fds  # we covered it
    assert len(report.entries) == 2


# ---------------------------------------------------------------------------
# Flexible PI column-format support (real Informatică Aplicată 2025-2028 layout)
# ---------------------------------------------------------------------------

from schemas.extraction import ExtractedField, ExtractedTable


def _ia_format_plan() -> ExtractedDocument:
    """Synthesize a minimal plan in the new IA per-week column format.

    Real layout headers: c1 (regimul-conținut DC/DF/DD/DS), c2 (DI/DO/DFc),
    s1_c, s1_s, s1_l, s1_p, s1_si, s1_pr, s1_v, s1_cr, s2_*.
    """
    return ExtractedDocument(
        document_type="plan",
        summary="",
        source_route="text_pdf",
        fields=[
            ExtractedField(key="universitatea", value="Universitatea Transilvania din Braşov",
                           field_type="string", confidence="high"),
            ExtractedField(key="facultatea", value="Facultatea de Matematică și Informatică",
                           field_type="string", confidence="high"),
            ExtractedField(key="domeniul_de_licenta", value="Informatică",
                           field_type="string", confidence="high"),
            ExtractedField(key="programul_de_studii_universitare_de_licenta",
                           value="INFORMATICĂ APLICATĂ",
                           field_type="string", confidence="high"),
        ],
        tables=[
            ExtractedTable(
                name="discipline_obligatorii_anul_i",
                headers=[
                    "nr_crt", "disciplina", "c1", "c2",
                    "s1_c", "s1_s", "s1_l", "s1_p", "s1_si", "s1_pr", "s1_v", "s1_cr",
                    "s2_c", "s2_s", "s2_l", "s2_p", "s2_si", "s2_pr", "s2_v", "s2_cr",
                ],
                rows=[
                    [
                        "1", "Analiză matematică", "DC", "DI",
                        "3", "2", "0", "0", "80", "0", "E", "5",
                        "", "", "", "", "", "", "", "",
                    ],
                ],
            ),
        ],
    )


def _ia_format_fd(**overrides) -> ExtractedDocument:
    fields = {
        "institutia_de_invatamant_superior": "Universitatea Transilvania din Brașov",
        "facultatea": "Matematică și Informatică",
        "domeniul_de_studii_de_licenta": "Informatică",
        "programul_de_studii_calificarea": "INFORMATICĂ APLICATĂ/ Licențiat în Informatică",
        "denumirea_disciplinei": "Analiză matematică",
        "anul_de_studiu": "I",
        "semestrul": 1,
        "tipul_de_evaluare": "E",
        "numarul_de_credite": 5.0,
        "regimul_disciplinei_continut": "DC",
        "ore_curs_pe_saptamana": 3.0,
        "ore_seminar_laborator_proiect_pe_saptamana": 2.0,
    }
    fields.update(overrides)
    return ExtractedDocument(
        document_type="FD",
        summary="",
        source_route="text_pdf",
        fields=[
            ExtractedField(key=k, value=v, field_type="string", confidence="high")
            for k, v in fields.items()
        ],
        tables=[],
    )


def test_cross_validate_handles_ia_per_week_columns() -> None:
    """The new C/S/L/P column layout must be extracted correctly."""
    plan = _ia_format_plan()
    fd = _ia_format_fd()
    result = cross_validate(fd=fd, plan=plan)
    assert result.plan_match is not None
    assert result.plan_match.credits == 5.0
    assert result.plan_match.evaluation_form == "E"
    assert result.plan_match.semester == 1
    assert result.plan_match.categoria_formativa == "DC"
    # Per-week sum: 3 + 2 + 0 + 0 = 5
    assert result.plan_match.weekly_hours == 5
    # No semestral hour columns in the IA layout
    assert result.plan_match.total_hours is None
    assert result.field_violations == []


def test_cross_validate_detects_weekly_hours_mismatch_ia_format() -> None:
    """FD declares a different weekly hour budget than the IA-format plan."""
    plan = _ia_format_plan()
    fd = _ia_format_fd(
        ore_curs_pe_saptamana=4.0,
        ore_seminar_laborator_proiect_pe_saptamana=4.0,
    )
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "weekly_hours_mismatch" in codes


def test_cross_validate_categoria_picks_c1_in_ia_format() -> None:
    """In IA layout c1=DC and c2=DI; the validator must pick the DC value."""
    plan = _ia_format_plan()
    fd = _ia_format_fd(regimul_disciplinei_continut="DF")
    result = cross_validate(fd=fd, plan=plan)
    codes = [v.code for v in result.field_violations]
    assert "categoria_formativa_mismatch" in codes
    assert result.plan_match is not None
    assert result.plan_match.categoria_formativa == "DC"
