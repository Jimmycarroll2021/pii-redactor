# Retrospective

## Milestone: v1.0 - Scale Evidence

**Shipped:** 2026-04-30
**Phases:** 3 | **Plans:** 3

### What Was Built

- Created canonical scale-test workspace under `scale-tests/`.
- Documented that prior concrete scale-test artifacts were not found.
- Added deterministic synthetic corpus generation for AU government and medical identifiers.
- Added direct library and HTTP batch benchmark harnesses.
- Executed a 1,000-document mock-backend benchmark and published a report.

### What Worked

- Treating missing historical work as missing avoided false confidence.
- Keeping artifacts inside the project created a durable evidence trail.
- Separating direct-library and HTTP benchmark paths kept the first baseline runnable without infrastructure.

### What Was Inefficient

- Initial benchmark harness used stale API assumptions and needed correction against the actual `Config` and `Pipeline` APIs.
- The current milestone did not run a live service-backed HTTP benchmark because no target service/backend was started in this execution pass.

### Patterns Established

- Every scale run should produce `documents.jsonl`, `expected_labels.jsonl`, `results.jsonl`, `summary.json`, and `REPORT.md`.
- Mock-backend leak checks should distinguish structured values from LLM-only values like names and addresses.
- Service/hardware-specific performance claims belong in separate reports from direct-library mock baselines.

### Key Lessons

- GSD summaries should include exact artifact paths and benchmark numbers, not just phase intent.
- The benchmark harness must track project API shape directly; stale method names are immediate execution risks.
- Privacy reporting needs explicit scope notes so mock-backend limitations are not mistaken for full clinical recall.

## Cross-Milestone Trends

| Pattern | First Seen | Status |
|---------|------------|--------|
| Durable evidence under project tree | v1.0 | Keep |
| Synthetic-only PII scale validation | v1.0 | Keep |
| Separate mock and service-backed claims | v1.0 | Keep |
