# Unified UI — "Studio" shell

**Date:** 2026-04-25
**Status:** Design (pre-implementation)
**Decision posture:** Recommended defaults assumed (IDE shell, 1-day budget,
session-only persistence with a "save case" stub). If the user wants a lighter
or different approach we can downgrade phases — see "Scope dials" below.

## Problem
Today the app is 5 unrelated pages (Home/Diff/Sync/Drafter/Template Shifter,
soon Copilot). Each re-uploads the same PDFs, results vanish on navigation,
the AI chat is stranded on the home page, and the user has no sense of "what
am I working on right now."

## Vision
A VS Code-style **Studio** shell:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Studio   • Case: Analiza matematică I — 2026 redesign     [Save]   │
├──────────────┬─────────────────────────────────────┬────────────────┤
│ EXPLORER     │  ┌───┬───┬───┬───┐                  │  AI CHAT       │
│              │  │FD │PI │TPL│ + │   ← tab strip    │                │
│ ▾ Fișa Disc. │  ├───┴───┴───┴───┤                  │  Talk to the   │
│   FD_2025.docx  │                │                  │  active doc(s) │
│ ▾ Plan       │  │   document    │                  │                │
│   PI_2026.pdf│  │   preview /   │                  │  > _____       │
│ ▾ Template   │  │   tool view   │                  │                │
│   TPL_2026.… │  │               │                  │                │
│              │  │               │                  │                │
│ ▸ TOOLS      │  └───────────────┘                  │                │
│   Diff       │  ┌──────────────────────────────┐   │                │
│   Sync       │  │ STATUS BAR: Sync ✓ • Numeric │   │                │
│   Migrate    │  │ ✓ • Bibliography ⚠            │   │                │
│   Draft      │  └──────────────────────────────┘   │                │
│   Validate   │                                      │                │
│              │                                      │                │
└──────────────┴─────────────────────────────────────┴────────────────┘
```

## Core concepts

### 1. Case (session)
A **Case** is the in-memory bag of documents you're working on, plus their
parsed forms. Default unnamed case is auto-created on first upload.
- `documents: Doc[]` — list of uploaded files (FD, PI, Template, "Other").
- `activeTabId: string | null` — which tab is foregrounded.
- `chatMessages: ChatMsg[]` — conversation, persists across tool views.
- `toolResults: { syncCheck?, numericCheck?, biblioCheck?, shiftReport?, … }` —
  cached results, so re-opening a tool shows the previous output instantly.

Persistence:
- **Phase 1**: in-memory only (Angular `signal` store, lost on refresh).
- **Phase 2 (stub)**: a "💾 Save case" button serializes the case (minus blobs)
  to `localStorage` with a name; "Open recent" lists them. Documents are kept
  as base64 in localStorage for now (small docs only).

### 2. Documents (Explorer panel)
- Auto-classified by filename + content into **FD**, **Plan de Învățământ**,
  **Template**, or **Other** (we already have document_classifier.py — wire it).
- Drag-and-drop into the explorer or onto the empty workspace.
- Each entry shows status chips: `parsed`, `validated`, `synced`, `migrated`.
- Right-click / kebab menu → "Open", "Set as primary FD", "Use as template",
  "Remove".

### 3. Tabs (center)
Two kinds of tab:
- **Document tab** — shows a preview of the doc (PDF.js for PDFs, formatted
  view for parsed JSON). Read-only in v1.
- **Tool tab** — shows the result UI of a tool (e.g. "Sync Check Report",
  "Migration Result", "Diff View"). Tool tabs auto-open when the user runs
  a command from the Explorer or command palette.

Tab affordances: drag to reorder, X to close, modified dot if there are
unsaved tweaks, middle-click to close.

### 4. Tools panel (Explorer bottom)
The 5 existing pages become commands. Clicking a tool either:
- Opens a tool tab immediately if the required docs are already in the case
  (Sync needs an FD + a Plan; Migrate needs an old FD + a new Template).
- Otherwise pops a tiny "missing inputs" prompt with file picker shortcuts.

### 5. AI Chat (right rail)
Persistent chat that always knows the **active tab's context**:
- Active doc → "Tell me about this doc", "Find the bibliography".
- Active tool result → "Explain the diff to me in human language" (wires
  through to `/api/documents/explain-diff`), "Suggest a fix for this
  numeric inconsistency".
- The chat composer has quick-action chips: 🔍 Explain selection,
  ✨ Improve this section (jumps into Copilot endpoint when reinstated).

### 6. Status bar (bottom)
Live indicators for the active doc:
- ✓/⚠/✗ Sync vs Plan
- ✓/⚠ Numeric consistency (sums, %)
- ✓/⚠ Bibliography (freshness, links)
- "Anthropic key: ●" connection dot

Clicking any indicator opens that tool's tab.

### 7. Command palette (`Ctrl+K`)
- "Run sync check"
- "Migrate FD to template"
- "Draft FD from plan"
- "Diff two documents"
- "Open document…"
- "New case"
- "Save case"

## Information architecture mapping

| Today (route) | Tomorrow (in shell) |
|---|---|
| `/` Home (chat + uploader) | Removed — chat lives in the right rail; uploader is the empty state of the Explorer |
| `/diff` Diff Analyzer | Tool command "Diff documents" → opens a Diff tool tab |
| `/sync` Sync Check | Tool command "Sync FD ↔ Plan" → opens a Sync tool tab |
| `/draft` FD Drafter | Tool command "Draft FD from Plan" → opens a Drafter tool tab |
| `/template-shift` Template Shifter | Tool command "Migrate to new template" → opens a Migration tool tab |
| (Copilot, currently reverted) | Inline rail action + tool command later |

We keep the existing pages reachable at `/legacy/diff`, `/legacy/sync`, etc.
during the migration so we never break the demo halfway through.

## Tech approach (Angular)

- New `studio/` feature folder:
  - `studio-shell/` — the 3-pane layout component (CSS grid:
    `[explorer 280px] [main 1fr] [chat 360px]`, draggable splitters).
  - `case.store.ts` — `CaseStore` service with signals for documents, tabs,
    active tab, chat, tool results. Single source of truth.
  - `explorer/` — left panel, includes Documents tree + Tools list.
  - `tabs/` — center tab bar + dynamic tab outlet that renders the right
    component for the tab type.
  - `chat-rail/` — right panel.
  - `status-bar/` — bottom strip.
- Existing tool pages become **embeddable views**: refactor each component to
  read its inputs from `CaseStore` instead of its own File inputs. We keep
  their old "page" wrappers (just thin shells) so legacy routes still work.
- `/` route becomes the Studio. Old routes move under `/legacy/*`.
- Drag-and-drop uses native `dragover/drop`.
- Keyboard shortcuts via a tiny global `KeyboardService` (`Ctrl+K`,
  `Ctrl+W` close tab, `Ctrl+Tab` next tab).

## UX details that matter

- **Empty state**: huge centered drop zone with "Drop your FD, Plan, or
  Template here — or paste from clipboard." Three example chips:
  "Try a sample case", "Open recent", "Read the use cases".
- **Optimistic feedback**: every tool button immediately opens a tab with a
  shimmer skeleton; results stream/slot in when ready. No frozen "Migrating…"
  state on the button.
- **Color language** (consistent across all tools):
  - Green = exact / valid / new
  - Amber = fuzzy / warning / changed
  - Red / muted = error / removed / placeholder
  - Purple = LLM-touched
- **Document chips** in the chat composer ("@FD_2025.docx") make it explicit
  what context is being sent. Click X to remove a chip.
- **Toast region** bottom-right for non-blocking events ("Migration ready —
  open tab", "Sync check found 2 mismatches").
- **Never lose work**: closing the last tab returns you to the empty state
  with a "Reopen last tab" toast for 10 seconds.
- **Dark theme available** but default light, matching the demo background.

## Scope dials (so the user can downgrade fast)

| Dial | Min | Recommended | Max |
|---|---|---|---|
| Layout | Single-column with collapsible panels | 3-pane grid with splitters | 3-pane + bottom panel for terminal-like log |
| Persistence | Session memory only | + "Save case" to localStorage | + backend cases collection |
| Chat context | Manual @-mentions only | Active-tab auto-context | Multi-doc auto-context, RAG |
| Tools | Reuse current pages 1:1 | Embed in tabs, share state | Rebuild each tool with the new color language |
| Command palette | Skip | `Ctrl+K` with 6 commands | Fuzzy search across docs + commands + recent results |

## Out of scope (v1)
- Real-time multi-user editing.
- A document editor (we render but don't let you change docx content here).
- Authentication / user accounts.
- Backend persistence of cases.
- Plugin/extension system.

## Risks
- Splitter ergonomics on small screens — mitigate with collapse-to-icons
  for explorer, and chat-as-overlay below 1280px.
- PDF.js bundle size — keep it lazy-loaded only when a PDF tab is opened.
- State store mutations across many tools — single `CaseStore` with signals
  + readonly accessors to avoid accidental writes.

## Success criteria
- A user uploads two docx files **once**, then runs Migrate, Diff, and
  Sync without ever re-picking a file.
- The chat sidebar can answer "what changed in this section?" while the
  Migration result tab is open.
- The page never "loses" results — closing and reopening a tool tab shows
  the cached result.


<!-- per-mode designs appended 2026-04-25 -->

