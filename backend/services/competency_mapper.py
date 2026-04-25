"""Competency mapper (UC 2.2 — The Competency Mapper).

Compares the CP/CT codes referenced by a Fișa Disciplinei with the
official catalogue declared in the Plan de Învățământ, and optionally
asks Claude to recommend additional competences that fit the course
topic.

The deterministic part (declared / unknown / plan_only) requires no
LLM and is always returned. The AI recommendations are best-effort:
if Claude isn't configured or the call fails, ``recommended`` is empty
and the rest of the mapping is still useful.
"""
from __future__ import annotations

import os
import re
from typing import Iterable

from schemas.competency_mapping import (
    CompetencyEntry,
    CompetencyMapping,
    RecommendedCompetency,
)
from schemas.extraction import ExtractedDocument


_CODE_RE = re.compile(r"\b(CP|CT)\s*0?(\d+)\b", re.IGNORECASE)


def map_competencies(
    *,
    fd: ExtractedDocument,
    plan: ExtractedDocument,
    use_claude: bool | None = None,
) -> CompetencyMapping:
    """Build the side-by-side competence mapping for a single FD.

    ``use_claude`` defaults to ``True`` when ``ANTHROPIC_API_KEY`` is set
    in the environment; pass ``False`` to force the deterministic path.
    """
    catalog = _plan_catalog(plan)
    catalog_by_code = {entry.code: entry for entry in catalog}

    fd_codes = _fd_codes(fd)
    declared: list[CompetencyEntry] = []
    unknown: list[CompetencyEntry] = []
    for code in fd_codes:
        entry = catalog_by_code.get(code)
        if entry is not None:
            declared.append(entry)
        else:
            unknown.append(CompetencyEntry(code=code, title=None))

    declared_set = {e.code for e in declared}
    plan_only = [e for e in catalog if e.code not in declared_set]

    course_name = _field(fd, "denumirea_disciplinei")
    program = _field(plan, "programul_de_studii")

    if use_claude is None:
        use_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))

    recommended: list[RecommendedCompetency] = []
    if use_claude and plan_only and course_name:
        try:
            recommended = _recommend_with_claude(
                course_name=course_name,
                declared=declared,
                candidates=plan_only,
            )
        except Exception:
            # Recommendations are best-effort; never fail the whole mapping.
            recommended = []

    summary = _build_summary(course_name, declared, unknown, recommended)

    return CompetencyMapping(
        fd_course_name=course_name,
        plan_program=program,
        catalog=catalog,
        declared=declared,
        unknown=unknown,
        plan_only=plan_only,
        recommended=recommended,
        summary=summary,
    )


# ---------- deterministic helpers ----------

def _plan_catalog(plan: ExtractedDocument) -> list[CompetencyEntry]:
    """Read ``competente_catalog`` (added by the PI fast parser) into typed entries."""
    raw = _field(plan, "competente_catalog")
    entries: list[CompetencyEntry] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, str):
                continue
            # Stored as "CODE: title" — be lenient with separator whitespace.
            if ":" in item:
                code, title = item.split(":", 1)
                entries.append(
                    CompetencyEntry(code=code.strip(), title=title.strip() or None)
                )
            else:
                entries.append(CompetencyEntry(code=item.strip(), title=None))
    return entries


def _fd_codes(fd: ExtractedDocument) -> list[str]:
    """Pull deduped CP/CT codes from ``competente_referite`` (or any field)."""
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(values: Iterable[object]) -> None:
        for v in values:
            if v is None:
                continue
            if isinstance(v, list):
                _add(v)
                continue
            for prefix, num in _CODE_RE.findall(str(v)):
                code = f"{prefix.upper()}{int(num)}"
                if code not in seen:
                    seen.add(code)
                    ordered.append(code)

    _add(f.value for f in fd.fields)
    return ordered


def _field(doc: ExtractedDocument, key: str) -> object | None:
    for f in doc.fields:
        if f.key == key:
            return f.value
    return None


def _build_summary(
    course_name: str | None,
    declared: list[CompetencyEntry],
    unknown: list[CompetencyEntry],
    recommended: list[RecommendedCompetency],
) -> str:
    name = course_name or "FD"
    parts: list[str] = []
    parts.append(
        f"FD '{name}' declară {len(declared)} competențe valide din catalogul Planului."
    )
    if unknown:
        codes = ", ".join(e.code for e in unknown)
        parts.append(
            f"⚠ {len(unknown)} cod(uri) referite în FD nu există în Plan: {codes}."
        )
    if recommended:
        codes = ", ".join(r.code for r in recommended)
        parts.append(
            f"💡 AI sugerează {len(recommended)} competențe suplimentare: {codes}."
        )
    return " ".join(parts)


# ---------- Claude recommendation step ----------

_RECOMMEND_TOOL = {
    "name": "recommend_competencies",
    "description": (
        "Choose competence codes from the supplied catalogue that best match "
        "the given course title. Only return codes from the catalogue; do "
        "not invent new ones."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Competence code (e.g. CP3 or CT2).",
                        },
                        "rationale": {
                            "type": "string",
                            "description": (
                                "One short sentence in Romanian explaining "
                                "why this competence fits the course."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["code", "rationale", "confidence"],
                },
            }
        },
        "required": ["recommendations"],
    },
}


def _recommend_with_claude(
    *,
    course_name: str,
    declared: list[CompetencyEntry],
    candidates: list[CompetencyEntry],
) -> list[RecommendedCompetency]:
    """Ask Claude which catalogue competences fit the course but are missing.

    Imported lazily so the module stays importable without ``anthropic`` /
    network access; any failure falls back to no recommendations.
    """
    if not candidates:
        return []

    from services import claude_service  # noqa: WPS433 — lazy on purpose

    declared_lines = (
        "\n".join(f"- {e.code}: {e.title or '(fără descriere)'}" for e in declared)
        or "(nicio competență deja declarată)"
    )
    candidate_lines = "\n".join(
        f"- {e.code}: {e.title or '(fără descriere)'}" for e in candidates
    )
    candidate_codes = sorted({e.code for e in candidates})

    user_prompt = (
        "Ești un asistent academic care recomandă competențe pentru o fișă a "
        "disciplinei (FD).\n\n"
        f"Titlul disciplinei: {course_name}\n\n"
        "Competențe deja declarate în FD:\n"
        f"{declared_lines}\n\n"
        "Catalog disponibil (din Planul de Învățământ) — recomandă DOAR coduri "
        "din această listă:\n"
        f"{candidate_lines}\n\n"
        "Sarcina ta:\n"
        "- Recomandă cel mult 4 competențe suplimentare care se potrivesc cu "
        "titlul disciplinei.\n"
        "- Nu recomanda competențe deja declarate.\n"
        f"- Folosește exclusiv coduri din lista: {', '.join(candidate_codes)}.\n"
        "- Pentru fiecare recomandare oferă o motivație scurtă (1 frază) în limba română.\n"
        "- Dacă nicio competență din catalog nu se potrivește, returnează o listă goală."
    )

    payload = claude_service._call_claude_tool(  # noqa: SLF001
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=(
            "You are a careful academic curriculum reviewer. Reply only via "
            "the recommend_competencies tool, never as plain text."
        ),
        tool=_RECOMMEND_TOOL,
        tool_name="recommend_competencies",
    )

    raw = payload.get("recommendations") or []
    catalog_by_code = {e.code: e for e in candidates}
    out: list[RecommendedCompetency] = []
    declared_set = {e.code for e in declared}
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().upper()
        if not code or code in seen or code in declared_set:
            continue
        if code not in catalog_by_code:
            # Reject hallucinated codes outside the catalogue.
            continue
        seen.add(code)
        out.append(
            RecommendedCompetency(
                code=code,
                title=catalog_by_code[code].title,
                rationale=str(item.get("rationale") or "").strip()
                or "Se potrivește cu titlul disciplinei.",
                confidence=item.get("confidence") if item.get("confidence") in {"high", "medium", "low"} else "medium",
            )
        )
    return out
