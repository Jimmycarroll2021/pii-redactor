# Phase 11: Calibration Review Pack - Plan

**Status:** Planned
**Mode:** Autonomous GSD

## Goal

Add tooling to export reviewer-friendly calibration samples for false-positive/false-negative analysis.

## Tasks

1. Create scale-tests/export_review_pack.py.
2. Generate a small mock-backed review pack.
3. Publish a calibration report.
4. Update GSD state.

## Acceptance Criteria

- Review pack exporter exists.
- Review pack includes redacted text, safe PII table, expected labels, and reviewer fields.
- A generated sample pack exists under scale-tests/review-packs.
