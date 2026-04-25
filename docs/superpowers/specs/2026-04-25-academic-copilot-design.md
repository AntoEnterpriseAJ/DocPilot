# UC 3.3 — Academic Copilot (per-section AI rewrite)

## Goal
Let a professor select a single FD section, type an instruction
("reformulate ca să includă AI", "shorten to 5 bullet points",
"include the new transversal competency CT4"), and get a Claude-generated
rewrite that they can Accept or Refine. No persistent state on the server.

## Surfaces
1. **Standalone page** at `/copilot` — paste/upload section text, type
   instruction, see proposal, accept/refine.
2. **Bolted into Template Shifter result** — each section in the report
   gets an "✨ Improve" button that opens an inline rewrite panel using the
   same endpoint.

## Backend
**`POST /api/documents/rewrite-section`**

```json
{
  "section_heading": "8.1 Tematica activităților de curs",
  "current_text": "...",
  "instruction": "reformulează ca să includă noțiuni de AI",
  "course_context": {                  // optional
    "course_name": "Analiza matematică I",
    "program": "Matematică informatică",
    "competencies": ["C1 ...", "CT2 ..."]
  }
}
```

Response:
```json
{ "proposed_text": "...", "rationale": "1-2 sentence explanation in Romanian." }
```

Errors:
- 400 if `current_text` and `instruction` are both empty.
- 503 if `ANTHROPIC_API_KEY` is unset (Copilot is purely LLM-driven; no
  deterministic fallback that would mislead the user).

Implementation:
- New file [backend/services/copilot_service.py](backend/services/copilot_service.py)
  with `rewrite_section(payload) -> {"proposed_text", "rationale"}`.
- Uses `claude_service._get_client()`, `_MODEL`, `_MAX_TOKENS`.
- Forced tool_use with a tiny schema `{proposed_text, rationale}` so we
  never have to parse free-form prose.
- New schema [backend/schemas/copilot.py](backend/schemas/copilot.py).

## Frontend
- Service `copilot.service.ts` with `rewriteSection(req): Observable<resp>`.
- Standalone page `copilot/copilot-page.component.*` — three textareas
  (heading, current text, instruction) + Generate + result panel with
  Accept (copies to current text + clears proposal) / Refine (focus
  back on instruction with previous proposal kept as context).
- Nav link "🤖 Copilot" added to [nav.component.ts](frontend-hackathon/src/app/shared/nav/nav.component.ts).
- Lazy route `/copilot`.
- In Template Shifter result, each match row gets an "✨ Improve" button
  → opens the same panel inline, prefilled with the new heading + a
  reasonable seed text.

## Tests
- `tests/test_copilot_service.py` — happy path (mock Claude), empty
  inputs raise.
- `tests/test_rewrite_section_api.py` — 400 on empty, 503 on missing
  API key, 200 with mocked client.

## Out of scope (v1)
- Tables (we operate on plain text only).
- Multi-turn server-side memory (frontend chains current_text manually).
- Streaming.
- Validating against academic guard rules (UC 3.4 will).
