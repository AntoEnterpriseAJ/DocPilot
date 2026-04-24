from types import SimpleNamespace

from services import claude_service


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


def test_generate_template_suggestions_uses_structured_tool_response(
    monkeypatch,
) -> None:
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                input={
                    "explanation": "Examenul final nu poate depasi 60%.",
                    "suggestions": [
                        {
                            "code": "redistribute_to_lab",
                            "label": "Redistribuie spre laborator",
                            "reason": "Pastreaza examenul la 60% si muta restul spre laborator.",
                            "confidence": "high",
                            "patch": {
                                "final_exam_weight": 60,
                                "lab_weight": 20,
                                "project_weight": 20,
                            },
                        }
                    ],
                }
            )
        ],
        stop_reason="tool_use",
    )
    fake_client = _FakeClient(response)
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)

    result = claude_service.generate_template_suggestions(
        user_message="Pune 80% pondere pe examenul final",
        template={
            "final_exam_weight": 80,
            "lab_weight": 10,
            "project_weight": 10,
        },
        schema={
            "fields": {
                "final_exam_weight": {"type": "number", "required": True},
                "lab_weight": {"type": "number", "required": True},
                "project_weight": {"type": "number", "required": True},
            }
        },
        guards=[
            {
                "code": "final_exam_cap",
                "kind": "range",
                "field": "final_exam_weight",
                "min_value": 0,
                "max_value": 60,
            }
        ],
        violations=[
            {
                "code": "final_exam_cap",
                "message": "Field 'final_exam_weight' must be at most 60.",
                "field": "final_exam_weight",
                "fields": [],
            }
        ],
        max_suggestions=3,
    )

    assert result == {
        "explanation": "Examenul final nu poate depasi 60%.",
        "suggestions": [
            {
                "code": "redistribute_to_lab",
                "label": "Redistribuie spre laborator",
                "reason": "Pastreaza examenul la 60% si muta restul spre laborator.",
                "confidence": "high",
                "patch": {
                    "final_exam_weight": 60,
                    "lab_weight": 20,
                    "project_weight": 20,
                },
            }
        ],
    }
    assert fake_client.messages.calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "suggest_template_fixes",
    }


def test_generate_guard_drafts_uses_structured_tool_response(monkeypatch) -> None:
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                input={
                    "guard_drafts": [
                        {
                            "field": "final_grade",
                            "selected_code": "final_grade_numeric",
                            "rationale": "Nota finala este evaluata numeric in document.",
                            "suggestions": [
                                {
                                    "code": "final_grade_numeric",
                                    "label": "Numeric value",
                                    "description": "Require a numeric value for the final grade.",
                                    "guard": {
                                        "code": "final_grade_numeric",
                                        "kind": "type_is",
                                        "field": "final_grade",
                                        "message": "Field 'final_grade' must be numeric.",
                                        "params": {"expected_type": "number"},
                                    },
                                },
                                {
                                    "code": "final_grade_range",
                                    "label": "Grade range 1-10",
                                    "description": "Constrain the grade to the Romanian 1-10 scale.",
                                    "guard": {
                                        "code": "final_grade_range",
                                        "kind": "range",
                                        "field": "final_grade",
                                        "message": "Field 'final_grade' must be between 1 and 10.",
                                        "params": {"min_value": 1, "max_value": 10},
                                    },
                                },
                            ],
                        }
                    ]
                }
            )
        ],
        stop_reason="tool_use",
    )
    fake_client = _FakeClient(response)
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)

    result = claude_service.generate_guard_drafts(
        document_type="grading_sheet",
        template={"final_grade": 9},
        schema={"fields": {"final_grade": {"type": "number", "required": True}}},
        baseline_guard_drafts=[
            {
                "field": "final_grade",
                "field_type": "number",
                "enabled": True,
                "selected_code": "final_grade_numeric",
                "rationale": "Deterministic numeric baseline.",
                "suggestions": [],
            }
        ],
    )

    assert result == {
        "guard_drafts": [
            {
                "field": "final_grade",
                "selected_code": "final_grade_numeric",
                "rationale": "Nota finala este evaluata numeric in document.",
                "suggestions": [
                    {
                        "code": "final_grade_numeric",
                        "label": "Numeric value",
                        "description": "Require a numeric value for the final grade.",
                        "guard": {
                            "code": "final_grade_numeric",
                            "kind": "type_is",
                            "field": "final_grade",
                            "message": "Field 'final_grade' must be numeric.",
                            "params": {"expected_type": "number"},
                        },
                    },
                    {
                        "code": "final_grade_range",
                        "label": "Grade range 1-10",
                        "description": "Constrain the grade to the Romanian 1-10 scale.",
                        "guard": {
                            "code": "final_grade_range",
                            "kind": "range",
                            "field": "final_grade",
                            "message": "Field 'final_grade' must be between 1 and 10.",
                            "params": {"min_value": 1, "max_value": 10},
                        },
                    },
                ],
            }
        ]
    }
    assert fake_client.messages.calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "suggest_guard_drafts",
    }


def test_generate_template_suggestions_sends_template_aware_prompt_context(
    monkeypatch,
) -> None:
    response = SimpleNamespace(
        content=[SimpleNamespace(input={"explanation": "ok", "suggestions": []})],
        stop_reason="tool_use",
    )
    fake_client = _FakeClient(response)
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)

    claude_service.generate_template_suggestions(
        user_message="Pune 80% pondere pe examenul final",
        template={
            "template_type": "grading",
            "final_exam_weight": 80,
            "lab_weight": 10,
            "project_weight": 10,
        },
        schema={
            "fields": {
                "final_exam_weight": {"type": "number", "required": True},
                "lab_weight": {"type": "number", "required": True},
                "project_weight": {"type": "number", "required": True},
            }
        },
        guards=[
            {
                "code": "final_exam_cap",
                "kind": "range",
                "field": "final_exam_weight",
                "min_value": 0,
                "max_value": 60,
            },
            {
                "code": "weights_total",
                "kind": "sum_equals",
                "fields": ["final_exam_weight", "lab_weight", "project_weight"],
                "expected": 100,
            },
        ],
        violations=[
            {
                "code": "final_exam_cap",
                "message": "Field 'final_exam_weight' must be at most 60.",
                "field": "final_exam_weight",
                "fields": [],
            }
        ],
        max_suggestions=3,
    )

    request = fake_client.messages.calls[0]
    assert "Romanian academic templates" in request["system"]
    assert "grading" in request["system"]
    assert "Never propose a patch that still violates the guards" in request["system"]
    prompt_text = request["messages"][0]["content"]
    assert "Current template (JSON):" in prompt_text
    assert '"template_type": "grading"' in prompt_text
    assert "Guards (JSON):" in prompt_text
    assert "Current violations (JSON):" in prompt_text