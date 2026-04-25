# Plan — Studio shell rollout

**Spec:** [2026-04-25-studio-shell-design.md](../specs/2026-04-25-studio-shell-design.md)

Five short phases. Each phase is independently demoable and committable, so
we can stop early if time runs out.

## Phase 0 — Move existing pages to /legacy/* (safety net)
**Why:** every subsequent phase changes routing; we never want to break the
current demo while building the new shell.

- Edit [app.routes.ts](frontend-hackathon/src/app/app.routes.ts) so that
  every existing route is also reachable as `/legacy/<name>` (keep both
  paths alive temporarily).
- Add a "Legacy mode" link in the nav that toggles between Studio and
  the old multi-page nav.

**Done when:** `/legacy/diff`, `/legacy/sync`, `/legacy/draft`,
`/legacy/template-shift` all render exactly as today, and the old `/`
home still works.

## Phase 1 — CaseStore + 3-pane shell skeleton
**Why:** lay the foundation so tools can plug into it.

- Create `studio/case.store.ts` (signals: `documents`, `tabs`, `activeTabId`,
  `chat`, `toolResults`).
- Create `studio/studio-shell/` component with CSS-grid 3-pane layout
  (Explorer | Main | Chat). Splitters can be CSS-only for now.
- Replace `/` route with the Studio shell (legacy home moves to `/legacy`).
- Empty states for all three panes.

**Done when:** loading `/` shows the 3-pane shell, empty everywhere, no
console errors.

## Phase 2 — Document intake (Explorer) + tabs
**Why:** the central interaction loop — upload once, see everywhere.

- Explorer: drag-drop zone + file picker, lists uploaded docs grouped by
  auto-classified type (FD / Plan / Template / Other). Reuse
  `/api/documents/parse` for classification.
- Document tabs: click an explorer item → opens a tab with a basic
  preview (PDF.js for PDFs, formatted text for docx via existing
  `text_extractor`). Close, reorder, switch.
- Status chips on each doc (`parsed`, `validated`).

**Done when:** I can drop two docx + one pdf, see them in the explorer
correctly classified, click any of them and see a tab open.

## Phase 3 — Embed first tool (Template Shifter as exemplar)
**Why:** prove that an existing tool can read inputs from CaseStore and
emit results into the cache instead of using its own File inputs.

- Refactor `TemplateShiftPageComponent` to accept inputs from
  `CaseStore` (active FD doc + active Template doc).
- Add a "Migrate to template" command in the Tools section of the Explorer.
- Migration runs → opens a Migration tool tab with the existing report UI;
  result is cached in `CaseStore.toolResults.shift`.
- Keep `/legacy/template-shift` working unchanged.

**Done when:** I drop two docx in the explorer, click "Migrate to template",
a new tab opens with the report and download link without me re-uploading
anything. Closing and reopening the tab shows the cached report.

## Phase 4 — Chat rail with active-tab context
**Why:** the chat is the soul of the app and currently homeless.

- Move the chat from the legacy home into the right rail.
- Composer shows active-tab context as a chip (e.g. "@FD_2025.docx" or
  "@Migration result").
- Three quick-action chips: 🔍 Explain, ✨ Improve (stub), 📋 Summarize.
- Chat history persists across tab switches (lives in `CaseStore.chat`).

**Done when:** I can open a doc tab, send "summarize this" in the chat,
and the request automatically includes the active doc.

## Phase 5 — Embed remaining tools + status bar + Ctrl+K
**Why:** parity with legacy + the polish that sells the demo.

- Embed Diff, Sync, Drafter using the same pattern as Phase 3.
- Status bar at the bottom showing live indicators for the active doc
  (sync ✓/⚠, numeric ✓/⚠, biblio ✓/⚠).
- `Ctrl+K` command palette with 6 commands (one per tool + open doc + new
  case).
- Toast region bottom-right.
- Remove `/legacy/*` once everything has parity (decide at end).

**Done when:** every tool works inside the shell, status bar updates as
you switch tabs, command palette can launch any tool.

## Verification at each phase
- `npx ng build` succeeds (no TS errors).
- Manual smoke per the "Done when" criterion.
- For Phase 3 onward, an end-to-end click-through with the existing
  mock docx pair (`backend/mock-data/template-shift/`) so we know the
  whole flow still works.

## Effort estimate
Each phase ≈ 1-3 hours of focused work. Phases 0-2 are mostly Angular
plumbing; Phase 3 is the riskiest (proves the embedding pattern); 4-5
are refinement.

## Out of scope (don't get sucked in)
- Backend changes — none required for any phase.
- Auth, multi-user, persistence to a real DB.
- Re-skinning every tool with the new color language (Phase 5+ polish).
