"""
Diff narrative explainer — takes a DiffResponse from diff-service and asks
Claude to produce a plain-Romanian summary aimed at a professor.

This is the L5 "Delta Report" from the brief: turn structured diffs into
human-readable explanations of what changed and what the user should do.
"""
from __future__ import annotations

from typing import Any

from services import claude_service


_SYSTEM_PROMPT = (
    "Ești un asistent academic care explică clar și concis schimbările dintre "
    "două versiuni ale unui document academic românesc (Fișa Disciplinei sau "
    "Plan de Învățământ). Scrii în limba română, formal dar accesibil. "
    "Te concentrezi pe ce s-a schimbat semnificativ, NU pe diferențe minore "
    "de formatare. Evidențiezi în mod special schimbările care necesită "
    "acțiune din partea profesorului."
)


def explain_diff(diff_response: dict[str, Any]) -> dict[str, Any]:
    """Generate a narrative explanation of a DiffResponse.

    Returns a dict with:
      - narrative: str (full plain-Romanian summary)
      - key_changes: list[str] (bullet-pointed important changes)
      - action_items: list[str] (things the professor must address)
    """
    summary_block = _format_diff_for_prompt(diff_response)

    user_message = (
        "Mai jos este rezultatul comparației dintre două versiuni ale unui "
        "document academic. Generează un raport explicativ în română.\n\n"
        f"{summary_block}\n\n"
        "Returnează rezultatul folosind tool-ul 'explain_document_diff'."
    )

    response = claude_service._get_client().messages.create(
        model=claude_service._MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        tools=[_EXPLAIN_TOOL],
        tool_choice={"type": "tool", "name": "explain_document_diff"},
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)  # type: ignore[union-attr]

    raise RuntimeError("Claude did not return a tool_use block for explain_diff.")


_EXPLAIN_TOOL: dict = {
    "name": "explain_document_diff",
    "description": (
        "Produce a Romanian-language narrative explaining the changes between "
        "two versions of an academic document, plus key changes and action items."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative": {
                "type": "string",
                "description": (
                    "2-4 paragrafe în română care explică, la nivel de ansamblu, "
                    "ce s-a schimbat între cele două versiuni. Adresează-te direct "
                    "profesorului ('Ați avut...', 'Va trebui să...')."
                ),
            },
            "key_changes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Lista celor mai importante schimbări (3-7 puncte), formulate "
                    "scurt și concret, cu valori specifice unde e relevant."
                ),
            },
            "action_items": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Lista acțiunilor pe care profesorul trebuie să le facă "
                    "ca răspuns la aceste schimbări. Poate fi listă goală dacă "
                    "schimbările sunt pur informative."
                ),
            },
        },
        "required": ["narrative", "key_changes", "action_items"],
    },
}


def _format_diff_for_prompt(diff: dict[str, Any]) -> str:
    parts: list[str] = []

    summary = diff.get("summary") or {}
    if summary:
        parts.append(
            "REZUMAT NUMERIC:\n"
            f"  - Total secțiuni: {summary.get('total_sections', '?')}\n"
            f"  - Modificate: {summary.get('modified', 0)}\n"
            f"  - Adăugate: {summary.get('added', 0)}\n"
            f"  - Eliminate: {summary.get('removed', 0)}\n"
            f"  - Neschimbate: {summary.get('unchanged', 0)}\n"
            f"  - Schimbări de logică: {summary.get('logic_changes_count', 0)}"
        )

    logic_changes = diff.get("logic_changes") or []
    if logic_changes:
        parts.append("\nSCHIMBĂRI DE LOGICĂ DETECTATE:")
        for lc in logic_changes:
            parts.append(
                f"  • [{lc.get('severity', 'info')}] {lc.get('type', '?')} "
                f"în secțiunea '{lc.get('section', '?')}': "
                f"{lc.get('old_value', '?')} → {lc.get('new_value', '?')}. "
                f"{lc.get('description', '')}"
            )

    sections = diff.get("sections") or []
    modified_sections = [s for s in sections if s.get("status") in {"modified", "added", "removed"}]
    if modified_sections:
        parts.append("\nSECȚIUNI MODIFICATE/ADĂUGATE/ELIMINATE:")
        for sec in modified_sections[:20]:  # keep prompt bounded
            name = sec.get("name", "?")
            status = sec.get("status", "?")
            parts.append(f"\n  Secțiune: '{name}' [{status}]")
            for line in (sec.get("lines") or [])[:15]:
                t = line.get("type", "?")
                old_t = (line.get("old_text") or "").strip()
                new_t = (line.get("new_text") or "").strip()
                if t == "remove":
                    parts.append(f"    - {old_t}")
                elif t == "add":
                    parts.append(f"    + {new_t}")
                elif t == "replace":
                    parts.append(f"    - {old_t}")
                    parts.append(f"    + {new_t}")

    if not parts:
        return "Diferența nu conține modificări semnificative."

    return "\n".join(parts)
