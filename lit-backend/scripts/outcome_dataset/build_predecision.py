"""Build filing-based features with the live extraction and scoring services.

Run only after a reviewer has verified the manifest. The precedent index must
contain dated, published judgments; undated and post-filing results are skipped.
"""

import argparse
import asyncio
import csv
import hashlib
import json
from pathlib import Path

from models.schemas import SearchResult
from scripts.outcome_dataset.predecision_data import freeze_split, load_manifest
from services.embedder import EmbedderService
from services.extractor import extractor_service
from services.graph_builder import build_argument_graph
from services.precedent_filter import decision_before
from services.simulator import predict_outcome

FEATURE_KEYS = (
    "precedent_alignment", "statutory_strength", "argument_completeness",
    "case_complexity", "court_level",
)
COMPONENT_TO_KEY = {
    "Precedent Alignment": "precedent_alignment",
    "Statutory Strength": "statutory_strength",
    "Argument Completeness": "argument_completeness",
    "Case Complexity": "case_complexity",
    "Court Level": "court_level",
}


async def _precedents(embedder, query, case, top_k=5):
    if embedder.is_empty:
        return []
    vector = await embedder._get_embedding(query)
    hits = embedder.search(vector, top_k=embedder.total_vectors)
    found = []
    seen = {case.case_id}
    for hit in hits:
        meta = hit["metadata"]
        doc_id = str(meta.get("doc_id", ""))
        if not doc_id or doc_id in seen or meta.get("matter_id") == case.matter_id:
            continue
        if not decision_before(meta.get("date"), case.filing_date):
            continue
        seen.add(doc_id)
        found.append(SearchResult(
            title=meta.get("title", ""), url=meta.get("url", ""), doc_id=doc_id,
            court=meta.get("court"), date=meta.get("date"),
            snippet=(meta.get("text") or "")[:300],
            similarity_score=hit["similarity_score"],
        ))
        if len(found) == top_k:
            break
    return found


async def build(manifest: Path, precedent_index: Path, output_dir: Path, use_model: bool) -> None:
    if (output_dir / "training_report.json").exists() or (output_dir / "evaluation_report.json").exists():
        raise ValueError("Dataset version is sealed by training or evaluation; use a new output directory")
    cases = load_manifest(manifest)
    split = freeze_split(cases, output_dir / "frozen_split.json")
    embedder = EmbedderService()
    if not embedder.load_index(precedent_index):
        raise ValueError(f"Cannot load dated precedent index: {precedent_index}")
    if any(not item.get("date") for item in embedder._metadata):
        raise ValueError("Precedent index contains undated entries")

    rows = []
    try:
        for case in cases:
            text = case.text_path.read_text(encoding="utf-8")
            profile, meta = await extractor_service.extract(text, use_model=use_model)
            query = " ".join(profile.legal_issues) or text
            precedents = await _precedents(embedder, query, case)
            graph = build_argument_graph(profile, precedents[:3])
            prediction = predict_outcome(
                profile, precedents,
                {"node_count": graph["node_count"], "weak_nodes": graph["weak_nodes"]},
            )
            scores = {COMPONENT_TO_KEY[item.component]: item.raw_score for item in prediction.score_breakdown}
            if set(scores) != set(FEATURE_KEYS):
                raise ValueError(f"Feature contract mismatch for {case.case_id}")
            rows.append({
                "case_id": case.case_id,
                "matter_id": case.matter_id,
                "split": "holdout" if case.case_id in split["holdout_ids"] else "train",
                "filing_date": case.filing_date.isoformat(),
                "decision_date": case.decision_date.isoformat(),
                "court": case.court,
                "appellant_type": case.appellant_type,
                "outcome": case.outcome,
                "text_hash": case.text_hash,
                "outcome_cue_found": case.outcome_cue_found,
                "extraction_method": meta.extraction_method,
                "precedent_ids": json.dumps([item.doc_id for item in precedents]),
                **scores,
            })
    finally:
        await embedder.close()
        await extractor_service.close()

    methods = sorted({row["extraction_method"] for row in rows})
    if len(methods) != 1:
        raise ValueError(f"Mixed extraction methods {methods}; rebuild with a stable extraction mode")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "features.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "precedent_index_sha256": hashlib.sha256(precedent_index.read_bytes()).hexdigest(),
        "feature_order": list(FEATURE_KEYS) + ["appellant_type"],
        "use_model": use_model,
        "extraction_method": methods[0],
        "rows": len(rows),
        "outcome_cue_flags": sum(row["outcome_cue_found"] for row in rows),
    }
    (output_dir / "feature_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    by_id = {case.case_id: case for case in cases}
    chosen = set()
    for split_name in ("train", "holdout"):
        eligible = [row for row in rows if row["split"] == split_name]
        eligible.sort(key=lambda row: hashlib.sha256(row["case_id"].encode()).hexdigest())
        chosen.update(row["case_id"] for row in eligible[:25])
    chosen.update(row["case_id"] for row in rows if row["outcome_cue_found"])
    review_path = output_dir / "review_queue.csv"
    with review_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "case_id", "split", "text_path", "outcome", "outcome_cue_found", "reviewed", "issue_found",
        ])
        writer.writeheader()
        for row in rows:
            if row["case_id"] in chosen:
                writer.writerow({
                    "case_id": row["case_id"], "split": row["split"],
                    "text_path": str(by_id[row["case_id"]].text_path),
                    "outcome": row["outcome"], "outcome_cue_found": row["outcome_cue_found"],
                    "reviewed": "", "issue_found": "",
                })
    print(f"Wrote {len(rows)} cases to {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--precedent-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rules-only", action="store_true", help="Match a browser session with model extraction disabled")
    args = parser.parse_args()
    asyncio.run(build(args.manifest, args.precedent_index, args.output_dir, not args.rules_only))


if __name__ == "__main__":
    main()
