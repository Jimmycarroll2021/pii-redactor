# PII Firewall for Knowledge Graph and RAG ingestion

This product mode makes PII redaction a mandatory pre-ingestion gate for
regulated Knowledge Graph and RAG systems.

## Default flow

```text
raw document
  -> pii-redactor ingest
  -> redacted document
  -> manifest with audit/provenance metadata
  -> KnowledgeGraph registration
  -> chunking / triples / embeddings / graph persistence
```

Raw PII must not be embedded, mirrored, written to graph properties, or sent to
external planning systems. Re-identification is available only through encrypted
audit with a separate key.

## CLI

Redact one file:

```powershell
pii-redactor redact --input raw\note.md --output safe\note.md --metadata safe\note.metadata.json
```

Redact a folder for KG/RAG ingestion:

```powershell
pii-redactor ingest --input raw --output redacted --manifest manifests\pii-redaction.jsonl
```

Gate a file or folder without keeping output:

```powershell
pii-redactor gate --input raw --output scale-tests\runs\gate-summary.json
```

Generate a compliance evidence pack:

```powershell
pii-redactor evidence --run scale-tests\runs\20260504-production-gate-final-1
```

## Metadata contract

Every redacted ingest row includes:

- `source_id`
- `input_path`
- `output_path`
- `redaction_audit_id`
- `pii_count`
- `pii_categories`
- `redaction_policy`
- `model_used`
- `gate_status`
- `processed_at`

## Policy profiles

- `kg_rag_default` — high-recall default for KG/RAG ingestion.
- `healthcare_high_recall` — high-recall clinical/patient profile.
- `legal_review` — fail-closed legal review profile.
- `logs_low_noise` — lower-noise log profile; not safe as the default for KG/RAG.

Default for regulated ingestion: `kg_rag_default`.
