# PII Redactor Scale Tests

This folder contains the recovered and formalized scale-test program for the local privacy-preserving PII redactor.

## Structure

- `fixtures/`: deterministic synthetic corpora and expected-label files.
- `runs/`: timestamped benchmark outputs.
- `reports/`: curated benchmark reports for project review.
- `generate_corpus.py`: synthetic corpus generator.
- `run_library_benchmark.py`: direct Python pipeline benchmark.
- `run_http_batch_benchmark.py`: FastAPI `/redact/batch` benchmark.
- `write_report.py`: benchmark summary to Markdown report.
- `RUNBOOK.md`: repeatable operator instructions.

The historical large-scale artifacts were not found in the local folders searched. This directory is the canonical replacement so future scale work leaves auditable evidence.
