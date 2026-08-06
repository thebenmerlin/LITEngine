"""
CLI entrypoint: builds dataset_v2.csv from the existing dataset.csv +
raw_cache, applying four fixes found by manually reviewing the first
50-case sample:

  1. Deduplication — collapse near-identical judgments that Kanoon
     indexed multiple times under different appellant names (dedup.py).
  2. Scope filter — hard-exclude Writ Petitions/Writ Appeals on
     unrelated subject matter that the search queries swept in, flag
     genuinely borderline cases rather than deciding for the user
     (scope_filter.py).
  3. Appellant type — state_appeal / accused_appeal / unclear, so
     "allowed"/"dismissed" can be interpreted consistently
     (appellant_type.py).
  4. Confidence-band re-audit — labeling.py itself was fixed (negation,
     conditional/hypothetical framing, interim-relief false positives,
     a previously-unrecognized "Rule made absolute/discharged" disposal
     idiom, and a conflict-detection gap) and is re-run here across all
     rows, not just the 0.4-0.6 band, since the same bugs affected some
     higher-confidence rows too (validated with zero regressions against
     220 previously >=0.75-confidence rows).

Does NOT touch simulator.py or re-scrape anything — reuses the existing
dataset.csv for source_url/title/court/date/case_type and the existing 5
simulator features as-is, and the existing raw_cache/ for full judgment
text. Original dataset.csv / manual_review_sample.csv are left
untouched as a paper trail.
"""

import csv
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List

from scripts.outcome_dataset.appellant_type import classify_appellant_type
from scripts.outcome_dataset.dedup import find_duplicate_clusters, pick_cluster_representative
from scripts.outcome_dataset.labeling import extract_outcome_label
from scripts.outcome_dataset.scope_filter import classify_scope
from scripts.outcome_dataset.scrape import load_cached_judgment
from utils.logger import get_logger

logger = get_logger(__name__)

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "outcome_dataset"
ORIGINAL_CSV = OUT_DIR / "dataset.csv"
V2_CSV = OUT_DIR / "dataset_v2.csv"
V2_REVIEW_CSV = OUT_DIR / "manual_review_sample_v2.csv"
V2_SUMMARY_JSON = OUT_DIR / "summary_v2.json"
V2_SUMMARY_MD = OUT_DIR / "summary_v2.md"

REVIEW_SAMPLE_SIZE = 50
SEED = 42

USABLE_CONFIDENCE_THRESHOLD = 0.6

V2_COLUMNS = [
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
    "appellant_type",
    "appellant_type_confidence",
    "borderline_scope",
    "borderline_scope_reason",
    "dedup_cluster_size",
]

REVIEW_COLUMNS = [
    "case_id",
    "source_url",
    "title",
    "extracted_label",
    "label_confidence",
    "label_snippet_full",
    "appellant_type",
    "appellant_type_confidence",
    "borderline_scope",
    "dedup_cluster_size",
]


def main() -> None:
    started = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)

    with open(ORIGINAL_CSV, encoding="utf-8") as f:
        original_rows = {r["case_id"]: r for r in csv.DictReader(f)}
    logger.info(f"Loaded {len(original_rows)} rows from {ORIGINAL_CSV}")

    # -- Phase 1: re-run labeling with the fixed logic, over ALL rows ----------
    logger.info("Phase 1: re-running outcome labeling with fixed logic")
    doc_texts: Dict[str, str] = {}
    doc_dates: Dict[str, str] = {}
    labels: Dict[str, str] = {}
    confidences: Dict[str, float] = {}
    snippets: Dict[str, str] = {}
    label_changed_count = 0

    for case_id, row in original_rows.items():
        detail = load_cached_judgment(case_id)
        if detail is None:
            logger.warning(f"No cached judgment for {case_id} — skipping entirely")
            continue
        doc_texts[case_id] = detail.text
        doc_dates[case_id] = detail.date or row.get("date") or ""

        result = extract_outcome_label(detail.text)
        labels[case_id] = result["label"]
        confidences[case_id] = result["confidence"]
        snippets[case_id] = result["snippet"]
        if result["label"] != row["extracted_label"]:
            label_changed_count += 1

    logger.info(f"Re-labeling complete: {label_changed_count} rows changed label vs. original dataset.csv")

    # -- Phase 2: deduplication --------------------------------------------------
    logger.info("Phase 2: finding near-duplicate clusters")
    clusters = find_duplicate_clusters(doc_texts, doc_dates)
    clustered_ids = {cid for cluster in clusters for cid in cluster}
    logger.info(f"Found {len(clusters)} clusters covering {len(clustered_ids)} rows")

    cluster_size_of: Dict[str, int] = {}
    representative_of_cluster: Dict[str, str] = {}
    collapsed_label: Dict[str, str] = {}
    collapsed_confidence: Dict[str, float] = {}

    for cluster in clusters:
        rep, label, conf = pick_cluster_representative(cluster, labels, confidences)
        for cid in cluster:
            representative_of_cluster[cid] = rep
        cluster_size_of[rep] = len(cluster)
        collapsed_label[rep] = label
        collapsed_confidence[rep] = conf

    survivors: List[str] = []
    seen_reps = set()
    for case_id in doc_texts:
        if case_id in clustered_ids:
            rep = representative_of_cluster[case_id]
            if rep in seen_reps:
                continue
            seen_reps.add(rep)
            survivors.append(rep)
        else:
            survivors.append(case_id)

    rows_before_dedup = len(doc_texts)
    rows_after_dedup = len(survivors)
    logger.info(f"Dedup collapse: {rows_before_dedup} -> {rows_after_dedup} rows ({rows_before_dedup - rows_after_dedup} removed)")

    # -- Phase 3: scope filter ---------------------------------------------------
    logger.info("Phase 3: scope filter (hard-exclude / borderline)")
    hard_excluded: List[str] = []
    borderline: Dict[str, str] = {}
    in_scope: List[str] = []

    for case_id in survivors:
        text = doc_texts[case_id]
        result = classify_scope(text)
        if result.hard_exclude:
            hard_excluded.append(case_id)
        else:
            in_scope.append(case_id)
            if result.borderline_scope:
                borderline[case_id] = result.reason

    logger.info(f"Scope filter: {len(hard_excluded)} hard-excluded, {len(borderline)} borderline, {len(in_scope)} remain")

    # -- Phase 4: appellant type --------------------------------------------------
    logger.info("Phase 4: appellant-type classification")
    appellant_types: Dict[str, str] = {}
    appellant_confidences: Dict[str, float] = {}
    for case_id in in_scope:
        row = original_rows[case_id]
        result = classify_appellant_type(row["title"], doc_texts[case_id])
        appellant_types[case_id] = result.appellant_type
        appellant_confidences[case_id] = result.confidence

    # -- Phase 5: assemble dataset_v2 rows ----------------------------------------
    logger.info("Phase 5: assembling dataset_v2 rows")
    v2_rows: List[Dict[str, Any]] = []
    for case_id in in_scope:
        row = original_rows[case_id]
        label = collapsed_label.get(case_id, labels[case_id])
        confidence = collapsed_confidence.get(case_id, confidences[case_id])
        snippet = snippets[case_id]

        v2_rows.append({
            **row,  # source_url, title, court, date, case_type, all feature_* columns
            "extracted_label": label,
            "label_confidence": confidence,
            "label_snippet": snippet[:400],
            "label_snippet_full": snippet,
            "appellant_type": appellant_types[case_id],
            "appellant_type_confidence": appellant_confidences[case_id],
            "borderline_scope": case_id in borderline,
            "borderline_scope_reason": borderline.get(case_id, ""),
            "dedup_cluster_size": cluster_size_of.get(case_id, 1),
        })

    with open(V2_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=V2_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in v2_rows:
            writer.writerow(row)
    logger.info(f"Wrote {len(v2_rows)} rows to {V2_CSV}")

    sample_size = min(REVIEW_SAMPLE_SIZE, len(v2_rows))
    review_rows = random.sample(v2_rows, sample_size)
    with open(V2_REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)
    logger.info(f"Wrote {sample_size} rows to {V2_REVIEW_CSV}")

    # -- Phase 6: summary -----------------------------------------------------
    label_counts: Dict[str, int] = {}
    for row in v2_rows:
        label_counts[row["extracted_label"]] = label_counts.get(row["extracted_label"], 0) + 1

    appellant_counts: Dict[str, int] = {}
    for row in v2_rows:
        appellant_counts[row["appellant_type"]] = appellant_counts.get(row["appellant_type"], 0) + 1

    def _bucket(conf: float) -> str:
        if conf >= 0.9:
            return "0.9-1.0 (high)"
        if conf >= 0.75:
            return "0.75-0.9 (medium-high)"
        if conf >= 0.6:
            return "0.6-0.75 (medium)"
        if conf > 0.0:
            return "0.0-0.6 (low)"
        return "0.0 (no match)"

    confidence_buckets: Dict[str, int] = {}
    for row in v2_rows:
        b = _bucket(row["label_confidence"])
        confidence_buckets[b] = confidence_buckets.get(b, 0) + 1

    usable_rows = [
        row for row in v2_rows
        if row["extracted_label"] != "unclear"
        and row["label_confidence"] >= USABLE_CONFIDENCE_THRESHOLD
        and not row["borderline_scope"]
    ]

    borderline_list = [
        {"case_id": cid, "reason": reason}
        for cid, reason in borderline.items()
    ]

    summary = {
        "rows_before_dedup": rows_before_dedup,
        "rows_after_dedup": rows_after_dedup,
        "dedup_clusters_found": len(clusters),
        "dedup_rows_removed": rows_before_dedup - rows_after_dedup,
        "hard_excluded_count": len(hard_excluded),
        "hard_excluded_ids": hard_excluded,
        "borderline_scope_count": len(borderline),
        "final_row_count": len(v2_rows),
        "label_counts": label_counts,
        "label_percentages": {k: round(100 * v / len(v2_rows), 1) for k, v in label_counts.items()},
        "appellant_type_counts": appellant_counts,
        "appellant_type_percentages": {k: round(100 * v / len(v2_rows), 1) for k, v in appellant_counts.items()},
        "confidence_buckets": confidence_buckets,
        "mean_confidence": round(sum(r["label_confidence"] for r in v2_rows) / len(v2_rows), 3),
        "relabeled_count_vs_original": label_changed_count,
        "usable_n": len(usable_rows),
        "usable_n_definition": "label != unclear AND confidence >= 0.6 AND not borderline_scope",
        "elapsed_seconds": round(time.time() - started, 1),
    }

    V2_SUMMARY_JSON.write_text(json.dumps({**summary, "borderline_scope_list": borderline_list}, indent=2), encoding="utf-8")

    md_lines = [
        "# Outcome dataset v2 — audit summary",
        "",
        "## Deduplication",
        f"- Rows before dedup: {rows_before_dedup}",
        f"- Clusters found: {len(clusters)}",
        f"- Rows removed (collapsed into a representative row): {summary['dedup_rows_removed']}",
        f"- Rows after dedup: {rows_after_dedup}",
        "",
        "## Scope filter",
        f"- Hard-excluded (Writ Petition/Appeal, unrelated subject matter): {len(hard_excluded)}",
        f"- Flagged borderline_scope (needs your review): {len(borderline)}",
        f"- Final row count (dataset_v2.csv): {len(v2_rows)}",
        "",
        "### borderline_scope cases (for your review)",
        *[f"- {b['case_id']}: {b['reason']}" for b in borderline_list],
        "",
        "## Class balance (dataset_v2.csv)",
        *[f"- {k}: {v} ({summary['label_percentages'][k]}%)" for k, v in label_counts.items()],
        "",
        "## Appellant type",
        *[f"- {k}: {v} ({summary['appellant_type_percentages'][k]}%)" for k, v in appellant_counts.items()],
        "",
        "## Confidence distribution (after re-audit)",
        *[f"- {k}: {v}" for k, v in confidence_buckets.items()],
        f"- Mean confidence: {summary['mean_confidence']}",
        f"- Rows whose label changed vs. original dataset.csv (fixed labeling logic): {label_changed_count}",
        "",
        "## Usable N",
        f"- **{summary['usable_n']}** rows where label != unclear AND confidence >= 0.6 AND not borderline_scope",
        f"- ({round(100*summary['usable_n']/len(v2_rows),1)}% of dataset_v2.csv, {round(100*summary['usable_n']/rows_before_dedup,1)}% of the original 505)",
    ]
    V2_SUMMARY_MD.write_text("\n".join(md_lines), encoding="utf-8")

    logger.info("=== DONE ===")
    logger.info(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
