from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def chunks(rows: list[dict], size: int) -> list[list[dict]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def post_json(url: str, payload: dict, api_key: str | None, request_timeout: int) -> dict | list:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        return json.loads(response.read().decode("utf-8"))


async def send_batch(
    index: int,
    url: str,
    batch: list[dict],
    api_key: str | None,
    request_timeout: int,
    semaphore: asyncio.Semaphore,
) -> tuple[int, float, dict | list]:
    payload = {
        "documents": [
            {"document_id": row["id"], "text": row["text"]}
            for row in batch
        ]
    }
    async with semaphore:
        started = time.perf_counter()
        response = await asyncio.to_thread(post_json, url, payload, api_key, request_timeout)
        elapsed = (time.perf_counter() - started) * 1000.0
        return index, elapsed, response


def response_items(response: dict | list) -> list[dict]:
    if isinstance(response, list):
        return response
    results = response.get("results", [])
    return results if isinstance(results, list) else []


def item_document_id(item: dict) -> str | None:
    return item.get("document_id") or item.get("id")


def load_existing_results(path: Path) -> tuple[list[dict], set[str]]:
    rows: list[dict] = []
    completed_ids: set[str] = set()
    if not path.exists():
        return rows, completed_ids
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append(row)
            for item in row.get("results", []):
                doc_id = item_document_id(item)
                if doc_id:
                    completed_ids.add(doc_id)
    return rows, completed_ids


def update_leaks(
    expected_by_id: dict[str, dict],
    items: list[dict],
    checked: Counter[str],
    leaks: Counter[str],
) -> None:
    for item in items:
        doc_id = item_document_id(item)
        expected = expected_by_id.get(doc_id or "", {"labels": []})
        safe_text = json.dumps(item, sort_keys=True)
        for label in expected.get("labels", []):
            if not label.get("valid", True):
                continue
            checked[label["category"]] += 1
            if label["value"] in safe_text:
                leaks[label["category"]] += 1


def build_summary(
    *,
    status: str,
    args: argparse.Namespace,
    started_at: str,
    docs_requested: int,
    docs_processed: int,
    batches_total: int,
    batches_completed: int,
    total_seconds: float,
    latencies: list[float],
    checked: Counter[str],
    leaks: Counter[str],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    docs_per_second = docs_processed / total_seconds if total_seconds else 0.0
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started_at,
        "url": args.url,
        "documents": docs_processed,
        "documents_requested": docs_requested,
        "batch_size": args.batch_size,
        "concurrency": args.concurrency,
        "batches_total": batches_total,
        "batches_completed": batches_completed,
        "total_seconds": total_seconds,
        "docs_per_second": docs_per_second,
        "estimated_docs_per_day": docs_per_second * 86400.0,
        "batch_latency_ms": {
            "min": min(latencies) if latencies else 0.0,
            "mean": statistics.mean(latencies) if latencies else 0.0,
            "median": statistics.median(latencies) if latencies else 0.0,
            "p90": percentile(latencies, 90),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "max": max(latencies) if latencies else 0.0,
        },
        "leak_checked_counts": dict(sorted(checked.items())),
        "leak_counts": dict(sorted(leaks.items())),
        "leak_count_total": sum(leaks.values()),
        "error_count": len(errors),
        "errors": errors,
        "partial": status != "OK",
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    docs = read_jsonl(args.documents)
    expected_rows = read_jsonl(args.expected)
    expected_by_id = {row["id"]: row for row in expected_rows}
    if args.limit:
        docs = docs[: args.limit]

    docs_requested = len(docs)
    args.out.mkdir(parents=True, exist_ok=True)
    results_path = args.out / "results.jsonl"
    summary_path = args.out / "summary.json"

    existing_rows, completed_ids = load_existing_results(results_path) if args.resume else ([], set())
    if completed_ids:
        docs = [doc for doc in docs if doc["id"] not in completed_ids]

    batch_rows = chunks(docs, args.batch_size)
    semaphore = asyncio.Semaphore(args.concurrency)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    latencies: list[float] = [
        float(row.get("batch_latency_ms", 0.0))
        for row in existing_rows
        if row.get("batch_latency_ms") is not None
    ]
    checked: Counter[str] = Counter()
    leaks: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []
    for row in existing_rows:
        update_leaks(expected_by_id, row.get("results", []), checked, leaks)
    docs_processed = len(completed_ids)
    batches_completed = len(existing_rows)
    batches_total = batches_completed + len(batch_rows)

    tasks = [
        send_batch(index, args.url.rstrip("/") + "/redact/batch", batch, args.api_key, args.request_timeout, semaphore)
        for index, batch in enumerate(batch_rows, start=1)
    ]

    def write_partial(status: str) -> None:
        summary = build_summary(
            status=status,
            args=args,
            started_at=started_at,
            docs_requested=docs_requested,
            docs_processed=docs_processed,
            batches_total=batches_total,
            batches_completed=batches_completed,
            total_seconds=time.perf_counter() - started,
            latencies=latencies,
            checked=checked,
            leaks=leaks,
            errors=errors,
        )
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    try:
        mode = "a" if args.resume and results_path.exists() else "w"
        with results_path.open(mode, encoding="utf-8") as handle:
            for task in asyncio.as_completed(tasks):
                try:
                    index, elapsed, response = await task
                    items = response_items(response)
                    latencies.append(elapsed)
                    batches_completed += 1
                    docs_processed += len(items)
                    update_leaks(expected_by_id, items, checked, leaks)
                    handle.write(
                        json.dumps(
                            {
                                "batch_index": index,
                                "batch_latency_ms": elapsed,
                                "result_count": len(items),
                                "results": items,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    handle.flush()
                    if args.progress_every and (batches_completed % args.progress_every == 0):
                        print(
                            json.dumps(
                                {
                                    "progress": True,
                                    "batches_completed": batches_completed,
                                    "batches_total": batches_total,
                                    "documents_processed": docs_processed,
                                },
                                sort_keys=True,
                            ),
                            flush=True,
                        )
                    write_partial("PARTIAL")
                except Exception as exc:
                    errors.append({"error": type(exc).__name__, "message": str(exc)})
                    write_partial("FAILED")
                    raise
    except asyncio.CancelledError:
        write_partial("INTERRUPTED")
        raise
    except KeyboardInterrupt:
        write_partial("INTERRUPTED")
        raise

    status = "OK" if not errors and docs_processed == docs_requested else "PARTIAL"
    final_summary = build_summary(
        status=status,
        args=args,
        started_at=started_at,
        docs_requested=docs_requested,
        docs_processed=docs_processed,
        batches_total=batches_total,
        batches_completed=batches_completed,
        total_seconds=time.perf_counter() - started,
        latencies=latencies,
        checked=checked,
        leaks=leaks,
        errors=errors,
    )
    summary_path.write_text(json.dumps(final_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return final_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the FastAPI /redact/batch endpoint.")
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=0)
    parser.add_argument("--request-timeout", type=int, default=600)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    try:
        summary = asyncio.run(run(args))
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        summary = {
            "status": "NOT RUN",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reason": str(exc),
            "url": args.url,
            "documents_input": str(args.documents),
            "partial": True,
        }
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
