from pydantic import BaseModel, Field
from typing import Optional, List

class InlineDiff(BaseModel):
    """Word-level diff within a line."""
    text: str
    type: str  # "equal" | "remove" | "add"

class LineDiff(BaseModel):
    """Single line in a diff."""
    type: str  # "equal" | "remove" | "add" | "replace"
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    old_line_no: Optional[int] = None
    new_line_no: Optional[int] = None
    inline_diff: List[InlineDiff] = Field(default_factory=list)

class SectionDiff(BaseModel):
    """Diff for a single section."""
    name: str
    status: str  # "equal" | "modified" | "added" | "removed"
    lines: List[LineDiff] = Field(default_factory=list)

class LogicChange(BaseModel):
    """Represents a semantic change detected in the diff."""
    type: str  # e.g., "HOURS_CHANGED", "ECTS_CHANGED"
    section: str
    description: str
    severity: str  # "LOW" | "MEDIUM" | "HIGH"
    old_value: Optional[str] = None
    new_value: Optional[str] = None

class DiffSummary(BaseModel):
    """Statistics about the diff."""
    total_sections: int
    modified: int
    added: int
    removed: int
    unchanged: int
    logic_changes_count: int

class DiffResponse(BaseModel):
    """Complete API response for a diff operation."""
    sections: List[SectionDiff] = Field(default_factory=list)
    logic_changes: List[LogicChange] = Field(default_factory=list)
    summary: Optional[DiffSummary] = None
