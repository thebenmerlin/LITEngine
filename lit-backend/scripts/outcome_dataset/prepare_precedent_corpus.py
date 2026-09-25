"""Stage dated cached judgments as precedents, never as case feature text.

The output manifest is accepted by build_precedent_index. Each source is a
published judgment in data/raw_cache; pre-decision filings need a separate
manifest and independent provenance review.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from scripts.outcome_dataset.dedup import find_duplicate_clusters


def stage(cache_dir: Path, output_dir: Path) -> dict:
    cache_dir = cache_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory is not empty; use a new corpus version")

    records = {}
    reasons = Counter()
    for path in sorted(cache_dir.glob("*.json")):
        try:
            raw = path.read_bytes()
            record = json.loads(raw)
            doc_id = str(record.get("doc_id", ""))
            date_value = date.fromisoformat(str(record.get("date", ""))).isoformat()
            title = str(record.get("title", "")).strip()
            court = str(record.get("court", "")).strip()
            text = str(record.get("text", "")).strip()
            url = str(record.get("url", "")).strip()
            if not re.fullmatch(r"[0-9]+", doc_id) or path.stem != doc_id:
                raise ValueError("doc_id mismatch")
            if not title or not court or len(text.split()) < 50:
                raise ValueError("missing title, court, or substantive text")
            if url != f"https://indiankanoon.org/doc/{doc_id}/":
                raise ValueError("unexpected source URL")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            reasons[str(exc)] += 1
            continue
        records[doc_id] = {
            "date": date_value, "title": title, "court": court,
            "text": text, "url": url,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
        }
    if not records:
        raise ValueError(f"No valid dated judgments in {cache_dir}")

    clusters = find_duplicate_clusters(
        {key: value["text"] for key, value in records.items()},
        {key: value["date"] for key, value in records.items()},
    )
    aliases = {}
    for cluster in clusters:
        representative = min(cluster, key=int)
        for doc_id in cluster:
            aliases[doc_id] = representative
    selected = [doc_id for doc_id in records if aliases.get(doc_id, doc_id) == doc_id]
    selected.sort(key=lambda doc_id: (records[doc_id]["date"], int(doc_id)))

    text_dir = output_dir / "texts"
    text_dir.mkdir(parents=True)
    manifest_path = output_dir / "precedents.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "doc_id", "matter_id", "title", "text_path", "decision_date",
            "court", "url", "source_sha256", "text_sha256",
        ])
        writer.writeheader()
        for doc_id in selected:
            record = records[doc_id]
            text_path = text_dir / f"{doc_id}.txt"
            text_path.write_text(record["text"] + "\n", encoding="utf-8")
            writer.writerow({
                "doc_id": doc_id, "matter_id": doc_id,
                "title": record["title"], "text_path": f"texts/{doc_id}.txt",
                "decision_date": record["date"], "court": record["court"],
                "url": record["url"],
                "source_sha256": record["source_sha256"],
                "text_sha256": hashlib.sha256(text_path.read_bytes()).hexdigest(),
            })
    summary = {
        "source": str(cache_dir),
        "scanned": sum(1 for _ in cache_dir.glob("*.json")),
        "valid_dated": len(records),
        "excluded": dict(reasons),
        "near_duplicate_clusters": len(clusters),
        "near_duplicate_rows_removed": len(records) - len(selected),
        "indexed_judgments": len(selected),
        "decision_years": dict(sorted(Counter(records[doc_id]["date"][:4] for doc_id in selected).items())),
        "duplicate_aliases": aliases,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw_cache"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.cache_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
