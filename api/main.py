"""FastAPI HTTP wrapper for the PII redactor.

This is the integration surface for upstream pipeline tools that prefer
HTTP over direct Python imports (Power Automate, Logic Apps, Airflow
HttpOperator, etc).

Endpoints:
- POST /redact          De-identify a single document (async)
- POST /redact/batch    De-identify a list of documents (concurrent, semaphore-bounded)
- POST /reidentify      Recover original values from an audit_id (auth required)
- GET  /health          Liveness check
- GET  /info            Backend, model name, version

API key authentication via the X-API-Key header. Set PIIR_API_KEY in env.

Scale notes
-----------
The batch endpoint runs documents concurrently via asyncio.gather, bounded by a
semaphore (default 8, set PIIR_MAX_CONCURRENCY to tune). Each document runs
Pipeline.process_document_async() which offloads blocking LLM calls to the
thread-pool executor, keeping the event loop free.

For 100k docs/day with a GPU-backed llama.cpp server:
  - Single RTX 4090: ~100-120 docs/min sustained → 144-173k docs/day
  - Semaphore of 8 keeps the GPU saturated without overwhelming it
  - Connection pooling in LlamaCppClient means no TCP reconnection overhead
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import threading
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from pii_redactor import Config, build_pipeline
from pii_redactor.detector import PIIExtractionError
from pii_redactor.pipeline import Pipeline

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PII Redactor",
    version="0.1.1",
    description=(
        "Pre-ingestion PII de-identification using zero-shot LLM detection "
        "with Australian government identifier checksum validation. "
        "Implements Wiest et al. (NEJM AI, 2024) extended with AU Commonwealth identifiers."
    ),
)

# Built once at startup
_pipeline: Optional[Pipeline] = None
_semaphore: Optional[asyncio.Semaphore] = None
_metrics_lock = threading.Lock()
_metrics = {
    "documents_processed": 0,
    "pii_spans_total": 0,
    "errors_total": 0,
    "latency_ms_total": 0.0,
    "latency_ms_max": 0.0,
    "categories": {},
}


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline(Config.from_env())
    return _pipeline


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        max_concurrency = int(os.environ.get("PIIR_MAX_CONCURRENCY", "8"))
        _semaphore = asyncio.Semaphore(max_concurrency)
    return _semaphore


# ------------------------------------------------------------- auth dependency

def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def _compare_key(provided: str, expected: str) -> bool:
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _max_text_chars() -> int:
    return _env_int("PIIR_MAX_TEXT_CHARS", 200_000)


def _max_batch_docs() -> int:
    return _env_int("PIIR_MAX_BATCH_DOCS", 1000)


def _enforce_text_limit(text: str) -> None:
    limit = _max_text_chars()
    if len(text) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Document exceeds PIIR_MAX_TEXT_CHARS limit of {limit}.",
        )


def _record_success(processing_ms: float, categories: list[str]) -> None:
    with _metrics_lock:
        _metrics["documents_processed"] += 1
        _metrics["pii_spans_total"] += len(categories)
        _metrics["latency_ms_total"] += processing_ms
        _metrics["latency_ms_max"] = max(_metrics["latency_ms_max"], processing_ms)
        category_counts = _metrics["categories"]
        for category in categories:
            category_counts[category] = category_counts.get(category, 0) + 1


def _record_error() -> None:
    with _metrics_lock:
        _metrics["errors_total"] += 1


def require_api_key(x_api_key: str = Header(default="")) -> None:
    expected = os.environ.get("PIIR_API_KEY")
    if not expected:
        return  # No key set means auth is disabled. Loud warning at startup.
    if not _compare_key(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )


def require_reidentify_api_key(x_api_key: str = Header(default="")) -> None:
    expected = os.environ.get("PIIR_REIDENTIFY_API_KEY") or os.environ.get("PIIR_API_KEY")
    if not expected:
        return
    if not _compare_key(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing re-identification API key.",
        )


# ----------------------------------------------------------------- schemas

class RedactRequest(BaseModel):
    text: str = Field(..., min_length=1)
    document_id: Optional[str] = None


class RedactBatchRequest(BaseModel):
    documents: list[RedactRequest] = Field(..., max_length=1000)


class SpanModel(BaseModel):
    category: str
    start: int
    end: int
    placeholder: Optional[str]
    confidence: float
    validator_passed: Optional[bool]


class RedactResponse(BaseModel):
    document_id: str
    redacted_text: str
    pii_count: int
    spans: list[SpanModel]
    pii_table: list[dict]
    audit_id: str
    processed_at: str
    model_used: Optional[str]
    processing_ms: Optional[float] = None


class ReidentifyRequest(BaseModel):
    audit_id: str


# ----------------------------------------------------------------- endpoints

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    pipeline = get_pipeline()
    max_concurrency = int(os.environ.get("PIIR_MAX_CONCURRENCY", "8"))
    cfg = Config.from_env()
    return {
        "version": "0.1.1",
        "model_used": pipeline.model_name,
        "backend": cfg.backend,
        "max_concurrency": max_concurrency,
        "max_text_chars": _max_text_chars(),
        "max_batch_docs": _max_batch_docs(),
        "fail_on_llm_error": cfg.fail_on_llm_error,
        "api_key_required": _env_truthy("PIIR_REQUIRE_API_KEY"),
    }


@app.get("/metrics", dependencies=[Depends(require_api_key)])
def metrics() -> dict:
    with _metrics_lock:
        snapshot = dict(_metrics)
        snapshot["categories"] = dict(_metrics["categories"])
    processed = snapshot["documents_processed"]
    snapshot["latency_ms_mean"] = (
        round(snapshot["latency_ms_total"] / processed, 3) if processed else 0.0
    )
    return snapshot


@app.post(
    "/redact",
    response_model=RedactResponse,
    dependencies=[Depends(require_api_key)],
)
async def redact(req: RedactRequest) -> RedactResponse:
    _enforce_text_limit(req.text)
    pipeline = get_pipeline()
    t0 = time.perf_counter()
    try:
        result = await pipeline.process_document_async(req.text, document_id=req.document_id)
    except PIIExtractionError as exc:
        _record_error()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    d = result.to_dict()
    processing_ms = round((time.perf_counter() - t0) * 1000, 1)
    d["processing_ms"] = processing_ms
    _record_success(processing_ms, [span.category.value for span in result.spans])
    return RedactResponse(**d)


@app.post(
    "/redact/batch",
    response_model=list[RedactResponse],
    dependencies=[Depends(require_api_key)],
)
async def redact_batch(req: RedactBatchRequest) -> list[RedactResponse]:
    """Process documents concurrently.

    Bounded by PIIR_MAX_CONCURRENCY (default 8) to avoid overwhelming the
    LLM backend. Documents are returned in submission order.
    """
    max_docs = _max_batch_docs()
    if len(req.documents) > max_docs:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch exceeds PIIR_MAX_BATCH_DOCS limit of {max_docs}.",
        )
    for doc in req.documents:
        _enforce_text_limit(doc.text)

    pipeline = get_pipeline()
    sem = get_semaphore()

    async def _process(doc: RedactRequest) -> RedactResponse:
        async with sem:
            t0 = time.perf_counter()
            try:
                result = await pipeline.process_document_async(
                    doc.text, document_id=doc.document_id
                )
            except PIIExtractionError as exc:
                _record_error()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
            d = result.to_dict()
            processing_ms = round((time.perf_counter() - t0) * 1000, 1)
            d["processing_ms"] = processing_ms
            _record_success(processing_ms, [span.category.value for span in result.spans])
            return RedactResponse(**d)

    return list(await asyncio.gather(*[_process(doc) for doc in req.documents]))


@app.post("/reidentify", dependencies=[Depends(require_reidentify_api_key)])
def reidentify(req: ReidentifyRequest) -> list[dict]:
    """Recover original PII values from the audit log.

    Requires the audit encryption key to be configured. This endpoint
    should be wrapped in additional authorisation in production
    (the API key alone is not sufficient — re-identification typically
    requires a separate caseworker-level credential).
    """
    pipeline = get_pipeline()
    try:
        return pipeline.audit.reidentify(req.audit_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ----------------------------------------------------------------- startup

@app.on_event("startup")
async def startup() -> None:
    # Initialise semaphore inside the event loop
    get_semaphore()
    get_pipeline()

    if _env_truthy("PIIR_REQUIRE_API_KEY") and not os.environ.get("PIIR_API_KEY"):
        raise RuntimeError("PIIR_REQUIRE_API_KEY=true but PIIR_API_KEY is not set.")

    if _env_truthy("PIIR_REQUIRE_PRODUCTION_SAFETY"):
        missing = []
        cfg = Config.from_env()
        if not os.environ.get("PIIR_API_KEY"):
            missing.append("PIIR_API_KEY")
        if not os.environ.get("PIIR_REIDENTIFY_API_KEY"):
            missing.append("PIIR_REIDENTIFY_API_KEY")
        if not os.environ.get("PIIR_AUDIT_KEY"):
            missing.append("PIIR_AUDIT_KEY")
        if not _env_truthy("PIIR_FAIL_ON_LLM_ERROR"):
            missing.append("PIIR_FAIL_ON_LLM_ERROR=true")
        if cfg.backend == "mock":
            missing.append("PIIR_BACKEND must not be mock")
        if missing:
            raise RuntimeError(
                "PIIR_REQUIRE_PRODUCTION_SAFETY=true but required settings are missing: "
                + ", ".join(missing)
            )

    if not os.environ.get("PIIR_API_KEY"):
        logger.warning(
            "PIIR_API_KEY not set. The redaction API is unauthenticated. "
            "Set this in production."
        )
    if os.environ.get("PIIR_API_KEY") and not os.environ.get("PIIR_REIDENTIFY_API_KEY"):
        logger.warning(
            "PIIR_REIDENTIFY_API_KEY not set. /reidentify falls back to PIIR_API_KEY. "
            "Set a separate key for production re-identification workflows."
        )
    max_concurrency = int(os.environ.get("PIIR_MAX_CONCURRENCY", "8"))
    logger.info("PII Redactor started. max_concurrency=%d", max_concurrency)
