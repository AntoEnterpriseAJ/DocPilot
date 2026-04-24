from __future__ import annotations

from typing import Any

from schemas.extraction import ExtractedDocument, ExtractedField
from schemas.template_validation import FieldGuardDraft, GuardDefinition, GuardSuggestion


def build_template_schema_and_baseline_drafts(
    document: ExtractedDocument,
) -> tuple[dict[str, Any], dict[str, Any], list[FieldGuardDraft]]:
    template: dict[str, Any] = {}
    schema_fields: dict[str, dict[str, Any]] = {}
    baseline_drafts: list[FieldGuardDraft] = []

    for field in document.fields:
        template[field.key] = field.value
        schema_fields[field.key] = {
            "type": _schema_type_for(field.field_type),
            "required": field.value is not None,
        }

        suggestions = _baseline_suggestions_for(field)
        if not suggestions:
            continue

        baseline_drafts.append(
            FieldGuardDraft(
                field=field.key,
                field_type=field.field_type,
                current_value=field.value,
                enabled=True,
                selected_code=suggestions[0].code,
                rationale=_baseline_rationale(field),
                suggestions=suggestions,
            )
        )

    return template, {"fields": schema_fields}, baseline_drafts


def build_schema_and_baseline_drafts_from_template(
    *,
    template: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[FieldGuardDraft]]:
    schema_fields = dict((schema or {}).get("fields", {}))
    baseline_drafts: list[FieldGuardDraft] = []

    for field_name, value in template.items():
        field_type = str(schema_fields.get(field_name, {}).get("type") or _infer_field_type(value))
        schema_fields[field_name] = {
            "type": field_type,
            "required": bool(schema_fields.get(field_name, {}).get("required", value is not None)),
        }

        extracted_field = ExtractedField(
            key=field_name,
            value=value,
            field_type=_normalize_field_type(field_type),
        )
        suggestions = _baseline_suggestions_for(extracted_field)
        if not suggestions:
            continue

        baseline_drafts.append(
            FieldGuardDraft(
                field=field_name,
                field_type=extracted_field.field_type,
                current_value=value,
                enabled=True,
                selected_code=suggestions[0].code,
                rationale=_baseline_rationale(extracted_field),
                suggestions=suggestions,
            )
        )

    return {"fields": schema_fields}, baseline_drafts


def merge_guard_drafts(
    baseline_drafts: list[FieldGuardDraft],
    raw_result: dict[str, Any] | None,
) -> list[FieldGuardDraft]:
    if not raw_result:
        return baseline_drafts

    raw_drafts = raw_result.get("guard_drafts", [])
    if not raw_drafts:
        return baseline_drafts

    baseline_by_field = {draft.field: draft for draft in baseline_drafts}
    merged: list[FieldGuardDraft] = []

    for raw_draft in raw_drafts:
        field_name = str(raw_draft.get("field", ""))
        baseline = baseline_by_field.get(field_name)
        if baseline is None:
            continue

        merged.append(
            FieldGuardDraft(
                field=field_name,
                field_type=baseline.field_type,
                current_value=baseline.current_value,
                enabled=bool(raw_draft.get("enabled", baseline.enabled)),
                selected_code=str(raw_draft.get("selected_code", baseline.selected_code)),
                rationale=str(raw_draft.get("rationale", baseline.rationale)),
                suggestions=[
                    GuardSuggestion.model_validate(suggestion)
                    for suggestion in raw_draft.get("suggestions", [])
                ],
            )
        )

    return merged or baseline_drafts


def select_guards(guard_drafts: list[FieldGuardDraft]) -> list[GuardDefinition]:
    selected_guards: list[GuardDefinition] = []

    for draft in guard_drafts:
        if not draft.enabled:
            continue

        selected_suggestion = next(
            (suggestion for suggestion in draft.suggestions if suggestion.code == draft.selected_code),
            None,
        )
        if selected_suggestion is None:
            continue

        selected_guards.append(selected_suggestion.guard)

    return selected_guards


def serialize_guard_drafts(guard_drafts: list[FieldGuardDraft]) -> list[dict[str, Any]]:
    return [draft.model_dump(mode="json", exclude_none=True) for draft in guard_drafts]


def _schema_type_for(field_type: str) -> str:
    if field_type in {"date", "id", "signature"}:
        return "string"
    return field_type


def _normalize_field_type(field_type: str) -> str:
    if field_type in {"string", "number", "boolean", "list", "date", "signature", "id"}:
        return field_type
    return "string"


def _infer_field_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "list"
    return "string"


def _baseline_rationale(field: ExtractedField) -> str:
    if field.field_type == "number":
        return "Numeric fields benefit from explicit type or range guards."
    if field.field_type == "date":
        return "Dates benefit from format-oriented guards."
    if field.field_type == "boolean":
        return "Boolean fields should stay limited to true/false values."
    if field.field_type == "id":
        return "Identifiers usually need a stable format or non-empty check."
    return "Drafted from extracted field metadata."


def _baseline_suggestions_for(field: ExtractedField) -> list[GuardSuggestion]:
    if field.field_type == "number":
        suggestions = [
            GuardSuggestion(
                code=f"{field.key}_numeric",
                label="Numeric value",
                description=f"Require a numeric value for '{field.key}'.",
                guard=GuardDefinition(
                    code=f"{field.key}_numeric",
                    kind="type_is",
                    field=field.key,
                    message=f"Field '{field.key}' must be numeric.",
                    params={"expected_type": "number"},
                ),
            )
        ]

        if "grade" in field.key:
            suggestions.append(
                GuardSuggestion(
                    code=f"{field.key}_range",
                    label="Grade range 1-10",
                    description="Restrict the value to the Romanian grading scale.",
                    guard=GuardDefinition(
                        code=f"{field.key}_range",
                        kind="range",
                        field=field.key,
                        message=f"Field '{field.key}' must be between 1 and 10.",
                        params={"min_value": 1, "max_value": 10},
                    ),
                )
            )
        elif "percent" in field.key:
            suggestions.append(
                GuardSuggestion(
                    code=f"{field.key}_range",
                    label="Percentage range 0-100",
                    description="Restrict the value to a percentage scale.",
                    guard=GuardDefinition(
                        code=f"{field.key}_range",
                        kind="range",
                        field=field.key,
                        message=f"Field '{field.key}' must be between 0 and 100.",
                        params={"min_value": 0, "max_value": 100},
                    ),
                )
            )

        return suggestions

    if field.field_type == "date":
        return [
            GuardSuggestion(
                code=f"{field.key}_date",
                label="ISO date",
                description="Require an ISO-8601 date string.",
                guard=GuardDefinition(
                    code=f"{field.key}_date",
                    kind="type_is",
                    field=field.key,
                    message=f"Field '{field.key}' must be an ISO date string.",
                    params={"expected_type": "date"},
                ),
            )
        ]

    if field.field_type == "boolean":
        return [
            GuardSuggestion(
                code=f"{field.key}_boolean",
                label="Boolean value",
                description="Require a true/false value.",
                guard=GuardDefinition(
                    code=f"{field.key}_boolean",
                    kind="type_is",
                    field=field.key,
                    message=f"Field '{field.key}' must be boolean.",
                    params={"expected_type": "boolean"},
                ),
            )
        ]

    if field.field_type == "id":
        return [
            GuardSuggestion(
                code=f"{field.key}_non_empty",
                label="Non-empty ID",
                description="Require a non-empty identifier value.",
                guard=GuardDefinition(
                    code=f"{field.key}_non_empty",
                    kind="non_empty",
                    field=field.key,
                    message=f"Field '{field.key}' must not be empty.",
                ),
            )
        ]

    return []