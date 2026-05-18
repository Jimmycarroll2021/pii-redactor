param(
    [string]$Python = "C:\Users\j_car\AppData\Local\Programs\Python\Python312\python.exe",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8020,
    [string]$Model = "qwen2.5:7b",
    [string]$OllamaUrl = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Python)) {
    throw "Python executable not found: $Python"
}

$env:PIIR_BACKEND = "ollama"
$env:PIIR_OLLAMA_MODEL = $Model
$env:PIIR_OLLAMA_URL = $OllamaUrl
$env:PIIR_LLM_TIMEOUT_SECONDS = "600"
$env:PIIR_LLM_RETRIES = "1"
$env:PIIR_MAX_CONCURRENCY = "1"
$env:PIIR_AUDIT_ENABLED = "false"

Write-Host "Starting qwen API on http://$HostAddress`:$Port using $Python"
Write-Host "Model: $Model"
& $Python -m uvicorn api.main:app --host $HostAddress --port $Port
