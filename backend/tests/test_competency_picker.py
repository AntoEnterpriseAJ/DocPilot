"""Tests for UC 1.4 competency picker (closed-set hallucination guard)."""
from __future__ import annotations

import pytest

from schemas.extraction import ExtractedDocument, ExtractedField
from services.competency_picker import (
    CompetencyEntry,
    PlanCompetencies,
    parse_plan_competencies,
    pick_for_course,
)


def _plan(**fields: object) -> ExtractedDocument:
    return ExtractedDocument(
        document_type="form",
        source_route="text_pdf",
        summary="",
        fields=[
            ExtractedField(key=k, value=v, field_type="list", confidence="high")  # type: ignore[arg-type]
            for k, v in fields.items()
        ],
        tables=[],
    )


def test_parse_plan_competencies_groups_ri_bullets_by_index() -> None:
    plan = _plan(
        competente_profesionale=[
            "CP1. Creează software.",
            "CP2. Utilizează șabloane.",
        ],
        rezultate_invatare_profesionale=[
            "RÎ.1.1. Absolventul transpune cerințe.",
            "RÎ.1.2. Absolventul creează prototipuri.",
            "RÎ.2.1. Absolventul folosește pattern-uri.",
        ],
        competente_transversale=["CT1. Lucrează în echipă."],
        rezultate_invatare_transversale=["RÎ.1.1. Absolventul colaborează."],
    )

    comps = parse_plan_competencies(plan)
    assert set(comps.cp.keys()) == {"CP1", "CP2"}
    assert set(comps.ct.keys()) == {"CT1"}
    assert len(comps.cp["CP1"].ri_bullets) == 2
    assert len(comps.cp["CP2"].ri_bullets) == 1
    assert comps.cp["CP1"].title.startswith("Creează software")


def test_parse_plan_competencies_falls_back_to_competente_catalog() -> None:
    """Live PI fast-parser produces ``competente_catalog`` instead of the 4 separate fields."""
    plan = _plan(
        competente_catalog=[
            "CP1: Creează software.",
            "CP02: Utilizează șabloane.",   # normalize to CP2
            "CT1: Lucrează în echipă.",
            "FOO: ignored",                  # not CP/CT
        ],
    )
    comps = parse_plan_competencies(plan)
    assert set(comps.cp.keys()) == {"CP1", "CP2"}
    assert set(comps.ct.keys()) == {"CT1"}
    assert comps.cp["CP1"].ri_bullets == []  # no R.Î. info available in this format


def test_pick_for_course_returns_fallback_when_catalog_empty() -> None:
    empty = PlanCompetencies(cp={}, ct={})
    pick = pick_for_course(
        course_name="Anything",
        course_meta={},
        plan_competencies=empty,
        use_claude=True,
    )
    assert pick.cp == [] and pick.ct == []
    assert pick.fallback_reason is not None
    assert "absent" in pick.fallback_reason.lower()


def test_pick_for_course_skips_ai_when_disabled() -> None:
    comps = PlanCompetencies(
        cp={"CP1": CompetencyEntry(code="CP1", title="x")},
        ct={"CT1": CompetencyEntry(code="CT1", title="y")},
    )
    pick = pick_for_course(
        course_name="x",
        course_meta={},
        plan_competencies=comps,
        use_claude=False,
    )
    assert pick.cp == [] and pick.ct == []
    assert pick.fallback_reason is not None
    assert "ai" in pick.fallback_reason.lower()


def test_pick_for_course_rejects_hallucinated_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Claude returning unknown CP/CT IDs must not leak into the result."""
    comps = PlanCompetencies(
        cp={
            "CP1": CompetencyEntry(code="CP1", title="t1"),
            "CP2": CompetencyEntry(code="CP2", title="t2"),
        },
        ct={"CT1": CompetencyEntry(code="CT1", title="ct1")},
    )

    def fake_call(**_kwargs):  # noqa: ANN003
        return {
            "selected_cp": [
                {"code": "CP2", "rationale": "ok"},
                {"code": "CP99", "rationale": "hallucinated"},  # MUST be dropped
                {"code": "NOPE", "rationale": "garbage"},        # MUST be dropped
            ],
            "selected_ct": [
                {"code": "CT1", "rationale": "fine"},
                {"code": "CT5", "rationale": "hallucinated"},   # MUST be dropped
            ],
        }

    # Stub the lazy-imported claude_service module that the picker calls.
    from services import claude_service  # noqa: WPS433
    monkeypatch.setattr(claude_service, "_call_claude_tool", fake_call)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    pick = pick_for_course(
        course_name="X",
        course_meta={"year": 1},
        plan_competencies=comps,
        use_claude=True,
    )

    assert [e.code for e in pick.cp] == ["CP2"]
    assert [e.code for e in pick.ct] == ["CT1"]
    assert pick.rationale == {"CP2": "ok", "CT1": "fine"}
    assert pick.ai_used is True


def test_pick_for_course_respects_max_n(monkeypatch: pytest.MonkeyPatch) -> None:
    comps = PlanCompetencies(
        cp={f"CP{i}": CompetencyEntry(code=f"CP{i}", title=f"t{i}") for i in range(1, 6)},
        ct={f"CT{i}": CompetencyEntry(code=f"CT{i}", title=f"ct{i}") for i in range(1, 4)},
    )

    def fake_call(**_kwargs):  # noqa: ANN003
        return {
            "selected_cp": [{"code": f"CP{i}", "rationale": "x"} for i in range(1, 6)],
            "selected_ct": [{"code": f"CT{i}", "rationale": "x"} for i in range(1, 4)],
        }

    from services import claude_service  # noqa: WPS433
    monkeypatch.setattr(claude_service, "_call_claude_tool", fake_call)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    pick = pick_for_course(
        course_name="X",
        course_meta={},
        plan_competencies=comps,
        max_cp=2,
        max_ct=1,
        use_claude=True,
    )
    assert len(pick.cp) == 2
    assert len(pick.ct) == 1
