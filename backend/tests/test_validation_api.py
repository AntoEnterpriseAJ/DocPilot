import pytest
from fastapi.testclient import TestClient

from main import app
from services import claude_service


client = TestClient(app)


def test_validate_endpoint_returns_guard_violations() -> None:
    response = client.post(
        "/api/documents/validate",
        json={
            "template": {
                "course_name": "Programare avansata",
                "final_exam_weight": 80,
                "lab_weight": 10,
                "project_weight": 10,
                "final_grade": 9,
            },
            "schema": {
                "fields": {
                    "course_name": {"type": "string", "required": True},
                    "final_exam_weight": {"type": "number", "required": True},
                    "lab_weight": {"type": "number", "required": True},
                    "project_weight": {"type": "number", "required": True},
                    "final_grade": {"type": "number", "required": True},
                }
            },
            "guards": [
                {
                    "code": "final_exam_cap",
                    "kind": "range",
                    "field": "final_exam_weight",
                    "min_value": 0,
                    "max_value": 60,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "invalid",
        "violations": [
            {
                "code": "final_exam_cap",
                "message": "Field 'final_exam_weight' must be at most 60.",
                "field": "final_exam_weight",
                "fields": [],
            }
        ],
        "suggestions": [],
    }


def test_suggest_endpoint_returns_only_revalidated_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_generate_template_suggestions(
        *,
        user_message: str,
        template: dict,
        schema: dict,
        guards: list[dict],
        violations: list[dict],
        max_suggestions: int,
    ) -> dict:
        return {
            "explanation": "Examenul final nu poate depasi 60%.",
            "suggestions": [
                {
                    "code": "keep_exam_at_60",
                    "label": "Muta diferenta spre laborator",
                    "reason": "Pastreaza examenul la 60% si redistribuie restul catre laborator.",
                    "confidence": "high",
                    "patch": {
                        "final_exam_weight": 60,
                        "lab_weight": 20,
                        "project_weight": 20,
                    },
                },
                {
                    "code": "invalid_total",
                    "label": "Varianta invalida",
                    "reason": "Aceasta varianta nu respecta totalul.",
                    "confidence": "medium",
                    "patch": {
                        "final_exam_weight": 60,
                        "lab_weight": 10,
                        "project_weight": 10,
                    },
                },
            ],
        }

    monkeypatch.setattr(
        claude_service,
        "generate_template_suggestions",
        fake_generate_template_suggestions,
    )

    response = client.post(
        "/api/documents/suggest",
        json={
            "user_message": "Pune 80% pondere pe examenul final",
            "template": {
                "course_name": "Programare avansata",
                "final_exam_weight": 80,
                "lab_weight": 10,
                "project_weight": 10,
                "final_grade": 9,
            },
            "schema": {
                "fields": {
                    "course_name": {"type": "string", "required": True},
                    "final_exam_weight": {"type": "number", "required": True},
                    "lab_weight": {"type": "number", "required": True},
                    "project_weight": {"type": "number", "required": True},
                    "final_grade": {"type": "number", "required": True},
                }
            },
            "guards": [
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
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "explanation": "Examenul final nu poate depasi 60%.",
        "violations": [
            {
                "code": "final_exam_cap",
                "message": "Field 'final_exam_weight' must be at most 60.",
                "field": "final_exam_weight",
                "fields": [],
            }
        ],
        "suggestions": [
            {
                "code": "keep_exam_at_60",
                "label": "Muta diferenta spre laborator",
                "reason": "Pastreaza examenul la 60% si redistribuie restul catre laborator.",
                "confidence": "high",
                "patch": {
                    "final_exam_weight": 60,
                    "lab_weight": 20,
                    "project_weight": 20,
                },
            }
        ],
    }