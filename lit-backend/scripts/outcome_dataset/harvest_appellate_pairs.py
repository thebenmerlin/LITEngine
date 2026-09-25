"""
Harvest verified pre-decision filings for PREDECISION.md's training manifest
using the lower-court-judgment design: for each Supreme Court criminal
appeal, the High Court judgment it appealed genuinely existed before the
SC's decision and is not the decision being predicted, so — once
independently located on Indian Kanoon and VERIFIED (its own case number,
read from its own caption, must literally match what the SC judgment cited)
— it can serve as case text. Labels (outcome, appellant_type) come only
from the SC judgment's own operative text, via the same labeling.py /
appellant_type.py modules already audited for the N=187 corpus.

A case is only ever written to filings.csv when the HC match is verified.
Extraction failures, unresolved citations, and low-confidence labels are
logged to rejected_log.csv with a reason and simply excluded — never
guessed. Nothing here marks input_verified/outcome_verified true without
that verification actually having happened in this run.

Usage (from lit-backend/):
    ./venv/bin/python -m scripts.outcome_dataset.harvest_appellate_pairs \
        --output-dir data/outcome_dataset/predecision/appellate_pairs/v1 \
        --target 520 --max-sc-docs 3000
"""

import argparse
import asyncio
import csv
import glob
import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from scripts.outcome_dataset.appellant_type import TITLE_DATE_SUFFIX_RE, VS_SPLIT_RE, classify_appellant_type
from scripts.outcome_dataset.hc_citation import (
    ImpugnedCitation,
    court_matches_family,
    extract_impugned_citation,
    parse_loose_date,
    verify_citation_in_text,
)
from scripts.outcome_dataset.labeling import extract_outcome_label
from scripts.outcome_dataset.scope_filter import classify_scope
from scripts.outcome_dataset.scrape import RAW_CACHE_DIR, fetch_judgment, load_cached_judgment
from services.kanoon import kanoon_service
from utils.logger import get_logger

logger = get_logger(__name__)

OUTCOME_LABEL_CONFIDENCE_MIN = 0.75
APPELLANT_CONFIDENCE_MIN = 0.6
MAX_HC_CANDIDATES_TO_FETCH = 3
LABEL_TO_BINARY = {"dismissed": "dismissed", "allowed": "succeeds", "partly_allowed": "succeeds"}

SC_SEARCH_QUERIES = [
    "supreme court criminal appeal impugned judgment high court",
    "special leave petition criminal appeal conviction upheld",
    "special leave petition criminal appeal acquittal set aside",
    "supreme court criminal appeal sentence confirmed",
    "supreme court criminal appeal partly allowed sentence reduced",
    "supreme court criminal appeal dismissed conviction affirmed",
    "arising out of special leave petition criminal appeal",
    "supreme court criminal appeal against acquittal high court",
    "supreme court criminal appeal against conviction high court",
    "leave granted criminal appeal high court judgment",
    "supreme court criminal appeal life imprisonment high court",
    "supreme court criminal appeal bail cancelled high court",
]
MAX_PAGES_PER_QUERY = 40
CONSECUTIVE_FAILURE_LIMIT = 8

FILINGS_COLUMNS = [
    "case_id", "matter_id", "text_path", "filing_date", "decision_date",
    "court", "appellant_type", "outcome", "input_verified", "outcome_verified",
]
REJECTED_COLUMNS = ["sc_doc_id", "title", "reason", "detail"]

_BACKOFF_DELAYS = (0, 6, 18)


async def _search_with_backoff(query: str, **kwargs):
    """Retry a Kanoon search through transient failures (429/502 bursts
    are observed to come in short bursts, not a persistently dead
    endpoint — see memory on kanoon.py rate limiting), rather than
    surfacing the first failure."""
    last_exc = None
    for attempt, delay in enumerate(_BACKOFF_DELAYS):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await kanoon_service.search(query, **kwargs)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"search failed (attempt {attempt + 1}/{len(_BACKOFF_DELAYS)}) for {query!r}: {exc}")
    raise last_exc


def _appellant_name(title: str) -> str:
    clean = TITLE_DATE_SUFFIX_RE.sub("", title or "").strip()
    parts = VS_SPLIT_RE.split(clean, maxsplit=1)
    name = parts[0].strip() if parts else clean
    return name[:60]


def _local_sc_doc_ids() -> List[str]:
    ids = []
    for path in sorted(RAW_CACHE_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "Supreme Court" in (record.get("court") or ""):
            ids.append(path.stem)
    return ids


async def _sc_doc_id_stream(seen: Set[str]):
    """Yield SC doc_ids: local cache first (free), then live search
    (network), skipping anything already in `seen`."""
    for doc_id in _local_sc_doc_ids():
        if doc_id not in seen:
            seen.add(doc_id)
            yield doc_id

    kanoon_service.use_fixtures = False
    consecutive_failures = 0
    for query in SC_SEARCH_QUERIES:
        empty_pages_in_a_row = 0
        for pagenum in range(MAX_PAGES_PER_QUERY):
            try:
                results = await _search_with_backoff(query, pagenum=pagenum, limit=20)
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                logger.warning(f"SC search failed (query={query!r}, page={pagenum}): {exc}")
                if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                    logger.error("Too many consecutive SC search failures — aborting live search.")
                    return
                continue

            if not results:
                empty_pages_in_a_row += 1
                if empty_pages_in_a_row >= 2:
                    break
                continue
            empty_pages_in_a_row = 0

            new_count = 0
            for r in results:
                if r.doc_id in seen:
                    continue
                seen.add(r.doc_id)
                if r.court and "Supreme Court" not in r.court:
                    continue
                new_count += 1
                yield r.doc_id
            if new_count == 0:
                break


def _local_hc_candidates(family: str) -> List[str]:
    candidates = []
    for path in sorted(RAW_CACHE_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "Supreme Court" in (record.get("court") or ""):
            continue
        if court_matches_family(record.get("court") or "", family):
            candidates.append(path.stem)
    return candidates


_LOCAL_HC_TEXT_CACHE: Dict[str, dict] = {}


def _load_local_record(doc_id: str) -> Optional[dict]:
    if doc_id not in _LOCAL_HC_TEXT_CACHE:
        path = RAW_CACHE_DIR / f"{doc_id}.json"
        try:
            _LOCAL_HC_TEXT_CACHE[doc_id] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _LOCAL_HC_TEXT_CACHE[doc_id] = {}
    return _LOCAL_HC_TEXT_CACHE[doc_id] or None


async def resolve_hc_judgment(citation: ImpugnedCitation, sc_title: str) -> Optional[Tuple[str, dict, str]]:
    """Return (doc_id, record_dict, match_method) for a VERIFIED HC
    judgment matching `citation`, or None. Tries the local raw_cache first
    (free, no network). The live fallback searches by the appellant's own
    name — Kanoon's plain-text search ranks a specific case number far too
    weakly on its own (tried and confirmed: generic "<court> Criminal
    Appeal No X of Y" queries get swamped by unrelated same-court results)
    — narrowed by the citation's own "dated" recital via fromdate/todate
    when available (confirmed working against live Kanoon), which is a far
    stronger disambiguator than the number text. Whatever comes back is
    still only accepted if verify_citation_in_text proves it — the search
    only proposes candidates."""
    for doc_id in _local_hc_candidates(citation.hc_family):
        record = _load_local_record(doc_id)
        if record and verify_citation_in_text(record.get("text", ""), citation):
            return doc_id, record, "local_cache"

    appellant = _appellant_name(sc_title)
    if not appellant:
        return None

    queries: List[str] = []
    parsed_date = parse_loose_date(citation.dated_raw)
    if parsed_date:
        for window_days in (3, 30):
            window_start = parsed_date - timedelta(days=window_days)
            window_end = parsed_date + timedelta(days=window_days)
            fromdate = f"{window_start.day}-{window_start.month}-{window_start.year}"
            todate = f"{window_end.day}-{window_end.month}-{window_end.year}"
            queries.append(f"{appellant} fromdate:{fromdate} todate:{todate}")
    queries.append(f"{appellant} {citation.hc_family} High Court")

    for query in queries:
        try:
            results = await _search_with_backoff(query, limit=6)
        except Exception as exc:
            logger.warning(f"Live HC search failed for {citation} / {query!r}: {exc}")
            continue

        candidates = [r for r in results if not r.court or court_matches_family(r.court, citation.hc_family)]
        # Common appellant names (e.g. "Imtiaz") collide across dozens of
        # unrelated same-court judgments — fetching every court-matching
        # hit in Kanoon's relevance order burns huge request volume for
        # little yield. The search result already carries a date; when we
        # have a target date, rank candidates by closeness to it and only
        # fetch the closest few — the full-text verify_citation_in_text
        # check below is still what actually accepts a match, this only
        # decides fetch ORDER to avoid wasting requests on distant hits.
        if parsed_date:
            def _date_distance(result):
                d = parse_loose_date(result.date) if result.date else None
                return abs((d - parsed_date).days) if d else 10**6
            candidates.sort(key=_date_distance)
        candidates = candidates[:MAX_HC_CANDIDATES_TO_FETCH]

        for result in candidates:
            detail = await fetch_judgment(result.doc_id)
            if detail is None:
                continue
            if verify_citation_in_text(detail.text, citation):
                return detail.doc_id, detail.model_dump(), "live_search"
    return None


def _reject(writer, sc_doc_id: str, title: str, reason: str, detail: str = "") -> None:
    writer.writerow({"sc_doc_id": sc_doc_id, "title": title, "reason": reason, "detail": detail[:200]})


async def harvest(output_dir: Path, target: int, max_sc_docs: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    filings_dir = output_dir / "filings"
    filings_dir.mkdir(exist_ok=True)
    provenance_dir = output_dir / "provenance"
    provenance_dir.mkdir(exist_ok=True)

    filings_path = output_dir / "filings.csv"
    rejected_path = output_dir / "rejected_log.csv"

    existing_case_ids: Set[str] = set()
    if filings_path.exists():
        with filings_path.open(newline="", encoding="utf-8") as handle:
            existing_case_ids = {row["case_id"] for row in csv.DictReader(handle)}

    filings_is_new = not filings_path.exists()
    filings_handle = filings_path.open("a", newline="", encoding="utf-8")
    filings_writer = csv.DictWriter(filings_handle, fieldnames=FILINGS_COLUMNS)
    if filings_is_new:
        filings_writer.writeheader()

    rejected_is_new = not rejected_path.exists()
    rejected_handle = rejected_path.open("a", newline="", encoding="utf-8")
    rejected_writer = csv.DictWriter(rejected_handle, fieldnames=REJECTED_COLUMNS)
    if rejected_is_new:
        rejected_writer.writeheader()

    hc_doc_already_used: Set[str] = set()
    verified_count = len(existing_case_ids)
    scanned = 0
    reasons: Dict[str, int] = {}
    seen_sc_ids: Set[str] = set(existing_case_ids)
    started = time.time()

    def note(reason: str) -> None:
        reasons[reason] = reasons.get(reason, 0) + 1

    async for sc_doc_id in _sc_doc_id_stream(seen_sc_ids):
        if verified_count >= target or scanned >= max_sc_docs:
            break
        if sc_doc_id in existing_case_ids:
            continue
        scanned += 1

        detail = await fetch_judgment(sc_doc_id)
        if detail is None:
            note("sc_fetch_failed")
            _reject(rejected_writer, sc_doc_id, "", "sc_fetch_failed")
            continue

        scope = classify_scope(detail.text)
        if scope.hard_exclude or scope.borderline_scope:
            note("out_of_scope_or_borderline")
            _reject(rejected_writer, sc_doc_id, detail.title, "out_of_scope_or_borderline", scope.reason)
            continue

        label_result = extract_outcome_label(detail.text)
        if label_result["label"] == "unclear" or label_result["confidence"] < OUTCOME_LABEL_CONFIDENCE_MIN:
            note("outcome_label_not_confident")
            _reject(rejected_writer, sc_doc_id, detail.title, "outcome_label_not_confident",
                    f"label={label_result['label']} conf={label_result['confidence']}")
            continue

        appellant_result = classify_appellant_type(detail.title, detail.text)
        if appellant_result.appellant_type == "unclear" or appellant_result.confidence < APPELLANT_CONFIDENCE_MIN:
            note("appellant_type_not_confident")
            _reject(rejected_writer, sc_doc_id, detail.title, "appellant_type_not_confident",
                    f"type={appellant_result.appellant_type} conf={appellant_result.confidence}")
            continue

        citation = extract_impugned_citation(detail.text)
        if citation is None:
            note("no_hc_citation_extracted")
            _reject(rejected_writer, sc_doc_id, detail.title, "no_hc_citation_extracted")
            continue

        if not detail.date:
            note("sc_decision_date_missing")
            _reject(rejected_writer, sc_doc_id, detail.title, "sc_decision_date_missing")
            continue

        resolved = await resolve_hc_judgment(citation, detail.title)
        if resolved is None:
            note("hc_judgment_not_located")
            _reject(rejected_writer, sc_doc_id, detail.title, "hc_judgment_not_located", str(citation))
            continue
        hc_doc_id, hc_record, match_method = resolved

        if hc_doc_id in hc_doc_already_used:
            note("hc_judgment_reused")
            _reject(rejected_writer, sc_doc_id, detail.title, "hc_judgment_reused", hc_doc_id)
            continue

        hc_date = hc_record.get("date")
        hc_text = hc_record.get("text", "")
        if not hc_date or not hc_text.strip():
            note("hc_judgment_undated_or_empty")
            _reject(rejected_writer, sc_doc_id, detail.title, "hc_judgment_undated_or_empty", hc_doc_id)
            continue
        if hc_date >= detail.date:
            note("hc_date_not_before_sc_date")
            _reject(rejected_writer, sc_doc_id, detail.title, "hc_date_not_before_sc_date",
                    f"hc={hc_date} sc={detail.date}")
            continue
        if len(hc_text.split()) < 50:
            note("hc_text_too_short")
            _reject(rejected_writer, sc_doc_id, detail.title, "hc_text_too_short", hc_doc_id)
            continue

        text_path = filings_dir / f"{sc_doc_id}.txt"
        text_path.write_text(hc_text + "\n", encoding="utf-8")

        outcome = LABEL_TO_BINARY[label_result["label"]]
        row = {
            "case_id": sc_doc_id,
            "matter_id": hc_doc_id,  # remapped through precedent dedup aliases before build_predecision
            "text_path": f"filings/{sc_doc_id}.txt",
            "filing_date": hc_date,
            "decision_date": detail.date,
            "court": "Supreme Court",
            "appellant_type": appellant_result.appellant_type,
            "outcome": outcome,
            "input_verified": "true",
            "outcome_verified": "true",
        }
        filings_writer.writerow(row)
        filings_handle.flush()

        (provenance_dir / f"{sc_doc_id}.json").write_text(json.dumps({
            "sc_doc_id": sc_doc_id, "sc_title": detail.title, "sc_url": detail.url,
            "sc_decision_date": detail.date,
            "outcome_label": label_result["label"], "outcome_binary": outcome,
            "outcome_label_confidence": label_result["confidence"],
            "outcome_label_snippet": label_result["snippet"],
            "appellant_type": appellant_result.appellant_type,
            "appellant_type_confidence": appellant_result.confidence,
            "citation": citation._asdict(),
            "hc_doc_id": hc_doc_id, "hc_title": hc_record.get("title"),
            "hc_url": hc_record.get("url"), "hc_decision_date": hc_date,
            "match_method": match_method,
        }, indent=2), encoding="utf-8")

        hc_doc_already_used.add(hc_doc_id)
        existing_case_ids.add(sc_doc_id)
        verified_count += 1
        note("verified")
        if verified_count % 10 == 0:
            logger.info(f"progress: verified={verified_count} scanned={scanned} elapsed={round(time.time()-started,1)}s")

    filings_handle.close()
    rejected_handle.close()

    summary = {
        "verified_filings": verified_count,
        "sc_docs_scanned_this_run": scanned,
        "reasons": reasons,
        "elapsed_seconds": round(time.time() - started, 1),
        "target": target,
        "max_sc_docs": max_sc_docs,
    }
    (output_dir / "harvest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", type=int, default=520)
    parser.add_argument("--max-sc-docs", type=int, default=4000)
    args = parser.parse_args()
    asyncio.run(harvest(args.output_dir, args.target, args.max_sc_docs))


if __name__ == "__main__":
    main()
