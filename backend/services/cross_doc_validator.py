"""
Cross-document validator: verify a Fișa Disciplinei (FD) against the
Plan de Învățământ (the source of truth).

Three checks:
  1. Course identity — locate FD course in plan tables (exact then fuzzy)
  2. Administrative fields — credits + evaluation form must match plan row
  3. Competency references — every CPx / CTx code in FD must exist in plan
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from schemas.cross_validation import (
    CoverageReport,
    CrossValidationResult,
    FdCoverageEntry,
    PlanCourseMatch,
)
from schemas.extraction import ExtractedDocument, ExtractedTable
from schemas.template_validation import GuardViolation


# ---------- public API ----------

def cross_validate(
    *, fd: ExtractedDocument, plan: ExtractedDocument
) -> CrossValidationResult:
    fd_course = _get_field(fd, "denumirea_disciplinei")
    if not fd_course:
        return CrossValidationResult(
            status="no_match",
            summary="Fișa disciplinei nu conține câmpul 'denumirea_disciplinei'.",
        )

    fd_course_str = str(fd_course).strip()

    # Step 0: program identity — fail fast if FD belongs to a different program
    program_violations = _check_program_identity(fd, plan)

    plan_match = _find_course_in_plan(fd_course_str, plan)

    if plan_match is None:
        # Even if no course match, surface program mismatch — it explains why.
        summary = (
            f"Disciplina '{fd_course_str}' nu a fost găsită în Planul de "
            f"Învățământ. Verificați denumirea sau planul de referință."
        )
        if program_violations:
            summary = (
                "FD apare să aparțină unui alt program decât Planul de "
                "Învățământ furnizat:\n"
                + "\n".join(f"  • {v.message}" for v in program_violations)
                + f"\nDe asemenea, disciplina '{fd_course_str}' nu a fost găsită."
            )
        return CrossValidationResult(
            status="no_match",
            fd_course_name=fd_course_str,
            field_violations=program_violations,
            summary=summary,
        )

    field_violations = program_violations + _check_field_alignment(fd, plan_match)
    competency_violations = _check_competency_references(fd, plan)

    status = "valid" if not (field_violations or competency_violations) else "invalid"
    summary = _build_summary(fd_course_str, plan_match, field_violations, competency_violations)

    return CrossValidationResult(
        status=status,
        fd_course_name=fd_course_str,
        plan_match=plan_match,
        field_violations=field_violations,
        competency_violations=competency_violations,
        summary=summary,
    )


# ---------- program identity ----------

# (FD field key, list of acceptable PI field keys, human label)
_PROGRAM_IDENTITY_PAIRS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "institutia_de_invatamant_superior",
        ("universitatea", "institutia_de_invatamant_superior"),
        "instituția",
    ),
    (
        "facultatea",
        ("facultatea",),
        "facultatea",
    ),
    (
        "domeniul_de_studii_de_licenta",
        ("domeniul_de_licenta", "domeniul_de_studii_de_licenta"),
        "domeniul de licență",
    ),
    (
        "programul_de_studii_calificarea",
        (
            "programul_de_studii_universitare_de_licenta",
            "programul_de_studii_calificarea",
            "programul_de_studii",
        ),
        "programul de studii",
    ),
)


def _program_identity_compatible(fd_value: str, plan_value: str) -> bool:
    fd_norm = _normalize(fd_value)
    plan_norm = _normalize(plan_value)
    if not fd_norm or not plan_norm:
        return True  # missing data — don't accuse
    if fd_norm == plan_norm:
        return True
    # Substring tolerance: FD often says 'INFORMATICĂ APLICATĂ / Licențiat în Informatică'
    # while PI says 'INFORMATICĂ APLICATĂ'
    if fd_norm in plan_norm or plan_norm in fd_norm:
        return True
    # Token overlap fallback (≥2/3 of shorter set covered)
    fd_tokens = set(fd_norm.split())
    plan_tokens = set(plan_norm.split())
    if not fd_tokens or not plan_tokens:
        return False
    overlap = len(fd_tokens & plan_tokens)
    return overlap / min(len(fd_tokens), len(plan_tokens)) >= 0.66


def _check_program_identity(
    fd: ExtractedDocument, plan: ExtractedDocument
) -> list[GuardViolation]:
    violations: list[GuardViolation] = []
    for fd_key, plan_keys, label in _PROGRAM_IDENTITY_PAIRS:
        fd_value = _get_field(fd, fd_key)
        if fd_value is None:
            continue
        plan_value = next(
            (_get_field(plan, k) for k in plan_keys if _get_field(plan, k) is not None),
            None,
        )
        if plan_value is None:
            continue
        if not _program_identity_compatible(str(fd_value), str(plan_value)):
            violations.append(GuardViolation(
                code="program_identity_mismatch",
                field=fd_key,
                message=(
                    f"FD declară {label} '{fd_value}', dar Planul de Învățământ "
                    f"este pentru '{plan_value}'."
                ),
            ))
    return violations


# ---------- field lookup ----------

def _get_field(doc: ExtractedDocument, key: str) -> Any:
    for f in doc.fields:
        if f.key == key:
            return f.value
    return None


def _iter_fields(doc: ExtractedDocument):
    for f in doc.fields:
        yield f.key, f.value


# ---------- name normalization ----------

def _normalize(name: str) -> str:
    """Lowercase + strip diacritics + collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name)
    no_diacritics = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_diacritics.strip().lower())


# ---------- course lookup in plan ----------

_PLAN_COURSE_TABLE_PATTERNS = (
    "discipline_obligatorii",
    "discipline_optionale",
    "discipline_facultative",
)


def _plan_course_tables(plan: ExtractedDocument) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []
    for t in plan.tables:
        name = (t.name or "").lower()
        if any(p in name for p in _PLAN_COURSE_TABLE_PATTERNS):
            tables.append(t)
    return tables


def _row_to_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    return {h: (row[i] if i < len(row) else "") for i, h in enumerate(headers)}


def _extract_year_from_table_name(table_name: str) -> int | None:
    name = table_name.lower()
    if "anul_iii" in name or "anul_3" in name:
        return 3
    if "anul_ii" in name or "anul_2" in name:
        return 2
    if "anul_i" in name or "anul_1" in name:
        return 1
    return None


def _find_course_in_plan(
    fd_course: str, plan: ExtractedDocument
) -> PlanCourseMatch | None:
    target = _normalize(fd_course)
    if not target:
        return None

    best: PlanCourseMatch | None = None
    best_score = 0.0

    for table in _plan_course_tables(plan):
        year = _extract_year_from_table_name(table.name)
        for row in table.rows:
            row_dict = _row_to_dict(table.headers, row)
            disc_name = row_dict.get("disciplina") or row_dict.get("denumirea_disciplinei")
            if not disc_name:
                continue

            normalized = _normalize(disc_name)
            score = _name_match_score(target, normalized)
            if score < 0.6:
                continue

            credits, eval_form, semester, total_hours, weekly_hours = _extract_admin_fields(row_dict)
            categoria = _extract_categoria(row_dict)

            candidate = PlanCourseMatch(
                course_name=disc_name,
                course_code=row_dict.get("codul_disciplinei") or None,
                year=year,
                semester=semester,
                credits=credits,
                evaluation_form=eval_form,
                categoria_formativa=categoria,
                total_hours=total_hours,
                weekly_hours=weekly_hours,
                match_confidence="exact" if score >= 0.99 else "fuzzy",
            )

            if score > best_score:
                best = candidate
                best_score = score

    return best


def _name_match_score(target: str, candidate: str) -> float:
    if not candidate:
        return 0.0
    if target == candidate:
        return 1.0
    if target in candidate or candidate in target:
        # Weight by how much the shorter covers the longer
        shorter, longer = sorted([target, candidate], key=len)
        return len(shorter) / len(longer)
    # token overlap
    t_tokens = set(target.split())
    c_tokens = set(candidate.split())
    if not t_tokens or not c_tokens:
        return 0.0
    overlap = len(t_tokens & c_tokens)
    return overlap / max(len(t_tokens), len(c_tokens))


def _extract_admin_fields(
    row: dict[str, str],
) -> tuple[float | None, str | None, int | None, int | None, int | None]:
    """Return (credits, evaluation_form, semester, semestral_hours, weekly_hours).

    Plan tables encode each course twice: sem-1 columns (s1_*) and sem-2
    columns (s2_*). One pair is empty.

    Two real-world layouts are supported:
      * Existing legacy plans use semestral hour columns ``ai/at/tc/aa``.
        Their sum is returned as ``semestral_hours``.
      * Newer plans (e.g. Informatică Aplicată 2025-2028) use per-week
        columns ``c/s/l/p`` (curs/seminar/laborator/proiect) plus optional
        ``pr`` (project). Their sum is returned as ``weekly_hours``.
    Both can be present at the same time.
    """
    credit_keys = ("cr", "credits", "credite")
    eval_keys = ("fv", "v", "evaluare")
    weekly_hour_keys = ("c", "s", "l", "p", "pr")
    semestral_hour_keys = ("ai", "at", "tc", "aa")

    for sem in (1, 2):
        cr_raw = _first_value(row, [f"s{sem}_{k}" for k in credit_keys])
        fv_raw = _first_value(row, [f"s{sem}_{k}" for k in eval_keys])
        if not (cr_raw or fv_raw):
            continue

        credits = _safe_float(cr_raw)

        semestral_total = 0
        any_semestral = False
        for hkey in semestral_hour_keys:
            v = _safe_int(row.get(f"s{sem}_{hkey}", ""))
            if v is not None:
                semestral_total += v
                any_semestral = True

        weekly_total = 0
        any_weekly = False
        for hkey in weekly_hour_keys:
            v = _safe_int(row.get(f"s{sem}_{hkey}", ""))
            if v is not None:
                weekly_total += v
                any_weekly = True

        return (
            credits,
            (fv_raw or None),
            sem,
            (semestral_total if any_semestral else None),
            (weekly_total if any_weekly else None),
        )
    return None, None, None, None, None


def _first_value(row: dict[str, str], keys: list[str]) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            return v
    return ""


def _safe_float(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(str(raw).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _safe_int(raw: str) -> int | None:
    f = _safe_float(raw)
    if f is None:
        return None
    return int(f)


_CATEGORIA_RE = re.compile(r"^\s*(D[CFDS])\b", re.IGNORECASE)


def _extract_categoria(row: dict[str, str]) -> str | None:
    """Pick the column (c1/c2/categoria) whose value matches DC/DF/DD/DS."""
    for key in ("c1", "c2", "categoria", "categoria_formativa"):
        raw = (row.get(key) or "").strip()
        if not raw:
            continue
        m = _CATEGORIA_RE.match(raw)
        if m:
            return m.group(1).upper()
    return None


# ---------- field alignment ----------

def _check_field_alignment(
    fd: ExtractedDocument, match: PlanCourseMatch
) -> list[GuardViolation]:
    violations: list[GuardViolation] = []

    # Credits
    fd_credits = _to_float(_get_field(fd, "numarul_de_credite"))
    if (
        fd_credits is not None
        and match.credits is not None
        and abs(fd_credits - match.credits) > 0.01
    ):
        violations.append(GuardViolation(
            code="credits_mismatch",
            field="numarul_de_credite",
            message=(
                f"FD declară {fd_credits:g} credite, dar Planul de Învățământ "
                f"specifică {match.credits:g} credite pentru "
                f"'{match.course_name}'."
            ),
        ))

    # Evaluation form
    fd_eval = _normalize_eval_form(_get_field(fd, "tipul_de_evaluare"))
    plan_eval = _normalize_eval_form(match.evaluation_form)
    if fd_eval and plan_eval and fd_eval != plan_eval:
        violations.append(GuardViolation(
            code="evaluation_form_mismatch",
            field="tipul_de_evaluare",
            message=(
                f"FD declară forma de evaluare '{fd_eval}', dar Planul de "
                f"Învățământ specifică '{plan_eval}' pentru "
                f"'{match.course_name}'."
            ),
        ))

    # Year of study
    fd_year = _normalize_year(_get_field(fd, "anul_de_studiu"))
    if fd_year is not None and match.year is not None and fd_year != match.year:
        violations.append(GuardViolation(
            code="year_mismatch",
            field="anul_de_studiu",
            message=(
                f"FD declară anul de studiu {_year_to_roman(fd_year)}, dar "
                f"Planul plasează '{match.course_name}' în anul "
                f"{_year_to_roman(match.year)}."
            ),
        ))

    # Semester
    # FDs at some faculties number semesters globally (1..6 across the program)
    # while the Plan numbers them per-year (1..2). Normalize the FD value to
    # per-year before comparing to avoid false positives.
    fd_sem_raw = _normalize_semester(_get_field(fd, "semestrul"))
    fd_sem = _to_per_year_semester(fd_sem_raw)
    if fd_sem is not None and match.semester is not None and fd_sem != match.semester:
        # When the FD uses global numbering (e.g. "5" for year 3 sem 1) the
        # raw value alone is confusing next to the plan's per-year value.
        # Mention both so the professor can spot the discrepancy.
        if fd_sem_raw != fd_sem:
            fd_sem_label = f"{fd_sem} (în FD scris ca semestrul global {fd_sem_raw})"
        else:
            fd_sem_label = str(fd_sem)
        violations.append(GuardViolation(
            code="semester_mismatch",
            field="semestrul",
            message=(
                f"FD declară semestrul {fd_sem_label}, dar Planul plasează "
                f"'{match.course_name}' în semestrul {match.semester}."
            ),
        ))

    # Categoria formativă (DC/DF/DD/DS)
    fd_categ = _normalize_categoria(_get_field(fd, "regimul_disciplinei_continut"))
    plan_categ = _normalize_categoria(match.categoria_formativa)
    if fd_categ and plan_categ and fd_categ != plan_categ:
        violations.append(GuardViolation(
            code="categoria_formativa_mismatch",
            field="regimul_disciplinei_continut",
            message=(
                f"FD declară categoria formativă '{fd_categ}', dar Planul "
                f"specifică '{plan_categ}' pentru '{match.course_name}'."
            ),
        ))

    # Total ore (semestral)
    fd_total_hours = _to_float(_get_field(fd, "total_ore_plan_invatamant"))
    if (
        fd_total_hours is not None
        and match.total_hours is not None
        and abs(fd_total_hours - match.total_hours) > 0.5
    ):
        violations.append(GuardViolation(
            code="total_hours_mismatch",
            field="total_ore_plan_invatamant",
            message=(
                f"FD declară {fd_total_hours:g} ore total/semestru, dar "
                f"Planul însumează {match.total_hours} ore pentru "
                f"'{match.course_name}'."
            ),
        ))

    # Weekly hours (per saptamana) — used by newer plan layouts
    fd_weekly = _fd_weekly_hours(fd)
    if (
        fd_weekly is not None
        and match.weekly_hours is not None
        and abs(fd_weekly - match.weekly_hours) > 0.5
    ):
        violations.append(GuardViolation(
            code="weekly_hours_mismatch",
            field="numar_ore_pe_saptamana_total",
            message=(
                f"FD declară {fd_weekly:g} ore/săptămână, dar Planul însumează "
                f"{match.weekly_hours} ore/săptămână (C+S+L+P) pentru "
                f"'{match.course_name}'."
            ),
        ))

    return violations


def _fd_weekly_hours(fd: ExtractedDocument) -> float | None:
    """FD weekly hours: prefer explicit total, else sum components."""
    total = _to_float(_get_field(fd, "numar_ore_pe_saptamana_total"))
    if total is not None:
        return total
    components = [
        _to_float(_get_field(fd, "ore_curs_pe_saptamana")),
        _to_float(_get_field(fd, "ore_seminar_laborator_proiect_pe_saptamana")),
    ]
    present = [c for c in components if c is not None]
    if not present:
        return None
    return sum(present)


_ROMAN_TO_INT = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}
_INT_TO_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}


def _normalize_year(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip().lower().replace("anul", "").strip()
    if not s:
        return None
    if s in _ROMAN_TO_INT:
        return _ROMAN_TO_INT[s]
    try:
        return int(float(s))
    except ValueError:
        return None


def _year_to_roman(value: int) -> str:
    return _INT_TO_ROMAN.get(value, str(value))


def _normalize_semester(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip().lower().replace("semestrul", "").strip()
    if not s:
        return None
    if s in _ROMAN_TO_INT:
        return _ROMAN_TO_INT[s]
    try:
        return int(float(s))
    except ValueError:
        return None


def _to_per_year_semester(sem: int | None) -> int | None:
    """Map a possibly-global semester (1..6) to a per-year semester (1..2).

    Some FDs number semesters globally across the program (e.g. semester 5
    means year 3, sem 1) while the Plan numbers them per-year. This helper
    folds any value > 2 down to {1, 2} so the comparison is consistent.
    """
    if sem is None:
        return None
    if sem <= 2:
        return sem
    return ((sem - 1) % 2) + 1


def _normalize_categoria(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s:
        return None
    # Take only the first 2-3 letter code if there's a description suffix
    m = re.match(r"\b(D[CFDS])\b", s)
    return m.group(1) if m else s


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_EVAL_NORMALIZATIONS = {
    "e": "E",
    "examen": "E",
    "ex": "E",
    "c": "C",
    "colocviu": "C",
    "col": "C",
    "v": "V",
    "verificare": "V",
}


def _normalize_eval_form(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    return _EVAL_NORMALIZATIONS.get(s, s.upper())


# ---------- competency references ----------

_COMPETENCY_RE = re.compile(r"\b(CP|CT)\s*0?(\d+)\b", re.IGNORECASE)


def _extract_competency_codes(values: Iterable[Any]) -> set[str]:
    codes: set[str] = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, list):
            codes.update(_extract_competency_codes(v))
            continue
        for prefix, num in _COMPETENCY_RE.findall(str(v)):
            codes.add(f"{prefix.upper()}{int(num)}")
    return codes


def _plan_competency_codes(plan: ExtractedDocument) -> set[str]:
    codes: set[str] = set()

    # From dedicated competency tables: column 'cod_competenta'
    for t in plan.tables:
        if "competente" not in (t.name or "").lower():
            continue
        if "cod_competenta" not in t.headers:
            continue
        idx = t.headers.index("cod_competenta")
        for row in t.rows:
            if idx < len(row) and row[idx]:
                codes.update(_extract_competency_codes([row[idx]]))

    # Fallback: scan all field values too
    codes.update(_extract_competency_codes(v for _, v in _iter_fields(plan)))
    return codes


def _check_competency_references(
    fd: ExtractedDocument, plan: ExtractedDocument
) -> list[GuardViolation]:
    fd_codes = _extract_competency_codes(v for _, v in _iter_fields(fd))
    if not fd_codes:
        return []

    plan_codes = _plan_competency_codes(plan)
    if not plan_codes:
        # Plan has no extractable competencies — can't validate, skip silently
        return []

    missing = sorted(fd_codes - plan_codes)
    if not missing:
        return []

    return [
        GuardViolation(
            code="competency_not_in_plan",
            fields=missing,
            message=(
                f"Codurile de competență {', '.join(missing)} sunt menționate "
                f"în FD, dar nu există în Planul de Învățământ."
            ),
        )
    ]


# ---------- summary ----------

def _build_summary(
    fd_course: str,
    match: PlanCourseMatch,
    field_violations: list[GuardViolation],
    competency_violations: list[GuardViolation],
) -> str:
    if not field_violations and not competency_violations:
        return (
            f"FD pentru '{fd_course}' este aliniată cu Planul de Învățământ "
            f"(potrivire: {match.match_confidence})."
        )

    parts = [f"FD pentru '{fd_course}' are inconsistențe față de Plan:"]
    for v in field_violations:
        parts.append(f"  • {v.message}")
    for v in competency_violations:
        parts.append(f"  • {v.message}")
    return "\n".join(parts)


# ---------- batch / coverage ----------

def _enumerate_plan_courses(plan: ExtractedDocument) -> list[str]:
    names: list[str] = []
    for table in _plan_course_tables(plan):
        for row in table.rows:
            row_dict = _row_to_dict(table.headers, row)
            disc_name = row_dict.get("disciplina") or row_dict.get("denumirea_disciplinei")
            if disc_name:
                names.append(disc_name.strip())
    return names


def cross_validate_batch(
    *, plan: ExtractedDocument, fds: list[ExtractedDocument]
) -> CoverageReport:
    """Validate many FDs against a single Plan and produce a coverage report."""
    plan_courses = _enumerate_plan_courses(plan)
    matched_normalized: set[str] = set()

    entries: list[FdCoverageEntry] = []
    aligned = 0
    inconsistent = 0
    unmatched = 0

    for fd in fds:
        result = cross_validate(fd=fd, plan=plan)
        entries.append(FdCoverageEntry(fd_course_name=result.fd_course_name, result=result))
        if result.status == "valid":
            aligned += 1
        elif result.status == "invalid":
            inconsistent += 1
        else:
            unmatched += 1
        if result.plan_match is not None:
            matched_normalized.add(_normalize(result.plan_match.course_name))

    missing = [
        name for name in plan_courses
        if _normalize(name) not in matched_normalized
    ]

    return CoverageReport(
        total_plan_courses=len(plan_courses),
        fds_uploaded=len(fds),
        aligned=aligned,
        inconsistent=inconsistent,
        unmatched_fds=unmatched,
        missing_fds=missing,
        entries=entries,
    )
