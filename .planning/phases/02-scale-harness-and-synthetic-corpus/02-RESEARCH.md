# Phase 2 Research: Scale Harness and Synthetic Corpus

## Research Summary

Scale testing for PII redaction needs two independent dimensions:

1. Correctness and privacy safety: expected identifiers are detected and no original PII leaks into safe outputs.
2. Performance: throughput, latency distribution, concurrency behavior, and error rate.

## Corpus Strategy

Use deterministic synthetic fixtures rather than real data. Each generated document should contain:

- source text
- document ID
- expected PII labels with category, value, and source location if practical
- scenario metadata such as `clinical_letter`, `government_form`, `vendor_onboarding`, or `negative_control`

Categories should include:

- Standard: name, DOB, date, address, phone, email, URL, IP.
- AU government: TFN, Medicare, ABN, ACN, driver licence, passport, BSB/account, Centrelink CRN.
- Medical: patient ID, MRN/URN/hospital number, healthcare identifier.

## Harness Strategy

Build two runners:

- Direct library runner: imports `build_pipeline`, processes documents in-process, gives baseline correctness and local throughput.
- HTTP batch runner: posts chunks to `/redact/batch`, tests API concurrency, serialization, and service behavior.

## Metrics Strategy

Every run should write:

- `results.jsonl`: one line per document with safe outputs and timing.
- `summary.json`: aggregate counts, errors, latency percentiles, docs/sec.
- Future Phase 3 can convert these into Markdown reports.

## Pitfalls

- Do not confuse synthetic fixture originals with production-safe outputs.
- Do not benchmark with real PII.
- Do not hide errors inside aggregate counts.
- Do not compare different backends without recording backend/model/config.
