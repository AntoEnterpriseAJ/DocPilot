# Studio shell — Per-mode panel designs

**Date:** 2026-04-25
**Status:** Design (pre-implementation)
**Companion to:** [2026-04-25-studio-shell-design.md](2026-04-25-studio-shell-design.md)

## Locked design decisions

These were the three open questions from the brainstorm. Locked in for the
recommended path so implementation can proceed without further round-trips:

1. **Inputs are chips, not file pickers** inside tools.
   File pickers only exist in the Explorer's "Drop new files" zone and in the
   first-run empty state. Once a doc is in the Case, every tool binds to it
   via a chip dropdown that lists Case docs filtered by kind. This is the
   single biggest cohesion win — it's what makes the shell feel like one app
   instead of five.
2. **Validator is one combined view** (Format + Numeric + Bibliography) with
   a single score and three collapsible groups. The three existing endpoints
   stay separate on the backend; the frontend fans out and merges. Gives the
   prof one number to react to.
3. **Chat is text-only for v1**, but every AI message can carry a structured
   `actions[]` array that the renderer turns into buttons. v1 ships with one
   action kind: `open_tab` (jump to a tool tab). Apply-patch actions are
   stubbed (button shows, click toasts "coming soon"). This keeps v1 honest
   without committing to a full patch protocol.

## Universal anatomy of a tool tab

Every tool tab follows the same skeleton so users learn it once:

```
┌─ Tab title bar ───────────────────────────────────────────────┐
│  <icon> <Tool> · <input-summary>            [Re-run] [✕]      │
├─ Inputs strip (chips) ────────────────────────────────────────┤
│  Inputs:  [📄 FD_2025.docx ▾]  [📕 PI_2026.pdf ▾]             │
├─ Action bar (tool-specific) ──────────────────────────────────┤
│  [ Run ]  [ Export ]  ⚙ Options                                │
├─ Body (mode-specific) ────────────────────────────────────────┤
│                                                               │
│                                                               │
├─ Footer ──────────────────────────────────────────────────────┤
│  ⏱ telemetry   ✨ Send result to chat                          │
└───────────────────────────────────────────────────────────────┘
```

Rules that apply to every tab:

- **Inputs strip** — chips show docs from the Case bound to this tool. Click
  a chip → dropdown of Case docs of the right kind, plus "Add new…" which
  opens the file picker. Empty slot reads "Drop FD here ▾".
- **Re-run** is always present in the title bar.
- **Send result to chat** in the footer attaches the latest result as a
  context chip on the chat rail.
- **Skeleton-first**: tab opens immediately with a skeleton; results
  populate when ready. No modal spinners, no blocking.

## 0. Empty state (no docs in Case)

The center pane when the Case is empty. Replaces today's home page.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│            ⤓                                                │
│                                                             │
│      Drop your documents here                               │
│      or click to browse                                     │
│                                                             │
│      Accepted: .pdf  .docx                                  │
│                                                             │
│   ─────────  or start from a sample  ─────────              │
│                                                             │
│   [📄 Sample FD]   [📕 Sample Plan]   [📐 Sample Template]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- Drag-target is the whole center pane, not just the box.
- Sample chips load fixtures from `backend/mock-data/` so a brand-new user
  can demo the whole flow in 10 seconds.
- Status bar reads "Case: empty · drop a document to start".

## 1. Document tab (preview)

Open by double-clicking a doc in the Explorer. Per-doc, not per-tool.

```
┌─ FD_2025.docx ──────────────────────────────────────[✕]──┐
│  [👁 Preview] [🧾 Parsed] [🧪 Raw text]    [⬇ Download]   │
├──────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────┬─ Outline ──────┐ │
│  │                                    │ 1. Date despre │ │
│  │   (PDF.js or rendered docx HTML)   │    program     │ │
│  │                                    │ 2. Date despre │ │
│  │   1. Date despre program           │    disciplină  │ │
│  │   ...                              │ 3. Timp total  │ │
│  │                                    │ ...            │ │
│  │                                    │                │ │
│  └────────────────────────────────────┴────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

- **Three view modes**: Preview (visual), Parsed (collapsible JSON tree),
  Raw text (monospace).
- **Outline** is sticky-right, collapsible. Built from the parsed sections.
- **Selecting text** shows a floating action bar: ✨ Improve · 🔍 Explain ·
  📋 Quote in chat. Improve is the v1 stub (toast); Quote pushes selection
  to the chat composer as a quoted block.
- **No editing in v1.** It's a viewer.

## 2. Sync (FD ↔ Plan)

```
┌─ Sync · FD_2025 ↔ PI_2026 ─────────────────────────[✕]───┐
│  Inputs:  [📄 FD_2025.docx ▾]  [📕 PI_2026.pdf ▾]         │
│  [ Run ]  [ Export PDF ]                                  │
├──────────────────────────────────────────────────────────┤
│  Score header:  ✓ 9 match · ⚠ 2 mismatch · ✗ 1 missing   │
│  Filter: [ All ] [ Mismatches ] [ Missing ]               │
│ ──────────────────────────────────────────────────────── │
│  ┌────────────────┬───────────┬───────────┬────────────┐ │
│  │ Field          │ Plan      │ FD        │ Status     │ │
│  ├────────────────┼───────────┼───────────┼────────────┤ │
│  │ Denumirea      │ Analiza … │ Analiza … │   ✓        │ │
│  │ Credite        │     5     │     5     │   ✓        │ │
│  │ Tip evaluare   │  Examen   │ Colocviu  │   ⚠ [Apply]│ │
│  │ Titular curs   │     —     │ Conf. P.  │   ✗        │ │
│  └────────────────┴───────────┴───────────┴────────────┘ │
│                                                          │
│  Click any row → side drawer:                            │
│    • field path · plan value · fd value                  │
│    • [Apply Plan value to FD] (queues a stub patch)      │
│    • [Ask chat to justify this difference]               │
└──────────────────────────────────────────────────────────┘
```

- Default sort: status descending (worst first).
- Apply-patch actions are stubbed in v1 (toast "queued — coming soon").
- The score header drives the Status bar's Sync indicator.

## 3. Migrate (Template Shifter — restyled)

```
┌─ Migrate · FD_2025 → Template_2026 ────────────────[✕]───┐
│  Inputs:  [📄 Old FD ▾] [📐 Template ▾] [📕 Plan opt. ▾]  │
│  [ Run ]  [ ⬇ Download migrated docx ]                    │
├──────────────────────────────────────────────────────────┤
│  Pipeline:  ████████░░  85% — applying admin fields      │
│              parse · map · fill · admin · finalize       │
│ ──────────────────────────────────────────────────────── │
│  Section mapping  (legend: ✅ exact ⚖ fuzzy ✨ AI ⛔ stub) │
│  ┌──────────────────────────────────────────────────────┐│
│  │ ✅  1. Date despre program   ← 1. Date despre prog.  ││
│  │ ⚖   2. Informații despre …   ← 2. Date despre disc.  ││
│  │ ✨  3. Buget de timp pe sem. ← 3. Timpul total …     ││
│  │ ⛔  8.3 Plan de laborator    (placeholder)           ││
│  │ ✅  10. Evaluare             ← 10. Evaluare          ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  Right-click row →  📂 Open old · 📂 Open new ·           │
│                     ✨ Improve (stub) · 💬 Discuss in chat│
│                                                          │
│  ▾ Admin auto-fill (3 fields populated from Plan)         │
└──────────────────────────────────────────────────────────┘
```

- Pipeline strip exposes the multi-step nature so the bar isn't a black box.
- Mapping rows grouped by confidence by default; toggle "preserve template
  order" reads top-to-bottom like the new doc.
- Hovering a mapping row underlines the corresponding section in any open
  source-doc tab (cross-tab highlight via shared `highlightSectionId`
  signal in CaseStore).
- Download CTA stays sticky in the action bar after a successful run.

## 4. Drafter (FD from Plan)

```
┌─ Draft FD · Plan_2026 → "Analiza matematică I" ────[✕]───┐
│  Inputs:  [📕 Plan_2026.pdf ▾]  Course: [Analiza … ▾]     │
│  [ Generate draft ]  [ ⬇ Download .docx ]                 │
├──────────────────────────────────────────────────────────┤
│  Source legend:  📕 Plan  ✏ User  ✨ AI  ⊘ Empty          │
│  ▾ Missing fields (2):  Titular curs · Bibliografie       │
│ ──────────────────────────────────────────────────────── │
│  Section preview (live):                                  │
│  ┌──────────────────────────────────────────────────────┐│
│  │ 1. Date despre program        [📕 from Plan]         ││
│  │    Universitatea Transilvania din Brașov             ││
│  │    Facultatea: Matematică și Informatică             ││
│  │                                                      ││
│  │ 2. Date despre disciplină     [📕 + ⊘ partial]       ││
│  │    Denumirea: Analiza matematică I                   ││
│  │    Titular curs: ⊘ (needed)  [✨ Suggest]            ││
│  │                                                      ││
│  │ 6. Competențe specifice       [✨ AI suggested]      ││
│  │    ┌────────────────────────────────────────────┐    ││
│  │    │ Suggested by AI (low confidence)           │    ││
│  │    │ [Accept] [Edit] [Reject]                   │    ││
│  │    └────────────────────────────────────────────┘    ││
│  └──────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

- Source badges per section so the prof always sees what's verified vs guess.
- Missing-fields tray sits above the action bar — can't pretend the doc is
  complete.
- Accept/Edit/Reject inline on every AI block; Edit opens an inline editor.

## 5. Diff (Syllabus Diff)

```
┌─ Diff · FD_2025 ↔ FD_2026 ─────────────────────────[✕]───┐
│  Inputs:  [📄 Left ▾]  [📄 Right ▾]                       │
│  View: [⏸ Side-by-side] [📜 Inline] [📊 Summary]          │
│  🔒 Sync scroll                                          │
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────┬───────────────────────────┐│
│  │ FD_2025 (left)           │ FD_2026 (right)           ││
│  ├──────────────────────────┼───────────────────────────┤│
│  │ 8. Conținuturi           │ 8. Conținuturi            ││
│  │ 8.1 Tematica curs        │ 8.1 Plan de curs    ⚖     ││
│  │   - Curs 1: Mulțimi …    │   - Săpt. 1: Mulțimi … +  ││
│  │   - Curs 2: Limite …     │   - Săpt. 2: Limite … ✓   ││
│  │                          │ 8.3 Plan de laborator +   ││
│  │ 10. Evaluare             │ 10. Evaluare        ✓     ││
│  │   Examen 60%             │   Examen 50%        ⚠     ││
│  └──────────────────────────┴───────────────────────────┘│
│                                                          │
│  ▾ Summary (Explain in plain language)                   │
│    +2 sections added · −1 removed · 4 reworded           │
│    ⚠ Examen pondere: 60% → 50% (over budget by 10%)      │
└──────────────────────────────────────────────────────────┘
```

- Three view modes share the same data; toggle is instant.
- Summary tab calls `/api/documents/explain-diff` and renders the narrative.
- Click any change → "Discuss this change in chat" opens chat rail with the
  selection quoted.

## 6. Validate (combined: Format + Numeric + Bibliography)

```
┌─ Validate · FD_2025 ──────────────────────────────[✕]────┐
│  Inputs:  [📄 FD_2025.docx ▾]                             │
│  [ Re-run all ]                                           │
├──────────────────────────────────────────────────────────┤
│  Score: 7.5 / 10    ✅ Format · ⚠ Numeric · ⚠ Biblio     │
│ ──────────────────────────────────────────────────────── │
│  ▾ Format & Missing fields  (12/12 ✓)                    │
│      ✓ Heading 1 style on all sections                   │
│      ✓ Footer present                                    │
│      ✓ All required sections present                     │
│                                                          │
│  ▾ Numeric consistency  (3/4 ✓)                          │
│      ✓ Ore/săpt = 4 = curs(2) + sem(2)                   │
│      ⚠ Ponderi evaluare = 110% ≠ 100%                    │
│         💡 Suggested fix: scale to 100%   [Apply (stub)] │
│                                                          │
│  ▾ Bibliography  (2/3 ✓)                                 │
│      ✓ Trif 2021 — within 5 years                        │
│      ✓ Nicolescu 2019 — within 5 years                   │
│      ⚠ Rudin 1976 — older than 5 years                   │
│         🔍 Find newer edition (AI)        [Search (stub)]│
└──────────────────────────────────────────────────────────┘
```

- Frontend fans out three calls in parallel, merges into one view.
- One score derived from `(passed / total)` across all three groups.
- Status bar pulls its three indicators directly from this tab's last run.
- Apply / Search buttons are v1 stubs.

## 7. Chat rail (right side, always visible, collapsible)

```
┌─ Chat ─────────────────────────────────────[─][⛶]─┐
│  Context: @FD_2025.docx · @Migration result        │
│  [✕ remove chip]                                   │
│ ─────────────────────────────────────────────────  │
│                                                    │
│   🧑  Why is the Examen pondere flagged?           │
│                                                    │
│   🤖  The new template caps the final exam at 50%. │
│       Yours is 60%. Suggested fix: shift the       │
│       extra 10% to Activitate continuă.            │
│       [📂 Open Validator] [✨ Apply (stub)]         │
│                                                    │
│   🧑  __________________________  [🔍 ✨ 📋]        │
│   [📎 attach doc]                       [Send ↵]   │
└────────────────────────────────────────────────────┘
```

- **Context chips** at the top show what's actually in the prompt; remove a
  chip to scope down. Active tab is auto-attached unless removed.
- **Quick actions** (🔍 Explain · ✨ Improve · 📋 Summarize) are pre-filled
  prompts using the active tab's selection or contents.
- **Inline action buttons** on AI replies. v1 supports `open_tab` for real;
  `apply_patch` shows the button but toasts "coming soon".
- **Collapsible** to a slim 32 px rail (icon + unread dot). Never hidden
  entirely — discoverability matters.
- **No history persistence in v1** — clears on reload.

## 8. Explorer (left rail, always visible)

```
┌─ Explorer ─────────────────────────────[+][⚙]─┐
│  CASE: Analiza matematică I — 2026  [💾 Save] │
├───────────────────────────────────────────────┤
│  ▾ DOCUMENTS                                  │
│    ▾ Fișa Disciplinei                         │
│       📄 FD_2025.docx       ✓ ✓ ✓            │
│    ▾ Plan de Învățământ                       │
│       📕 PI_2026.pdf        ✓                │
│    ▾ Template                                 │
│       📐 Template_2026.docx                   │
│    ▾ Drop new files here ⤓                    │
│                                               │
│  ▾ TOOLS                                      │
│       🔍 Diff                                 │
│       🔗 Sync                                 │
│       🔄 Migrate                              │
│       📝 Draft                                │
│       ✅ Validate                              │
│                                               │
│  ▾ RESULTS (this session)                     │
│       🔄 Migration · 2m ago    [Open]         │
│       🔗 Sync check · 5m ago   [Open]         │
└───────────────────────────────────────────────┘
```

- Status chips next to each doc: parsed · classified · validated.
- Tools greyed out unless their required input kinds are present in the Case.
  Hover greyed tool → tooltip "Add a Template to enable Migrate".
- Save button is a stub in v1 (toast "Local save coming soon"); the icon is
  there to signal future intent.

## 9. Status bar (bottom, always visible)

```
┌──────────────────────────────────────────────────────────────┐
│ ●FD_2025 │ Sync ✓ │ Numeric ⚠ 110% │ Biblio ⚠ Rudin │ ✨ key │
└──────────────────────────────────────────────────────────────┘
```

- Click any indicator → opens that tool's tab pre-bound to the active doc.
- ✨ key indicator: green if `ANTHROPIC_API_KEY` is set, amber otherwise.
  Click → opens Settings sheet.
- Left side shows active tab name + a coloured dot for the active doc.

## 10. Command palette (Ctrl+K)

```
┌─ ⌘K  ─────────────────────────────────────────┐
│  > _________________________________          │
├───────────────────────────────────────────────┤
│  COMMANDS                                     │
│   🔍 Open Diff                       Ctrl+1   │
│   🔗 Open Sync                       Ctrl+2   │
│   🔄 Open Migrate                    Ctrl+3   │
│   📝 Open Draft                      Ctrl+4   │
│   ✅ Open Validate                    Ctrl+5   │
│   📂 Add document…                            │
│   💾 Save case (stub)                         │
│   ⚙ Settings                                  │
│                                               │
│  RECENT DOCUMENTS                             │
│   📄 FD_2025.docx                             │
│   📕 PI_2026.pdf                              │
└───────────────────────────────────────────────┘
```

- Fuzzy match on commands + doc names.
- Selecting a doc opens its Document tab.
- `Esc` closes; arrows navigate; `Enter` activates.

## 11. Settings sheet (slide-over)

```
┌─ Settings ───────────────────────────────────[✕]─┐
│                                                  │
│  ANTHROPIC API KEY                               │
│   ✨ Detected via env var (read-only in v1)      │
│                                                  │
│  THEME                                           │
│   ( • ) Light    (   ) Dark                       │
│                                                  │
│  SAMPLE DATA                                     │
│   [Load sample case]                             │
│                                                  │
│  ABOUT                                           │
│   Studio v0.1 · backend at 127.0.0.1:8001        │
└──────────────────────────────────────────────────┘
```

- Slides in from the right (over the chat rail).
- v1 is read-mostly; the key entry UI is intentionally deferred.

## Cross-cutting principles (re-stated)

1. **One source of truth** — the Case in CaseStore.
2. **Inputs are chips** in tools, file pickers only at the boundary.
3. **Results are tabs**, never modals; skeleton-first.
4. **Every result has a path to chat** via the footer "Send to chat".
5. **AI suggestions are actionable inline** (Accept / Edit / Reject).
6. **Color language is reserved**: 🟢 valid · 🟡 partial · 🔴 error · 🟣 LLM.
7. **Keyboard everywhere**: `Ctrl+K`, `Ctrl+1..5`, `Ctrl+W`, `Esc`.

## Responsive behavior (note for implementer)

- ≥ 1280 px: full 3-pane shell as drawn.
- 960–1279 px: chat rail collapses to slim icon by default; tap to expand
  as overlay.
- < 960 px: explorer also collapses to icon; layout stacks. (Not a v1
  target, but the CSS grid should not break.)

## Open question (low priority)

- Should the chat rail history persist across reloads via `localStorage`?
  v1 says no (KISS); flag if you'd rather have it.
