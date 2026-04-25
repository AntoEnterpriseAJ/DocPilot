"""Tests for the Academic Copilot rewrite endpoint."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from services import copilot_service


client = TestClient(app)


def _fake_message(proposed: str, rationale: str):
    block = SimpleNamespace(
        type="tool_use",
        input={"proposed_text": proposed, "rationale": rationale},
    )
    return SimpleNamespace(content=[block])


def test_rewrite_section_503_when_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post(
        "/api/documents/rewrite-section",
        json={"instruction": "shorten", "current_text": "abc"},
    )
    assert r.status_code == 503


def test_rewrite_section_400_on_empty_inputs(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # Force the client builder so we never hit the network if validation
    # somehow lets it through.
    with patch.object(copilot_service._cs, "_get_client") as mocked:
        mocked.return_value = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **_: _fake_message("x", "y"))
        )
        r = client.post(
            "/api/documents/rewrite-section",
            json={
                "instruction": "   ",
                "current_text": "anything",
            },
        )
    assert r.status_code == 400


def test_rewrite_section_happy_path(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: _fake_message(
                "Conținut nou\n\nAl doilea paragraf.",
                "Am adăugat referințe la AI.",
            )
        )
    )
    with patch.object(copilot_service._cs, "_get_client", return_value=fake_client):
        r = client.post(
            "/api/documents/rewrite-section",
            json={
                "section_heading": "8.1 Tematica activităților de curs",
                "current_text": "Curs introductiv.",
                "instruction": "Include noțiuni de AI.",
                "course_context": {
                    "course_name": "Analiza matematică I",
                    "competencies": ["C1 calcul diferențial"],
                },
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proposed_text"].startswith("Conținut nou")
    assert "AI" in body["rationale"]
