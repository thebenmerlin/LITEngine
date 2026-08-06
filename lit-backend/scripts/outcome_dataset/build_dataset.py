"""
CLI entrypoint: builds the judicial-outcome training dataset.

    ./venv/bin/python3 -m scripts.outcome_dataset.build_dataset --target 400

Pipeline:
  1. Collect ~target unique criminal-appeal judgment doc_ids from Indian
     Kanoon search (services.kanoon.KanoonService), across a rotating set
     of queries.
  2. Fetch each judgment's full text, using an on-disk cache
     (scripts/outcome_dataset/scrape.py) so re-runs never re-scrape.
  3. Extract an outcome label + confidence + snippet from each judgment's
     operative text (labeling.py).
  4. Assemble the 5 simulator features for each case (features.py),
     including a leave-one-out precedent-alignment score computed over
     the collected batch itself.
  5. Write data/outcome_dataset/dataset.csv (all cases) and
     data/outcome_dataset/manual_review_sample.csv (random 50, full
     snippets) for manual spot-checking.
  6. Print + persist a summary: totals, class balance, confidence
     distribution, and any parsing/fetch issues hit along the way.

This script does not touch the live app's request path — it only reuses
KanoonService/extractor/graph_builder/simulator as read-only library
code, and writes exclusively under data/, never fixtures/.
"""

import argparse
import asyncio
import csv
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset import scrape
from scripts.outcome_dataset.features import (
    PrecedentIndex,
    assemble_features,
    build_case_profile,
    build_feature_text,
    build_graph_stats,
)
from scripts.outcome_dataset.labeling import extract_outcome_label
from services.kanoon import kanoon_service
from utils.logger import get_logger

logger = get_logger(__name__)

OUT_DIR = scrape.DATA_DIR / "outcome_dataset"
DATASET_CSV = OUT_DIR / "dataset.csv"
REVIEW_CSV = OUT_DIR / "manual_review_sample.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"
SUMMARY_MD = OUT_DIR / "summary.md"
PRECEDENT_INDEX_PATH = OUT_DIR / "precedent_index.json"

MIN_TEXT_LEN = 300  # shorter than this is almost certainly a bad scrape
SNIPPET_MAIN_LEN = 400  # truncated snippet kept in the main dataset

DATASET_COLUMNS = [
    "case_id",
    "source_url",
    "title",
    "court",
    "court_level_normalized",
    "date",
    "case_type",
    "feature_precedent_alignment",
    "feature_statutory_strength",
    "feature_argument_completeness",
    "feature_case_complexity",
    "feature_court_level",
    "ipc_section_count",
    "acts_referenced_count",
    "legal_issue_count",
    "key_fact_count",
    "graph_node_count",
    "graph_weak_node_count",
    "precedent_match_count",
    "extracted_label",
    "label_confidence",
    "label_snippet",
]

REVIEW_COLUMNS = [
    "case_id",
    "source_url",
    "title",
    "extracted_label",
    "label_confidence",
    "label_snippet_full",
]


async def process_case(search_result) -> Optional[Dict[str, Any]]:
    """Fetch + label + build the (pre-precedent) feature inputs for one
    case. Returns None if the case should be skipped."""
    detail = await scrape.fetch_judgment(search_result.doc_id)
    if detail is None:
        return {"skip_reason": "fetch_failed", "doc_id": search_result.doc_id}

    if len(detail.text) < MIN_TEXT_LEN:
        return {"skip_reason": "text_too_short", "doc_id": search_result.doc_id}

    label_result = extract_outcome_label(detail.text)
    feature_text = build_feature_text(detail.text, label_result["match_start"])
    if not feature_text.strip():
        # Truncation left nothing usable (label matched very early in a
        # short document) — fall back to the full text for features.
        feature_text = detail.text

    profile = build_case_profile(feature_text, detail.court)
    graph_stats = build_graph_stats(profile)

    return {
        "skip_reason": None,
        "doc_id": detail.doc_id,
        "detail": detail,
        "feature_text": feature_text,
        "profile": profile,
        "graph_stats": graph_stats,
        "label_result": label_result,
    }


def _confidence_bucket(conf: float) -> str:
    if conf >= 0.9:
        return "0.9-1.0 (high)"
    if conf >= 0.75:
        return "0.75-0.9 (medium-high)"
    if conf >= 0.5:
        return "0.5-0.75 (medium)"
    if conf > 0.0:
        return "0.0-0.5 (low)"
    return "0.0 (no match)"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=400, help="Target number of unique cases to collect")
    parser.add_argument("--review-sample-size", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)

    started = time.time()
    skip_counts: Dict[str, int] = {}

    # -- Phase 1: collect doc_ids -------------------------------------------------
    logger.info(f"Phase 1: collecting up to {args.target} unique doc_ids from Indian Kanoon search")
    search_results = await scrape.collect_doc_ids(args.target)
    logger.info(f"Collected {len(search_results)} unique doc_ids")

    # -- Phase 2: fetch + label + pre-precedent features --------------------------
    logger.info("Phase 2: fetching judgments, extracting labels + case profiles")
    processed: List[Dict[str, Any]] = []
    for i, sr in enumerate(search_results, 1):
        result = await process_case(sr)
        if result is None or result.get("skip_reason"):
            reason = (result or {}).get("skip_reason", "unknown")
            skip_counts[reason] = skip_counts.get(reason, 0) + 1
            logger.warning(f"[{i}/{len(search_results)}] SKIP {sr.doc_id}: {reason}")
            continue
        processed.append(result)
        if i % 20 == 0 or i == len(search_results):
            logger.info(f"[{i}/{len(search_results)}] processed (kept {len(processed)}, skipped {sum(skip_counts.values())})")

    await kanoon_service.close()

    if not processed:
        logger.error("No cases survived processing — aborting before dataset write.")
        return

    # -- Phase 3: leave-one-out precedent index -----------------------------------
    logger.info(f"Phase 3: building leave-one-out precedent index over {len(processed)} cases")
    precedent_index = PrecedentIndex()
    for i, item in enumerate(processed, 1):
        detail = item["detail"]
        await precedent_index.add_case(
            doc_id=detail.doc_id,
            title=detail.title,
            url=detail.url,
            court=detail.court,
            date=detail.date,
            feature_text=item["feature_text"],
        )
        if i % 50 == 0 or i == len(processed):
            logger.info(f"Embedded {i}/{len(processed)} cases into precedent index")
    precedent_index.save(PRECEDENT_INDEX_PATH)

    # -- Phase 4: assemble final feature rows --------------------------------------
    logger.info("Phase 4: assembling final feature rows")
    rows: List[Dict[str, Any]] = []
    for item in processed:
        detail = item["detail"]
        profile = item["profile"]
        graph_stats = item["graph_stats"]
        label_result = item["label_result"]

        precedents = precedent_index.leave_one_out_precedents(detail.doc_id, top_k=5)
        feat = assemble_features(profile, graph_stats, precedents)

        rows.append(
            {
                "case_id": detail.doc_id,
                "source_url": detail.url,
                "title": detail.title,
                "court": detail.court or "",
                "date": detail.date or "",
                "extracted_label": label_result["label"],
                "label_confidence": label_result["confidence"],
                "label_snippet": label_result["snippet"][:SNIPPET_MAIN_LEN],
                "label_snippet_full": label_result["snippet"],
                **feat,
            }
        )

    # -- Phase 5: write outputs -----------------------------------------------------
    logger.info(f"Phase 5: writing {len(rows)} rows to {DATASET_CSV}")
    with open(DATASET_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    sample_size = min(args.review_sample_size, len(rows))
    review_rows = random.sample(rows, sample_size)
    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)
    logger.info(f"Wrote {sample_size} rows to {REVIEW_CSV}")

    # -- Phase 6: summary -------------------------------------------------------
    label_counts: Dict[str, int] = {}
    confidence_buckets: Dict[str, int] = {}
    confidences = []
    for row in rows:
        label_counts[row["extracted_label"]] = label_counts.get(row["extracted_label"], 0) + 1
        confidences.append(row["label_confidence"])
        bucket = _confidence_bucket(row["label_confidence"])
        confidence_buckets[bucket] = confidence_buckets.get(bucket, 0) + 1

    elapsed = time.time() - started
    summary = {
        "target_count": args.target,
        "unique_doc_ids_found": len(search_results),
        "cases_written": len(rows),
        "skip_counts": skip_counts,
        "label_counts": label_counts,
        "label_percentages": {
            k: round(100 * v / len(rows), 1) for k, v in label_counts.items()
        },
        "confidence_buckets": confidence_buckets,
        "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "elapsed_seconds": round(elapsed, 1),
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Outcome dataset build summary",
        "",
        f"- Unique doc_ids found: {summary['unique_doc_ids_found']}",
        f"- Cases written to dataset.csv: {summary['cases_written']}",
        f"- Skipped: {sum(skip_counts.values())} ({skip_counts})",
        f"- Elapsed: {summary['elapsed_seconds']}s",
        "",
        "## Class balance",
        *[f"- {k}: {v} ({summary['label_percentages'][k]}%)" for k, v in label_counts.items()],
        "",
        "## Confidence distribution",
        *[f"- {k}: {v}" for k, v in confidence_buckets.items()],
        f"- Mean confidence: {summary['mean_confidence']}",
    ]
    SUMMARY_MD.write_text("\n".join(md_lines), encoding="utf-8")

    logger.info("=== DONE ===")
    logger.info(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
