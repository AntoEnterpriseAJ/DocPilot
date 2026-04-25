"""Academic Copilot — single-shot LLM rewrite of an FD section.

Stateless. Frontend chains turns by feeding the previous proposal back
in as `current_text`.
"""
from __future__ import annotations

import os

from schemas.copilot import (
    CourseContext,
    RewriteSectionRequest,
    RewriteSectionResponse,
)
from services import claude_service as _cs


_TOOL = {
    "name": "propose_section_rewrite",
    "description": (
        "Propose a rewritten version of an academic syllabus (Fișa "
        "Disciplinei) section that satisfies the professor's instruction "
        "while staying coherent with the rest of the course."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "proposed_text": {
                "type": "string",
                "description": (
                    "The full rewritten section body in Romanian, "
                    "paragraphs separated by blank lines. Do not include "
                    "the section heading itself."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "1-2 short sentences in Romanian explaining what was "
                    "changed and why, addressed to the professor."
                ),
            },
        },
        "required": ["proposed_text", "rationale"],
    },
}


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _format_context(ctx: CourseContext | None) -> str:
    if ctx is None:
        return ""
    parts: list[str] = []
    if ctx.course_name:
        parts.append(f"Disciplina: {ctx.course_name}")
    if ctx.program:
        parts.append(f"Program de studii: {ctx.program}")
    if ctx.competencies:
        joined = "\n".join(f"- {c}" for c in ctx.competencies)
        parts.append(f"Competențe vizate:\n{joined}")
    return "\n".join(parts)


def rewrite_section(req: RewriteSectionRequest) -> RewriteSectionResponse:
    """Call Claude to produce a rewrite of the given section."""
    instruction = req.instruction.strip()
    if not instruction:
        raise ValueError("instruction is required")
    if not req.current_text.strip() and not req.section_heading.strip():
        raise ValueError("section_heading or current_text must be provided")

    context_block = _format_context(req.course_context)

    system = (
        "Ești un asistent academic care rescrie secțiuni din Fișa "
        "Disciplinei. Răspunzi întotdeauna în limba română academică, "
        "păstrezi terminologia universitară și nu inventezi date "
        "administrative (titulari, ani, credite). Dacă instrucțiunea "
        "profesorului contrazice conținutul existent, prioritar este "
        "instrucțiunea, dar menționezi schimbarea în rationale."
    )

    user_parts = [
        f"## Secțiunea de rescris\n{req.section_heading or '(fără titlu)'}",
    ]
    if context_block:
        user_parts.append(f"## Context curs\n{context_block}")
    user_parts.append(
        "## Conținut actual\n"
        + (req.current_text.strip() or "(secțiune goală)")
    )
    user_parts.append(f"## Instrucțiune\n{instruction}")
    user_parts.append(
        "Apelează tool-ul propose_section_rewrite cu noul conținut."
    )

    client = _cs._get_client()
    message = client.messages.create(
        model=_cs._MODEL,
        max_tokens=_cs._MAX_TOKENS,
        system=system,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "propose_section_rewrite"},
        messages=[{"role": "user", "content": "\n\n".join(user_parts)}],
    )

    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            data = block.input or {}
            return RewriteSectionResponse(
                proposed_text=str(data.get("proposed_text", "")).strip(),
                rationale=str(data.get("rationale", "")).strip(),
            )

    raise RuntimeError("Claude did not return a tool_use block")
