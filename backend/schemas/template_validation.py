from __future__ import annotations

from typing import Any, Literal

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
