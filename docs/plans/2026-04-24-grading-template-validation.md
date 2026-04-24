# Generic Template Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a backend-first generic template validator that accepts a template payload, schema, and guards, using a grading example only as test data.

**Architecture:** Keep extraction separate from validation. Add a small generic validation schema and service that evaluates schema-level checks and declarative guards against any template dict, then prove it with a grading example in pytest before integrating any route or frontend surface.

**Tech Stack:** FastAPI, Pydantic, pytest

---

### Task 1: Add failing tests for generic schema-and-guards validation

**Files:**
- Create: `backend/tests/test_template_validator.py`
- Modify: `backend/requirements.txt`

**Step 1:** Add pytest to backend dependencies.

**Step 2:** Write failing tests covering:
- valid template passes with provided schema and guards
- schema type mismatch fails
- range guard fails
- sum-equals guard fails
- failed guards return machine-readable codes

**Step 3:** Run `pytest backend/tests/test_template_validator.py -q` and verify the tests fail because the validator module does not exist yet.

### Task 2: Implement validation models and generic guard runner

**Files:**
- Create: `backend/schemas/template_validation.py`
- Create: `backend/services/template_validator.py`

**Step 1:** Add a small schema for:
- guard violation
- suggestion option
- validation result

**Step 2:** Implement a `validate_template` service that evaluates deterministic guards against a plain dict template.

**Step 3:** Return violations with machine-readable codes and field references.

### Task 3: Add optional suggestion generation from guard failures

**Files:**
- Modify: `backend/services/template_validator.py`

**Step 1:** Allow guards to carry optional suggestion metadata that can be surfaced with failed violations.

**Step 2:** Return up to three suggestions, each with explanation and patch payload.

**Step 3:** Keep the suggestion layer separate from hard validation so Claude can replace or extend it later.

### Task 4: Verify focused backend behavior

**Files:**
- Test: `backend/tests/test_template_validator.py`

**Step 1:** Run `pytest backend/tests/test_template_validator.py -q` and verify all tests pass.

**Step 2:** If needed, run a narrow import check on the backend package.