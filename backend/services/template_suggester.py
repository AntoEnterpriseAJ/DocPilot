from __future__ import annotations

from typing import Any

from schemas.template_validation import GuardViolation, SemanticSuggestion, SemanticSuggestionResult
from services import claude_service
from services.template_validator import validate_template


def suggest_template_fixes(
    *,
    user_message: str,
    template: dict[str, Any],
    schema: dict[str, Any],
    guards: list[dict[str, Any]],
    max_suggestions: int = 3,
) -> SemanticSuggestionResult:
    validation_result = validate_template(
        template=template,
        schema=schema,
        guards=guards,
    )

    violations = validation_result.violations
    if not violations:
        return SemanticSuggestionResult(
            explanation="Template is already valid.",
            violations=[],
            suggestions=[],
        )

    raw_result = claude_service.generate_template_suggestions(
        user_message=user_message,
        template=template,
        schema=schema,
        guards=guards,
        violations=[violation.model_dump() for violation in violations],
        max_suggestions=max_suggestions,
    )

    explanation = str(raw_result.get("explanation", ""))
    accepted_suggestions: list[SemanticSuggestion] = []

    for suggestion_data in raw_result.get("suggestions", []):
        patch = dict(suggestion_data.get("patch", {}))
        candidate_template = {**template, **patch}
        candidate_result = validate_template(
            template=candidate_template,
            schema=schema,
            guards=guards,
        )
        if candidate_result.violations:
            continue

        accepted_suggestions.append(
            SemanticSuggestion(
                code=str(suggestion_data.get("code", "suggestion")),
                label=str(suggestion_data.get("label", "Suggested fix")),
                reason=str(suggestion_data.get("reason", "")),
                confidence=str(suggestion_data.get("confidence", "medium")),
                patch=patch,
            )
        )

        if len(accepted_suggestions) >= max_suggestions:
            break

    return SemanticSuggestionResult(
        explanation=explanation,
        violations=[
            GuardViolation.model_validate(violation.model_dump()) for violation in violations
        ],
        suggestions=accepted_suggestions,
    )