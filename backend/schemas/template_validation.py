from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict
from pydantic import BaseModel, Field


ValidationStatus = Literal["valid", "invalid"]
SuggestionConfidence = Literal["high", "medium", "low"]


class SuggestionOption(BaseModel):
    code: str
    label: str
    patch: dict[str, Any] = Field(default_factory=dict)


class GuardViolation(BaseModel):
    code: str
    message: str
    field: str | None = None
    fields: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    status: ValidationStatus
    violations: list[GuardViolation] = Field(default_factory=list)
    suggestions: list[SuggestionOption] = Field(default_factory=list)


class SemanticSuggestion(BaseModel):
    code: str
    label: str
    reason: str
    confidence: SuggestionConfidence = "medium"
    patch: dict[str, Any] = Field(default_factory=dict)


class SemanticSuggestionResult(BaseModel):
    explanation: str
    violations: list[GuardViolation] = Field(default_factory=list)
    suggestions: list[SemanticSuggestion] = Field(default_factory=list)


class GuardDefinition(BaseModel):
    code: str
    kind: str
    field: str | None = None
    fields: list[str] = Field(default_factory=list)
    message: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class GuardSuggestion(BaseModel):
    code: str
    label: str
    description: str
    guard: GuardDefinition


class FieldGuardDraft(BaseModel):
    field: str
    field_type: str
    current_value: Any | None = None
    enabled: bool = True
    selected_code: str
    rationale: str = ""
    suggestions: list[GuardSuggestion] = Field(default_factory=list)


class TemplateDraftResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_type: str = "form"
    template: dict[str, Any] = Field(default_factory=dict)
    template_schema: dict[str, Any] = Field(default_factory=dict, alias="schema")
    guard_drafts: list[FieldGuardDraft] = Field(default_factory=list)
    guards: list[GuardDefinition] = Field(default_factory=list)
