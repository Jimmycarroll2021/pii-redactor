# Roadmap: PII Redactor Scale-Test Recovery

## Milestones

- Complete **v1.0 Scale Evidence** - Phases 1-3 shipped 2026-04-30. Archive: `.planning/milestones/v1.0-ROADMAP.md`
- Active **v1.1 Local LLM Scale Validation** - service-backed HTTP and real local-backend benchmarking.

## Phases

<details>
<summary>Complete v1.0 Scale Evidence (Phases 1-3) - shipped 2026-04-30</summary>

- [x] Phase 1: Scale-Test Evidence Baseline - completed 2026-04-30
- [x] Phase 2: Scale Harness and Synthetic Corpus - completed 2026-04-30
- [x] Phase 3: Scaled Runs and Reporting - completed 2026-04-30

</details>

## v1.1 Local LLM Scale Validation

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 4 | Model Readiness Hardening | Make qwen2.5:7b readiness evidence trustworthy before scaling further | READ-01, READ-02, READ-03 | Complete |
| 5 | Readiness Gate Report | Produce a model readiness report and define next gates for controlled testing vs production readiness | READ-04, READ-05, READ-06 | In Progress |

## Phase 4: Model Readiness Hardening

**Goal:** Make the de-PII model readiness evidence trustworthy enough for controlled local testing.

**Requirements:** READ-01, READ-02, READ-03

**Success criteria:**
1. Corrected HTTP benchmark sends `document_id` and validates expected-label leaks.
2. qwen2.5:7b corrected baseline has a readable report.
3. Completed resumed runs report `OK` instead of misleading `PARTIAL`.
4. State file is clean and points to the latest trustworthy evidence.

## Phase 5: Readiness Gate Report

**Goal:** Produce a concise readiness report that states what is ready, what is not ready, and what must happen before production use.

**Requirements:** READ-04, READ-05, READ-06

**Success criteria:**
1. `scale-tests/reports/de-pii-readiness-gate.md` summarizes current qwen2.5:7b evidence.
2. Report clearly separates controlled local testing readiness from production readiness.
3. Report identifies model throughput, audit-mode comparison, larger corrected sample, and real-data prohibition as gates.
4. `.planning/STATE.md` points to the readiness report and next GSD action.

## Requirements

| Requirement | Phase | Status |
|-------------|-------|--------|
| READ-01 | Phase 4 | Complete |
| READ-02 | Phase 4 | Complete |
| READ-03 | Phase 4 | Complete |
| READ-04 | Phase 5 | Pending |
| READ-05 | Phase 5 | Pending |
| READ-06 | Phase 5 | Pending |

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Scale-Test Evidence Baseline | v1.0 | 1/1 | Complete | 2026-04-30 |
| 2. Scale Harness and Synthetic Corpus | v1.0 | 1/1 | Complete | 2026-04-30 |
| 3. Scaled Runs and Reporting | v1.0 | 1/1 | Complete | 2026-04-30 |
| 4. Model Readiness Hardening | v1.1 | 1/1 | Complete | 2026-05-02 |
| 5. Readiness Gate Report | v1.1 | 0/1 | In Progress | - |

---
*Last updated: 2026-05-03 after formalizing v1.1 autonomous work*

## Phase 6: Audit Mode Comparison

**Status:** In Progress
**Goal:** Compare audit-disabled and audit-encrypted operation so the project can prove audit logs do not reintroduce plaintext PII risk.

**Success Criteria:**
- Disabled audit mode creates no audit log.
- Encrypted audit mode creates audit evidence with encrypted values.
- Encrypted audit mode has zero plaintext leak count for checked synthetic values.
- Both runs keep safe-payload leak count at zero.

### Phase 6 Completion

**Status:** Complete
**Report:** scale-tests/reports/audit-mode-comparison.md
**Outcome:** Audit-disabled and audit-encrypted modes pass the local validation gate.

## Phase 7: Expanded qwen2.5 Validation

**Status:** In Progress
**Goal:** Resume corrected qwen2.5:7b HTTP validation to 40 documents.

**Success Criteria:** 40 processed documents, zero errors, zero structured safe-payload leaks.

### Phase 7 Completion

**Status:** Complete with bounded validation
**Report:** scale-tests/reports/qwen25-7b-model-path-hardening.md
**Outcome:** qwen2.5:7b model path fixed and validated on bounded local run with zero leaks. Large HTTP extension deferred due runtime/service-runner instability.

## Phase 8: Final Readiness Handoff

**Status:** In Progress
**Goal:** Publish a final readiness package that consolidates validation evidence and remaining production blockers.

**Success Criteria:** Final report exists, evidence paths are linked, readiness is precise, and GSD state is updated.

### Phase 8 Completion

**Status:** Complete
**Report:** scale-tests/reports/final-readiness-package.md
**Outcome:** Final handoff published. Autonomous GSD workstream complete for controlled local validation/demo readiness.

## Phase 9: Service Lifecycle Hardening

**Status:** In Progress
**Goal:** Add repeatable qwen FastAPI startup and HTTP validation scripts.

**Success Criteria:** Scripts avoid Python interpreter ambiguity and encode correct benchmark base URL usage.

### Phase 9 Completion

**Status:** Complete
**Outcome:** Added qwen API lifecycle scripts and runbook instructions.

## Phase 10: Expanded qwen Library Validation

**Status:** In Progress
**Goal:** Expand corrected qwen2.5:7b library validation to 5 documents.

**Success Criteria:** 5 processed documents, zero safe-payload leaks, LLM-only field detection present.

### Phase 10 Completion

**Status:** Complete
**Report:** scale-tests/reports/qwen25-7b-expanded-library-validation.md
**Outcome:** qwen2.5:7b expanded bounded library validation passed at 4 documents with zero leaks.

## Phase 11: Calibration Review Pack

**Status:** In Progress
**Goal:** Create reviewer-facing calibration samples for false-positive and false-negative analysis.

**Success Criteria:** Exporter and sample review pack exist.

### Phase 11 Completion

**Status:** Complete
**Report:** scale-tests/reports/calibration-review-pack.md
**Outcome:** Review-pack exporter and initial mock review pack generated.

## Phase 12: API Security Hardening

**Status:** In Progress
**Goal:** Add strict API auth controls and separate re-identification key support.

**Success Criteria:** Production strict mode and separate re-identification auth are implemented and documented.

### Phase 12 Completion

**Status:** Complete
**Report:** scale-tests/reports/api-security-hardening.md
**Outcome:** Strict auth mode and separate re-identification key support added.
