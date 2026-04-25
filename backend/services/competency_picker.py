"""UC 1.4 — Per-course CP/CT picker.

Given a parsed Plan and one course (name, year, semester, hours, type),
selects 1-2 Competențe Profesionale (CP) and 1-2 Competențe Transversale
(CT) from the Plan's catalog, plus the verbatim R.Î. bullets associated
with each picked competency.

Strict guard: Claude can only return IDs that exist in the catalog. Any
unknown ID is dropped server-side. R.Î. bullet text is copied verbatim
from the Plan — never regenerated.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable

from schemas.extraction import ExtractedDocument


_CP_RE = re.compile(r"^\s*(CP\s*\d+)\s*\.?\s*(.*)$", re.IGNORECASE)
_CT_RE = re.compile(r"^\s*(CT\s*\d+)\s*\.?\s*(.*)$", re.IGNORECASE)
_RI_RE = re.compile(r"^\s*R[ÎI]\s*\.?\s*(\d+)\s*\.\s*(\d+)\s*\.?\s*(.*)$", re.IGNORECASE)


@dataclass
class CompetencyEntry:
    code: str           # e.g. "CP1", "CT2"
    title: str
    ri_bullets: list[str] = field(default_factory=list)


@dataclass
class PlanCompetencies:
    cp: dict[str, CompetencyEntry]
    ct: dict[str, CompetencyEntry]

    def is_empty(self) -> bool:
        return not self.cp and not self.ct


@dataclass
class CompetencyPick:
    cp: list[CompetencyEntry] = field(default_factory=list)
    ct: list[CompetencyEntry] = field(default_factory=list)
    rationale: dict[str, str] = field(default_factory=dict)  # code -> reason
    ai_used: bool = False
    fallback_reason: str | None = None


def parse_plan_competencies(plan: ExtractedDocument) -> PlanCompetencies:
    """Read CP/CT + R.Î. fields from a parsed Plan.

    Supports two upstream formats:
      * AI-parsed plans (cached mock JSON) — separate ``competente_profesionale``
        / ``competente_transversale`` / ``rezultate_invatare_*`` list fields.
      * Live PI fast-parser (`pi_fast_parser.py`) — single ``competente_catalog``
        field containing ``[{"code": "CP1", "title": "..."}, ...]``.
    """
    cp_raw = _list_field(plan, "competente_profesionale")
    ct_raw = _list_field(plan, "competente_transversale")
    ri_prof = _list_field(plan, "rezultate_invatare_profesionale")
    ri_trans = _list_field(plan, "rezultate_invatare_transversale")

    cp = _parse_competence_block(cp_raw, _CP_RE, "CP")
    ct = _parse_competence_block(ct_raw, _CT_RE, "CT")

    _attach_ri(cp, ri_prof, "CP")
    _attach_ri(ct, ri_trans, "CT")

    # Fallback: live PI parser stores everything in ``competente_catalog``
    # as ``["CODE: title", ...]`` strings (no R.Î. info).
    if not cp and not ct:
        for raw in _list_field(plan, "competente_catalog"):
            text = str(raw).strip()
            if ":" not in text:
                continue
            code_part, title = text.split(":", 1)
            code = _normalize_code(code_part)
            title = title.strip()
            if not code or not title:
                continue
            target = cp if code.startswith("CP") else ct if code.startswith("CT") else None
            if target is None or code in target:
                continue
            target[code] = CompetencyEntry(code=code, title=title)

    return PlanCompetencies(cp=cp, ct=ct)


def pick_for_course(
    *,
    course_name: str,
    course_meta: dict,
    plan_competencies: PlanCompetencies,
    use_claude: bool | None = None,
    max_cp: int = 2,
    max_ct: int = 2,
) -> CompetencyPick:
    """Pick CP/CT for one course. Falls back to no-pick if catalog empty."""
    if plan_competencies.is_empty():
        return CompetencyPick(fallback_reason="Catalog de competențe absent în Plan.")

    if use_claude is None:
        use_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if not use_claude:
        return CompetencyPick(
            fallback_reason="AI dezactivat — selecție competențe omisă (alegeți manual).",
        )

    try:
        return _pick_with_claude(
            course_name=course_name,
            course_meta=course_meta,
            plan_competencies=plan_competencies,
            max_cp=max_cp,
            max_ct=max_ct,
        )
    except Exception as exc:  # noqa: BLE001 — AI is optional, never blocks the draft
        return CompetencyPick(
            fallback_reason=f"Eroare la apelul AI ({type(exc).__name__}): {exc}",
        )


# ---------- Claude integration with closed-set guard ----------

_PICK_TOOL = {
    "name": "select_course_competencies",
    "description": (
        "Select the most relevant CP and CT codes for the given course "
        "from the supplied catalog. ONLY return codes from the catalog; "
        "unknown codes will be rejected."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_cp": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Catalog CP code (CP1, CP2, ...)"},
                        "rationale": {"type": "string", "description": "One short Romanian sentence."},
                    },
                    "required": ["code", "rationale"],
                },
            },
            "selected_ct": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Catalog CT code (CT1, CT2, ...)"},
                        "rationale": {"type": "string", "description": "One short Romanian sentence."},
                    },
                    "required": ["code", "rationale"],
                },
            },
        },
        "required": ["selected_cp", "selected_ct"],
    },
}


def _pick_with_claude(
    *,
    course_name: str,
    course_meta: dict,
    plan_competencies: PlanCompetencies,
    max_cp: int,
    max_ct: int,
) -> CompetencyPick:
    from services import claude_service  # noqa: WPS433 — lazy import

    cp_lines = "\n".join(
        f"- {e.code}: {e.title}" for e in plan_competencies.cp.values()
    ) or "(niciuna)"
    ct_lines = "\n".join(
        f"- {e.code}: {e.title}" for e in plan_competencies.ct.values()
    ) or "(niciuna)"
    cp_codes = sorted(plan_competencies.cp.keys())
    ct_codes = sorted(plan_competencies.ct.keys())

    meta_lines = []
    if course_meta.get("year"):
        meta_lines.append(f"An studiu: {course_meta['year']}")
    if course_meta.get("semester"):
        meta_lines.append(f"Semestru: {course_meta['semester']}")
    if course_meta.get("credits") is not None:
        meta_lines.append(f"Credite: {course_meta['credits']}")
    if course_meta.get("evaluation_form"):
        meta_lines.append(f"Evaluare: {course_meta['evaluation_form']}")
    if course_meta.get("categoria_formativa"):
        meta_lines.append(f"Categorie: {course_meta['categoria_formativa']}")
    if course_meta.get("weekly_hours"):
        meta_lines.append(f"Ore săptămânale (C/S/L/P): {course_meta['weekly_hours']}")

    user_prompt = (
        "Sarcină: alege competențele profesionale (CP) și transversale (CT) "
        "cele mai relevante pentru disciplina de mai jos, din catalogul Planului.\n\n"
        f"Disciplină: {course_name}\n"
        + ("\n".join(meta_lines) + "\n\n" if meta_lines else "\n")
        + f"Catalog CP disponibile:\n{cp_lines}\n\n"
        f"Catalog CT disponibile:\n{ct_lines}\n\n"
        f"Reguli stricte:\n"
        f"- Alege MAXIM {max_cp} CP-uri și MAXIM {max_ct} CT-uri.\n"
        f"- Folosește EXCLUSIV coduri din: CP={', '.join(cp_codes) or '-'} ; CT={', '.join(ct_codes) or '-'}.\n"
        "- Nu inventa coduri noi.\n"
        "- Pentru fiecare alegere, oferă o motivație de o singură frază în limba română."
    )

    payload = claude_service._call_claude_tool(  # noqa: SLF001
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=(
            "You are an academic curriculum specialist. Reply ONLY via the "
            "select_course_competencies tool, never as plain text."
        ),
        tool=_PICK_TOOL,
        tool_name="select_course_competencies",
    )

    pick = CompetencyPick(ai_used=True)
    pick.cp, pick.rationale = _validate_picks(
        raw=payload.get("selected_cp") or [],
        catalog=plan_competencies.cp,
        max_n=max_cp,
        rationale=pick.rationale,
    )
    pick.ct, pick.rationale = _validate_picks(
        raw=payload.get("selected_ct") or [],
        catalog=plan_competencies.ct,
        max_n=max_ct,
        rationale=pick.rationale,
    )
    return pick


def _validate_picks(
    *,
    raw: list,
    catalog: dict[str, CompetencyEntry],
    max_n: int,
    rationale: dict[str, str],
) -> tuple[list[CompetencyEntry], dict[str, str]]:
    out: list[CompetencyEntry] = []
    seen: set[str] = set()
    for item in raw:
        if len(out) >= max_n:
            break
        if not isinstance(item, dict):
            continue
        code = _normalize_code(str(item.get("code") or ""))
        if not code or code in seen:
            continue
        if code not in catalog:
            # Reject hallucinated IDs.
            continue
        seen.add(code)
        out.append(catalog[code])
        reason = str(item.get("rationale") or "").strip()
        if reason:
            rationale[code] = reason
    return out, rationale


# ---------- parsing helpers ----------

def _list_field(doc: ExtractedDocument, key: str) -> list[str]:
    for f in doc.fields:
        if f.key == key and isinstance(f.value, list):
            return [str(v) for v in f.value if v is not None]
    return []


def _parse_competence_block(
    items: Iterable[str], code_re: re.Pattern[str], prefix: str
) -> dict[str, CompetencyEntry]:
    out: dict[str, CompetencyEntry] = {}
    for raw in items:
        text = str(raw).strip()
        m = code_re.match(text)
        if m:
            code = _normalize_code(m.group(1))
            title = m.group(2).strip()
        else:
            # Fallback: assign sequential code.
            code = f"{prefix}{len(out) + 1}"
            title = text
        if code not in out:
            out[code] = CompetencyEntry(code=code, title=title)
    return out


def _attach_ri(
    catalog: dict[str, CompetencyEntry], ri_items: Iterable[str], prefix: str
) -> None:
    for raw in ri_items:
        text = str(raw).strip()
        m = _RI_RE.match(text)
        if not m:
            continue
        group_idx = int(m.group(1))
        code = f"{prefix}{group_idx}"
        if code in catalog:
            catalog[code].ri_bullets.append(text)


def _normalize_code(code: str) -> str:
    cleaned = re.sub(r"\s+", "", code).upper()
    # Coerce "CP01" → "CP1"
    m = re.match(r"^(CP|CT)(\d+)$", cleaned)
    if m:
        return f"{m.group(1)}{int(m.group(2))}"
    return cleaned
