# Scale-Test Runbook

## 1. Generate a deterministic corpus

```powershell
py -3.12 scale-tests\generate_corpus.py --count 1000 --seed 42 --profile mixed --out scale-tests\fixtures\synthetic-1000-seed42
```

## 2. Run direct library benchmark

```powershell
$run = "scale-tests\runs\$(Get-Date -Format yyyyMMdd-HHmmss)-library-mock-1000docs"
py -3.12 scale-tests\run_library_benchmark.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --backend mock --audit-mode disabled --out $run
py -3.12 scale-tests\write_report.py --summary "$run\summary.json" --out "$run\REPORT.md"
```

## 3. Run service-backed benchmark

Start the API with the desired local backend first, then run:

```powershell
$run = "scale-tests\runs\$(Get-Date -Format yyyyMMdd-HHmmss)-http-batch-1000docs"
py -3.12 scale-tests\run_http_batch_benchmark.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --url http://127.0.0.1:8000 --batch-size 25 --concurrency 4 --out $run
py -3.12 scale-tests\write_report.py --summary "$run\summary.json" --out "$run\REPORT.md"
```

## 4. Run Ollama-safe local LLM benchmark

For slower local models, raise the app-side LLM timeout and avoid hidden retry amplification:

```powershell
$env:PIIR_BACKEND = "ollama"
$env:PIIR_OLLAMA_MODEL = "qwen2.5:7b"
$env:PIIR_OLLAMA_URL = "http://127.0.0.1:11434"
$env:PIIR_LLM_TIMEOUT_SECONDS = "600"
$env:PIIR_LLM_RETRIES = "1"
$env:PIIR_MAX_CONCURRENCY = "2"
$env:PIIR_AUDIT_ENABLED = "false"

py -3.12 -m uvicorn api.main:app --host 127.0.0.1 --port 8019
```

In another terminal:

```powershell
$run = "scale-tests\runs\$(Get-Date -Format yyyyMMdd-HHmmss)-http-ollama-qwen25-7b-100docs-c2"
py -3.12 scale-tests\run_http_batch_benchmark.py --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl --url http://127.0.0.1:8019 --batch-size 5 --concurrency 2 --limit 100 --progress-every 2 --request-timeout 900 --out $run
py -3.12 scale-tests\write_report.py --summary "$run\summary.json" --out "$run\REPORT.md"
```

## 5. Evidence policy

Keep every run directory that informed a product or privacy decision. Copy the best current report into `scale-tests/reports/` for quick review.


## qwen2.5:7b FastAPI lifecycle scripts

Use the explicit Python 3.12 executable. Do not rely on `python` resolving to the right environment.

Terminal 1:

```powershell
.\scale-tests\start_qwen_api.ps1
```

Terminal 2:

```powershell
.\scale-tests\run_qwen_http_validation.ps1 -Limit 20
```

Important: `run_http_batch_benchmark.py` appends `/redact/batch` internally. Pass only the base URL, for example `http://127.0.0.1:8020`.

## API security controls

Local demo mode can run without an API key, but production-style runs should require one:

```powershell
$env:PIIR_REQUIRE_API_KEY='true'
$env:PIIR_API_KEY='<redaction-api-key>'
$env:PIIR_REIDENTIFY_API_KEY='<separate-reidentify-key>'
```

When `PIIR_REQUIRE_API_KEY=true`, the API fails startup unless `PIIR_API_KEY` is set.

`/redact` and `/redact/batch` use `PIIR_API_KEY` via the `X-API-Key` header.

`/reidentify` uses `PIIR_REIDENTIFY_API_KEY` when set. If it is not set, it falls back to `PIIR_API_KEY`; use a separate key for production re-identification workflows.

## Proper PII eval suite

Full deterministic gate:

```powershell
py -3.12 scale-testsun_pii_eval_suite.py --profile proper --backend mock
```

Quick deterministic gate:

```powershell
py -3.12 scale-testsun_pii_eval_suite.py --profile quick --backend mock
```

Bounded qwen sample gate, explicit because it is slow:

```powershell
$env:PIIR_OLLAMA_MODEL='qwen2.5:7b'
$env:PIIR_OLLAMA_URL='http://127.0.0.1:11434'
py -3.12 scale-testsun_pii_eval_suite.py --profile quick --backend ollama --qwen-sample-limit 1
```

Latest implementation check:

```text
scale-testsunselease-placeholder
```

Replace the placeholder with the latest run folder printed by the eval command.
