import pytest

from services.template_validator import validate_template


BASE_SCHEMA = {
    "fields": {
        "course_name": {"type": "string", "required": True},
        "final_exam_weight": {"type": "number", "required": True},
        "lab_weight": {"type": "number", "required": True},
        "project_weight": {"type": "number", "required": True},
        "final_grade": {"type": "number", "required": True},
    }
}


BASE_TEMPLATE = {
    "course_name": "Programare avansata",
    "final_exam_weight": 60,
    "lab_weight": 20,
    "project_weight": 20,
    "final_grade": 9,
}


def test_validate_template_accepts_valid_payload() -> None:
    result = validate_template(
        template=BASE_TEMPLATE,
        schema=BASE_SCHEMA,
        guards=[
            {
                "code": "grade_range",
                "kind": "range",
                "field": "final_grade",
                "min_value": 1,
                "max_value": 10,
            },
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
    )

    assert result.status == "valid"
    assert result.violations == []


@pytest.mark.parametrize(
    ("template", "schema", "guards", "expected_codes"),
    [
        (
            {"final_grade": "A"},
            {"fields": {"final_grade": {"type": "number", "required": True}}},
            [],
            ["field_type_mismatch"],
        ),
        (
            {**BASE_TEMPLATE, "final_exam_weight": 80, "lab_weight": 10, "project_weight": 10},
            BASE_SCHEMA,
            [
                {
                    "code": "final_exam_cap",
                    "kind": "range",
                    "field": "final_exam_weight",
                    "min_value": 0,
                    "max_value": 60,
                }
            ],
            ["final_exam_cap"],
        ),
        (
            {**BASE_TEMPLATE, "final_exam_weight": 50},
            BASE_SCHEMA,
            [
                {
                    "code": "weights_total",
                    "kind": "sum_equals",
                    "fields": ["final_exam_weight", "lab_weight", "project_weight"],
                    "expected": 100,
                }
            ],
            ["weights_total"],
        ),
    ],
)
def test_validate_template_rejects_invalid_templates(
    template: dict, schema: dict, guards: list[dict], expected_codes: list[str]
) -> None:
    result = validate_template(
        template=template,
        schema=schema,
        guards=guards,
    )

    assert result.status == "invalid"
    assert [violation.code for violation in result.violations] == expected_codes