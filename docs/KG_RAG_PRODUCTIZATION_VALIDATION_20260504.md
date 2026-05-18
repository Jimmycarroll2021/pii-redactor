# KG/RAG PII Firewall Productization Validation - 2026-05-04

## Verdict

Status: PASS for controlled production pilot.

The PII Redactor KG/RAG firewall now passes the post-productization gate across deterministic registry tests, encrypted audit checks, Qwen/Ollama quick coverage, evidence-pack generation, Docker image build, production-safety refusal, and Ollama-backed API smoke.

## Passing Runs

| Gate | Result | Artifact |
|---|---:|---|
| CLI smoke: redact, ingest, gate, evidence | PASS | `scale-tests/runs/20260504-cli-smoke-kg-rag-2` |
| Full production gate with Qwen quick | PASS | `scale-tests/runs/20260504-production-gate-kg-rag-productization-4` |
| Docker image build | PASS | `pii-redactor-api:kg-rag-productization` |
| Docker production-safety mock refusal | PASS | `scale-tests/runs/20260504-docker-safety-mock-refusal-1` |
| Docker Ollama API smoke | PASS | `scale-tests/runs/20260504-docker-smoke-ollama-kg-rag-productization-1` |
| KnowledgeGraph secure wrapper smoke | PASS | `manifests/pii-redaction/20260504-092142.jsonl` |

## Production Gate Coverage

The full production gate passed with:

- Compile check: PASS.
- Deterministic full registry: PASS.
- Encrypted audit over 48,758 documents: PASS.
- Qwen `qwen2.5:7b` quick registry: PASS.
- Evidence-pack generation: PASS.

Evidence pack:

- `scale-tests/runs/20260504-production-gate-kg-rag-productization-4/EVIDENCE-PACK.md`
- `scale-tests/runs/20260504-production-gate-kg-rag-productization-4/evidence-summary.json`

## Fixes Made During Validation

- Evidence generation now supports production-gate summaries, CLI gate summaries, and manifest-only run folders.
- Production gate now fails if evidence-pack generation fails.
- Qwen/Ollama parser now tolerates common alternative entity schemas, empty JSON objects, and one parse-level retry.
- Deterministic address prepass added for street-address backstop coverage.
- International parenthesized phone formats expanded and tightened to avoid over-consuming trailing tokens.
- Production safety now refuses `PIIR_BACKEND=mock` when `PIIR_REQUIRE_PRODUCTION_SAFETY=true`.
- KnowledgeGraph secure registration now resolves source paths before entering the PII tool directory.
- CLI ingest now fails on missing paths or empty supported-file sets instead of reporting false PASS.
- Source registry ID generation now handles existing IDs robustly before assigning the next `SRC-###` value.
- Direct source registration now defaults to redacted paths only; raw path registration requires explicit `-AllowRaw`.

## KnowledgeGraph Wrapper Result

The secure wrapper was smoke-tested with a disposable source containing sample name, email, phone, and Medicare-like data.

Result:

- PII gated ingest: PASS.
- Manifest written: `manifests/pii-redaction/20260504-092142.jsonl`.
- Redacted source registered: `SRC-015`.
- Registered redacted path: `raw/redacted/disposable-secure-pii-smoke-20260504.txt`.
- Sample leak check over redacted file: PASS.
- Direct raw registration guard: PASS.

## Current Release Posture

Ready for a controlled production pilot behind API keys, encrypted audit logging, request size limits, and real LLM backend configuration.

Do not run broad unattended production ingestion with `PIIR_BACKEND=mock`. Production safety now blocks that configuration.
