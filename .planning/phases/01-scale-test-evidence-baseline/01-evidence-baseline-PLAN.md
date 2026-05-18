# Phase 1 Plan: Scale-Test Evidence Baseline

## Objective

Create a durable baseline for the missing PII scale-test work: document searched evidence, confirmed code-level scale support, missing historical artifacts, and the project-local artifact layout that future scale tests must use.

## Why This Phase Exists

The project has code paths that support scale testing, but no saved large-run evidence was found. Without an explicit baseline, future work will keep confusing "scale capable" with "scale proven." This phase draws that line clearly and prepares Phase 2 to rebuild the missing test system reproducibly.

## Inputs

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/phases/01-scale-test-evidence-baseline/01-CONTEXT.md`
- `.planning/phases/01-scale-test-evidence-baseline/01-RESEARCH.md`
- Existing source files referenced in the context:
  - `api/main.py`
  - `pii_redactor/config.py`
  - `README.md`

## Deliverables

### 1. `scale-tests/README.md`

Create the canonical home for future scale-test work.

Required sections:

- Purpose
- Artifact layout
- Naming convention
- Safety rules
- Reproducibility rules
- Phase ownership

Required directory contract:

- `scale-tests/fixtures/` for generated synthetic corpora and expected labels
- `scale-tests/runs/` for timestamped raw benchmark outputs
- `scale-tests/reports/` for curated summaries if separated from run folders
- `scale-tests/tools/` only if helper modules are needed later

### 2. `scale-tests/evidence-baseline.md`

Create the durable baseline report.

Required sections:

- Summary conclusion
- Searched roots
- Confirmed scale-related code traces
- Historical artifacts not found
- Non-PII artifacts intentionally excluded
- Decision: rebuild scale tests reproducibly
- Next phase handoff

The report must explicitly say that no concrete saved historical PII scale-run artifacts were found.

### 3. `.planning/STATE.md`

Update state after Phase 1 execution.

Required update:

- Mark Phase 1 as complete once deliverables exist.
- Set current focus to Phase 2.
- Record that the next action is `$gsd-plan-phase 2` or `$gsd-execute-phase 2`.

## Implementation Steps

1. Create `scale-tests/` if missing.
2. Create subdirectories:
   - `scale-tests/fixtures/`
   - `scale-tests/runs/`
   - `scale-tests/reports/`
3. Write `scale-tests/README.md` from the artifact contract above.
4. Write `scale-tests/evidence-baseline.md` using the searched evidence already gathered.
5. Update `.planning/STATE.md` only after deliverables are in place.

## Verification Checklist

- [ ] `scale-tests/README.md` exists.
- [ ] `scale-tests/evidence-baseline.md` exists.
- [ ] Baseline separates confirmed evidence from missing artifacts.
- [ ] Baseline does not claim historical scale tests passed.
- [ ] Artifact layout is explicit enough for Phase 2 to implement without more archaeology.
- [ ] No real PII is introduced.
- [ ] `.planning/STATE.md` points to Phase 2 after execution.

## Risks and Controls

| Risk | Control |
|------|---------|
| Accidentally overstating old evidence | Use only confirmed file paths and mark missing artifacts explicitly |
| Future artifacts getting lost again | Force all scale-test outputs under `scale-tests/` |
| PII leakage during future tests | Phase 1 safety rules require synthetic-only corpora |
| Phase 2 blocked by vague structure | Define directories and naming rules now |

## Acceptance Criteria

Phase 1 is complete when a maintainer can answer these questions from project-local docs alone:

1. What scale-test evidence currently exists?
2. What historical artifacts were searched for but not found?
3. Where must future scale-test inputs, outputs, and reports be stored?
4. What is the next implementation phase?

## Plan Status

Ready for `$gsd-execute-phase 1`.
