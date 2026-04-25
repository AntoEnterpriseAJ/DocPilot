"""Tests for the diff narrative explainer."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from services import claude_service, diff_explainer


class _FakeMessages:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.messages = _FakeMessages(response)


def _fake_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=payload)],
        stop_reason="tool_use",
    )


def test_explain_diff_returns_narrative_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "narrative": "Ați primit o nouă versiune a fișei...",
        "key_changes": ["Examenul final a scăzut la 60%."],
        "action_items": ["Redistribuiți restul de 10% către laborator."],
    }
    fake = _FakeClient(_fake_response(payload))
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake)

    result = diff_explainer.explain_diff({
        "summary": {"total_sections": 7, "modified": 2, "logic_changes_count": 1},
        "logic_changes": [{
            "type": "EXAM_WEIGHT_CHANGED",
            "section": "Evaluare",
            "severity": "high",
            "old_value": "70%",
            "new_value": "60%",
            "description": "Ponderea examenului final a fost redusă.",
        }],
        "sections": [],
    })

    assert result["narrative"].startswith("Ați primit")
    assert result["key_changes"] == payload["key_changes"]
    assert result["action_items"] == payload["action_items"]


def test_explain_diff_sends_diff_summary_in_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(_fake_response({"narrative": "x", "key_changes": [], "action_items": []}))
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake)

    diff_explainer.explain_diff({
        "summary": {"total_sections": 5, "modified": 1, "logic_changes_count": 0},
        "logic_changes": [],
        "sections": [{
            "name": "Bibliografie",
            "status": "modified",
            "lines": [
                {"type": "remove", "old_text": "Vechi titlu 2018", "new_text": ""},
                {"type": "add", "old_text": "", "new_text": "Titlu nou 2025"},
            ],
        }],
    })

    call = fake.messages.calls[0]
    user_text = call["messages"][0]["content"]
    assert "Bibliografie" in user_text
    assert "Vechi titlu 2018" in user_text
    assert "Titlu nou 2025" in user_text
    assert call["tool_choice"]["name"] == "explain_document_diff"


def test_explain_diff_raises_when_no_tool_use(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")], stop_reason="end_turn")
    fake = _FakeClient(bad)
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake)

    with pytest.raises(RuntimeError, match="tool_use"):
        diff_explainer.explain_diff({"summary": {}, "logic_changes": [], "sections": []})
