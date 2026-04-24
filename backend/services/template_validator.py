from __future__ import annotations

from typing import Any

from schemas.template_validation import GuardViolation, SuggestionOption, ValidationResult


def validate_template(
    *, template: dict[str, Any], schema: dict[str, Any], guards: list[dict[str, Any]]
) -> ValidationResult:
    violations: list[GuardViolation] = []
    suggestions: list[SuggestionOption] = []

    field_definitions = schema.get("fields", {})

    for field_name, field_schema in field_definitions.items():
        value = template.get(field_name)
        if value is None:
            if field_schema.get("required"):
                violations.append(
                    GuardViolation(
                        code="field_required",
                        message=f"Field '{field_name}' is required.",
                        field=field_name,
                    )
                )
            continue

        expected_type = field_schema.get("type")
        if not _value_matches_type(value, expected_type):
            violations.append(
                GuardViolation(
                    code="field_type_mismatch",
                    message=(
                        f"Field '{field_name}' must be of type '{expected_type}'."
                    ),
                    field=field_name,
                )
            )

    for guard in guards:
        guard_kind = guard.get("kind")
        if guard_kind == "range":
            violation = _evaluate_range_guard(template, guard)
        elif guard_kind == "sum_equals":
            violation = _evaluate_sum_equals_guard(template, guard)
        else:
            violation = None

        if violation is not None:
            violations.append(violation)
            if guard.get("suggestion"):
                suggestions.append(
                    SuggestionOption(
                        code=guard["code"],
                        label=str(guard["suggestion"].get("label", guard["code"])),
                        patch=dict(guard["suggestion"].get("patch", {})),
                    )
                )

    return ValidationResult(
        status="invalid" if violations else "valid",
        violations=violations,
        suggestions=suggestions,
    )


def _evaluate_range_guard(
    template: dict[str, Any], guard: dict[str, Any]
) -> GuardViolation | None:
    field_name = guard["field"]
    value = template.get(field_name)
    if not _is_number(value):
        return None

    min_value = guard.get("min_value")
    max_value = guard.get("max_value")

    if min_value is not None and value < min_value:
        return GuardViolation(
            code=guard["code"],
            message=f"Field '{field_name}' must be at least {min_value}.",
            field=field_name,
        )

    if max_value is not None and value > max_value:
        return GuardViolation(
            code=guard["code"],
            message=f"Field '{field_name}' must be at most {max_value}.",
            field=field_name,
        )

    return None


def _evaluate_sum_equals_guard(
    template: dict[str, Any], guard: dict[str, Any]
) -> GuardViolation | None:
    field_names = list(guard.get("fields", []))
    values = [template.get(field_name) for field_name in field_names]
    if not all(_is_number(value) for value in values):
        return None

    actual_total = sum(values)
    expected_total = guard["expected"]
    if actual_total == expected_total:
        return None

    return GuardViolation(
        code=guard["code"],
        message=f"Fields must sum to {expected_total}; received {actual_total}.",
        fields=field_names,
    )


def _value_matches_type(value: Any, expected_type: str | None) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return _is_number(value)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "list":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)