# Automatic Guards Template Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an upload-to-template flow that returns a generated template, schema, and Claude-assisted guard suggestions, then let the Angular frontend edit and export the resulting guards file for the auto-corrector.

**Architecture:** Keep document extraction separate from template drafting. Reuse the existing parse pipeline to obtain typed extracted fields, map those fields into a draft template/schema bundle, then call Claude with a structured tool to propose per-field guard defaults and selectable alternatives. In the frontend, add a focused review surface on the existing home page that uploads a document, renders the generated fields and guard options, lets the user edit guard parameters, and exports the finalized guard list as JSON.

**Tech Stack:** FastAPI, Pydantic, pytest, Angular 19, HttpClient, RxJS

---

### Task 1: Add failing backend tests for the generation bundle

**Files:**
- Modify: `backend/tests/test_claude_service.py`
- Modify: `backend/tests/test_validation_api.py`

**Step 1:** Add a Claude service test for a new structured method that returns per-field guard suggestions and alternatives.

**Step 2:** Add an API test for a new endpoint that returns `template`, `schema`, `guard_drafts`, and `guards` for a parsed document.

**Step 3:** Run `pytest backend/tests/test_claude_service.py backend/tests/test_validation_api.py -q` and verify the new tests fail for missing functionality.

### Task 2: Implement backend draft generation and Claude guard suggestions

**Files:**
- Modify: `backend/schemas/template_validation.py`
- Modify: `backend/services/claude_service.py`
- Create: `backend/services/template_drafts.py`
- Modify: `backend/routers/documents.py`

**Step 1:** Add response/request models for guard draft options and the generated template bundle.

**Step 2:** Implement a small service that converts extracted fields into:
- a plain `template` dict
- a `schema` dict inferred from field types
- baseline deterministic guard options per field

**Step 3:** Add a structured Claude call that can refine those baseline options into recommended per-field guard drafts.

**Step 4:** Add a new FastAPI endpoint that accepts an uploaded file, reuses the existing extraction flow, and returns the full generation bundle.

### Task 3: Add failing frontend tests or compile-targeted checks for the review flow

**Files:**
- Modify: `frontend-hackathon/src/app/home/home.component.spec.ts`
- Create: `frontend-hackathon/src/app/home/home.models.ts`
- Create: `frontend-hackathon/src/app/home/home.service.ts`

**Step 1:** Add a focused component test or narrow compile assumption for rendering generated guard drafts.

**Step 2:** Run the narrow Angular test or build command and verify the new surface is not implemented yet.

### Task 4: Implement the frontend upload, review, and export surface

**Files:**
- Modify: `frontend-hackathon/src/app/home/home.component.ts`
- Modify: `frontend-hackathon/src/app/home/home.component.html`
- Modify: `frontend-hackathon/src/app/home/home.component.scss`
- Create: `frontend-hackathon/src/app/home/home.models.ts`
- Create: `frontend-hackathon/src/app/home/home.service.ts`

**Step 1:** Replace the current mock chat behavior with an upload-driven flow that calls the new backend endpoint.

**Step 2:** Render the generated template fields and per-field guard drafts, including selectable suggested options.

**Step 3:** Let the user update guard kind, message, parameters, and inclusion state.

**Step 4:** Build a final guard JSON payload from the edited state and expose an export/download action for the auto-corrector.

### Task 5: Verify the implemented slice end-to-end

**Files:**
- Test: `backend/tests/test_claude_service.py`
- Test: `backend/tests/test_validation_api.py`
- Test: `frontend-hackathon/src/app/home/home.component.spec.ts`

**Step 1:** Run `pytest backend/tests/test_claude_service.py backend/tests/test_validation_api.py -q`.

**Step 2:** Run `npm test -- --watch=false --include src/app/home/home.component.spec.ts` or, if the test harness is brittle, run `npm run build`.

**Step 3:** Report any remaining gaps, especially around real Claude responses versus the mocked contract.