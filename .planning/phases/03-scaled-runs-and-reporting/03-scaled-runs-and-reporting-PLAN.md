# Phase 3 Plan: Scaled Runs and Reporting

## Objective

Execute reproducible synthetic scale benchmarks and publish reports that prove performance, correctness, and privacy safety for `pii-redactor`.

## Deliverables

### 1. Runbook

Create `scale-tests/RUNBOOK.md`.

Required sections:

- Prerequisites
- Generate corpus command
- Run direct library benchmark command
- Start API service command
- Run HTTP batch benchmark command
- Interpret reports
- Safety notes
- Known limitations

### 2. Report Generator

Create `scale-tests/write_report.py` if Phase 2 runners do not already write Markdown reports.

Required input:

- `summary.json`
- optional `results.jsonl`

Required output:

- `REPORT.md` with performance, correctness, safety, config, and limitations.

### 3. Benchmark Runs

Run or prepare commands for:

- Library benchmark with at least 1k generated synthetic docs.
- HTTP batch benchmark with two concurrency settings if the API service is running.

If not executing in this phase because runtime constraints apply, create a `REPORT.md` marked `NOT RUN` with exact commands to run and reason not executed.

### 4. State Updates

Update:

- `.planning/STATE.md`
- `.planning/REQUIREMENTS.md` traceability statuses if execution completes.

## Minimum Report Content

Each `REPORT.md` must include:

- Run ID and timestamp.
- Runner type and backend/model.
- Corpus manifest reference.
- Document count and error count.
- Docs/sec and estimated docs/day.
- Latency percentiles.
- Expected vs detected PII counts by category.
- Leak count and leak check surfaces.
- Audit mode and audit behavior.
- Limitations and next recommendations.

## Safety Verification

The benchmark/reporting path must check expected synthetic values against:

- redacted output
- safe spans
- safe PII table
- raw result JSONL
- Markdown report, except the controlled fixture/expected-label references if explicitly included

## Verification Checklist

- [ ] `scale-tests/RUNBOOK.md` exists.
- [ ] At least one benchmark run folder exists or a clear NOT RUN report exists.
- [ ] Reports include performance, correctness, and safety sections.
- [ ] Reports label synthetic fixture data clearly.
- [ ] No real PII is introduced.
- [ ] `.planning/STATE.md` captures latest scale status.

## Acceptance Criteria

Phase 3 is complete when the project contains reproducible benchmark commands and at least one durable report showing either executed scale results or an explicit blocked/not-run status with exact next command.

## Plan Status

Ready for `$gsd-execute-phase 3` after Phase 2 completes.
