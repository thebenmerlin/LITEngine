"""Exercise the staged backend over localhost or an SSH tunnel."""

import argparse
import json
import time
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base_url, path, payload=None, timeout=15):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        f"{base_url.rstrip('/')}{path}", data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST" if body else "GET",
    )
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def smoke(base_url, wait_seconds):
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            ready = request(base_url, "/api/v1/health/ready")
            if ready.get("outcome_model_loaded") and ready.get("index_loaded"):
                break
            raise RuntimeError(f"Subsystems not ready: {ready}")
        except (HTTPError, URLError, RuntimeError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Backend did not become ready: {exc}") from exc
            time.sleep(5)

    health = request(base_url, "/health")
    if health.get("status") != "healthy":
        raise RuntimeError(f"Unexpected health result: {health}")
    stats = request(base_url, "/api/v1/precedent/index/stats")
    if stats.get("total_documents", 0) < 1:
        raise RuntimeError(f"Precedent index is empty: {stats}")

    profile = {
        "parties": {},
        "legal_issues": ["Whether the conviction should be set aside?"],
        "ipc_sections": ["Section 302"],
        "acts_referenced": [],
        "court_level": "High Court",
        "case_type": "criminal",
        "key_facts": ["The witness account is disputed."],
        "relief_sought": "Set aside the conviction",
        "metadata": {"extraction_method": "rules", "confidence": 0.5, "processing_time_ms": 0},
    }
    simulation = request(base_url, "/api/v1/simulation/predict", {
        "case_profile": profile,
        "precedents": [],
        "appellant_type": "accused_appeal",
        "filing_date": "2020-01-01",
    })
    if simulation.get("old_vs_new", {}).get("primary") != "new_model":
        raise RuntimeError("The incumbent classifier was not primary in the staged response")

    cutoff = date(2020, 1, 1)
    search = request(base_url, "/api/v1/precedent/search", {
        "query": "criminal appeal conviction",
        "top_k": 5,
        "use_kanoon": False,
        "before_date": cutoff.isoformat(),
    }, timeout=180)
    results = search.get("results", [])
    if not results or any(not result.get("date") or date.fromisoformat(result["date"][:10]) >= cutoff for result in results):
        raise RuntimeError(f"Dated precedent search failed: {search}")
    print(f"Staging smoke passed: model loaded, {stats['total_documents']} indexed documents, {len(results)} dated search results")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait-seconds", type=int, default=180)
    args = parser.parse_args()
    smoke(args.base_url, args.wait_seconds)


if __name__ == "__main__":
    main()
