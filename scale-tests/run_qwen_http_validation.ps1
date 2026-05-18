param(
    [int]$Limit = 20,
    [int]$Port = 8020,
    [string]$RunName = "",
    [string]$Python = "C:\Users\j_car\AppData\Local\Programs\Python\Python312\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Python)) {
    throw "Python executable not found: $Python"
}

if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = "$(Get-Date -Format yyyyMMdd-HHmmss)-http-ollama-qwen25-7b-${Limit}docs-c1"
}

$run = "scale-tests\runs\$RunName"

& $Python scale-tests\run_http_batch_benchmark.py `
    --documents scale-tests\fixtures\synthetic-1000-seed42\documents.jsonl `
    --expected scale-tests\fixtures\synthetic-1000-seed42\expected_labels.jsonl `
    --url "http://127.0.0.1:$Port" `
    --batch-size 2 `
    --concurrency 1 `
    --limit $Limit `
    --request-timeout 600 `
    --resume `
    --out $run
