"""UC 1.2 — Numeric consistency checks for a Fișa Disciplinei.

Validates internal arithmetic of a parsed FD: that weekly hours add up,
that the semester totals are congruent with weekly × 14, that totals
match plan + studiu individual, that credits fall in a reasonable range,
and that ECTS hours roughly match credits × 25.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from schemas.extraction import ExtractedDocument


Severity = Literal["error", "warning", "info"]


class NumericIssue(BaseModel):
    severity: Severity
    code: str
    message: str
    expected: float | None = None
    actual: float | None = None
    delta: float | None = None
    fields: list[str] = []


class NumericConsistencyReport(BaseModel):
    issues: list[NumericIssue]
    passed: int
    total_checks: int
    summary: str


# --- helpers ---------------------------------------------------------------


def _num(fd: ExtractedDocument, key: str) -> float | None:
    for f in fd.fields:
        if f.key == key:
            v = f.value
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                try:
                    return float(v.replace(",", "."))
                except ValueError:
                    return None
    return None


def _approx(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


# --- checks ----------------------------------------------------------------


def check_fd_numeric_consistency(fd: ExtractedDocument) -> NumericConsistencyReport:
    """Run all numeric consistency checks on a parsed FD."""
    issues: list[NumericIssue] = []
    total = 0

    curs_w = _num(fd, "ore_curs_pe_saptamana")
    slp_w = _num(fd, "ore_seminar_laborator_proiect_pe_saptamana")
    total_w = _num(fd, "numar_ore_pe_saptamana_total")
    total_curs = _num(fd, "total_ore_curs")
    total_slp = _num(fd, "total_ore_seminar_laborator_proiect")
    total_plan = _num(fd, "total_ore_plan_invatamant")
    total_studiu = _num(fd, "total_ore_studiu_individual")
    total_sem = _num(fd, "total_ore_pe_semestru")
    credite = _num(fd, "numarul_de_credite")

    # Check 1: weekly hours add up
    if curs_w is not None and slp_w is not None and total_w is not None:
        total += 1
        expected = curs_w + slp_w
        if not _approx(expected, total_w, 0):
            issues.append(NumericIssue(
                severity="error",
                code="weekly_sum_mismatch",
                message=(
                    f"Suma orelor săptămânale (curs {curs_w:.0f} + "
                    f"S/L/P {slp_w:.0f} = {expected:.0f}) nu corespunde "
                    f"cu totalul declarat ({total_w:.0f})."
                ),
                expected=expected,
                actual=total_w,
                delta=total_w - expected,
                fields=[
                    "ore_curs_pe_saptamana",
                    "ore_seminar_laborator_proiect_pe_saptamana",
                    "numar_ore_pe_saptamana_total",
                ],
            ))

    # Check 2: semester totals add up
    if total_curs is not None and total_slp is not None and total_plan is not None:
        total += 1
        expected = total_curs + total_slp
        if not _approx(expected, total_plan, 0):
            issues.append(NumericIssue(
                severity="error",
                code="semester_total_mismatch",
                message=(
                    f"Suma orelor pe semestru (curs {total_curs:.0f} + "
                    f"S/L/P {total_slp:.0f} = {expected:.0f}) nu corespunde "
                    f"cu totalul declarat în planul de învățământ ({total_plan:.0f})."
                ),
                expected=expected,
                actual=total_plan,
                delta=total_plan - expected,
                fields=[
                    "total_ore_curs",
                    "total_ore_seminar_laborator_proiect",
                    "total_ore_plan_invatamant",
                ],
            ))

    # Check 3: weekly × 14 ≈ total semester didactic hours
    if total_w is not None and total_plan is not None:
        total += 1
        expected = total_w * 14
        if not _approx(expected, total_plan, 1):
            issues.append(NumericIssue(
                severity="warning",
                code="weekly_times_weeks_mismatch",
                message=(
                    f"Total orelor pe semestru ({total_plan:.0f}) nu corespunde "
                    f"cu {total_w:.0f} ore/săptămână × 14 săptămâni = "
                    f"{expected:.0f}."
                ),
                expected=expected,
                actual=total_plan,
                delta=total_plan - expected,
                fields=["numar_ore_pe_saptamana_total", "total_ore_plan_invatamant"],
            ))

    # Check 4: total semestru = total didactic + studiu individual
    if total_plan is not None and total_studiu is not None and total_sem is not None:
        total += 1
        expected = total_plan + total_studiu
        if not _approx(expected, total_sem, 0):
            issues.append(NumericIssue(
                severity="error",
                code="semester_grand_total_mismatch",
                message=(
                    f"Total ore pe semestru ({total_sem:.0f}) nu corespunde "
                    f"cu activitate didactică ({total_plan:.0f}) + studiu "
                    f"individual ({total_studiu:.0f}) = {expected:.0f}."
                ),
                expected=expected,
                actual=total_sem,
                delta=total_sem - expected,
                fields=[
                    "total_ore_plan_invatamant",
                    "total_ore_studiu_individual",
                    "total_ore_pe_semestru",
                ],
            ))

    # Check 5: credits in plausible range [1, 30]
    if credite is not None:
        total += 1
        if credite < 1 or credite > 30:
            issues.append(NumericIssue(
                severity="error",
                code="credits_out_of_range",
                message=(
                    f"Numărul de credite ({credite:.0f}) este în afara "
                    f"intervalului uzual [1, 30]."
                ),
                actual=credite,
                fields=["numarul_de_credite"],
            ))

    # Check 6: ECTS — total_sem ≈ credite × 25 (tolerate ±5 h/credit)
    if credite is not None and total_sem is not None and credite > 0:
        total += 1
        expected = credite * 25
        tol = max(5.0 * credite, 5.0)
        if not _approx(expected, total_sem, tol):
            issues.append(NumericIssue(
                severity="warning",
                code="ects_hours_mismatch",
                message=(
                    f"Total ore pe semestru ({total_sem:.0f}) nu respectă "
                    f"convenția ECTS de ~25 h/credit: pentru {credite:.0f} "
                    f"credite se așteaptă ≈{expected:.0f} ore (toleranță ±{tol:.0f})."
                ),
                expected=expected,
                actual=total_sem,
                delta=total_sem - expected,
                fields=["numarul_de_credite", "total_ore_pe_semestru"],
            ))

    passed = total - len(issues)
    if total == 0:
        summary = "Nu s-au putut efectua verificări — câmpuri numerice insuficiente."
    elif not issues:
        summary = f"Toate cele {total} verificări numerice au trecut."
    else:
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        summary = (
            f"{passed}/{total} verificări trecute "
            f"({errors} erori, {warnings} avertismente)."
        )

    return NumericConsistencyReport(
        issues=issues,
        passed=passed,
        total_checks=total,
        summary=summary,
    )
