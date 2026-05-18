# Fixtures

Synthetic fixture folders are generated here by `scale-tests/generate_corpus.py`.

Each generated corpus contains:

- `documents.jsonl`: one document per line.
- `expected_labels.jsonl`: expected PII labels per document.
- `manifest.json`: generator settings, profile, seed, and corpus statistics.

Synthetic values are fake and deterministic. They are designed for repeatable detection and redaction benchmarking, not for clinical realism.
