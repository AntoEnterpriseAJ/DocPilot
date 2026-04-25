"""Pydantic schemas for the Academic Copilot (UC 3.3)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CourseContext(BaseModel):
    course_name: str | None = None
    program: str | None = None
    competencies: list[str] = Field(default_factory=list)


class RewriteSectionRequest(BaseModel):
    section_heading: str = ""
    current_text: str = ""
    instruction: str
    course_context: CourseContext | None = None


class RewriteSectionResponse(BaseModel):
    proposed_text: str
    rationale: str
