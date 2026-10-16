#!/usr/bin/env python3
"""Bounded, local-only ingestion benchmark; reports measured latency and errors."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import math
import time
import urllib.request
from urllib.parse import urlsplit


def benchmark(url, requests=100, workers=4):
    target = urlsplit(url)
    if target.scheme != "http" or target.hostname not in ("localhost", "127.0.0.1") or target.username:
        raise ValueError("Benchmark requires an explicit local HTTP endpoint")
    if not 1 <= requests <= 1000 or not 1 <= workers <= 8:
        raise ValueError("Bounded benchmark: 1..1000 requests and 1..8 workers")
    def send(_):
        request = urllib.request.Request(url.rstrip("/") + "/api/events", data=json.dumps({
            "eventType": "sensor.benchmark", "value": 20.0,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()}).encode(),
            headers={"Content-Type": "application/json"})
        before = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                ok = response.status == 202
        except (OSError, urllib.error.URLError):
            ok = False
        return (time.perf_counter() - before) * 1000, ok
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(send, range(requests)))
    elapsed = time.perf_counter() - started
    latencies = sorted(item[0] for item in results)
    return {"requests": requests, "workers": workers, "errors": sum(not item[1] for item in results),
            "elapsed_seconds": elapsed, "requests_per_second": requests / elapsed,
            "average_ms": sum(latencies) / requests, "p95_ms": latencies[math.ceil(requests * .95) - 1],
            "scope": "Local ingestion acknowledgement; not a production capacity claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8082")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = benchmark(args.url, args.requests, args.workers)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["errors"] else 0)
