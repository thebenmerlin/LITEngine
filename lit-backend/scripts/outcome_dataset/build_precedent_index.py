"""Build a dated precedent index for filing-based model evaluation.

CSV columns: doc_id,matter_id,title,text_path,decision_date,court,url.
Every row must identify a published judgment and its decision date.
"""

import argparse
import asyncio
import csv
import hashlib
from datetime import date
from pathlib import Path

import numpy as np

from services.embedder import EmbedderService, _chunk_text

REQUIRED = {"doc_id", "matter_id", "title", "text_path", "decision_date", "court", "url"}


async def build(manifest: Path, output: Path):
    manifest = manifest.resolve()
    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if REQUIRED - set(reader.fieldnames or ()):
            raise ValueError(f"Missing columns: {sorted(REQUIRED - set(reader.fieldnames or ()))}")
        rows = list(reader)
    if not rows:
        raise ValueError("Precedent manifest is empty")
    seen = set()
    embedder = EmbedderService()
    try:
        for row in rows:
            doc_id = row["doc_id"].strip()
            if not doc_id or doc_id in seen:
                raise ValueError(f"Missing or duplicate precedent doc_id: {doc_id}")
            if not row["matter_id"].strip():
                raise ValueError(f"Missing matter_id for {doc_id}")
            seen.add(doc_id)
            decision_date = date.fromisoformat(row["decision_date"].strip()).isoformat()
            text_path = (manifest.parent / row["text_path"].strip()).resolve()
            if not text_path.is_relative_to(manifest.parent) or not text_path.is_file():
                raise ValueError(f"Invalid text_path for {doc_id}")
            text_bytes = text_path.read_bytes()
            expected_hash = row.get("text_sha256", "").strip()
            if expected_hash and hashlib.sha256(text_bytes).hexdigest() != expected_hash:
                raise ValueError(f"Text changed after manifest staging for {doc_id}")
            chunks = _chunk_text(text_bytes.decode("utf-8"))
            if not chunks:
                raise ValueError(f"Empty precedent text for {doc_id}")
            vectors = np.asarray(await embedder.embed_texts(chunks), dtype=np.float32)
            metadata = [
                {
                    "doc_id": doc_id,
                    "matter_id": row["matter_id"].strip(),
                    "title": row["title"].strip(),
                    "url": row["url"].strip(),
                    "court": row["court"].strip(),
                    "date": decision_date,
                    "text": chunk,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                for i, chunk in enumerate(chunks)
            ]
            embedder.add_vectors(vectors, metadata)
        embedder.save_index(output)
    finally:
        await embedder.close()
    print(f"Indexed {len(rows)} dated judgments at {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(build(args.manifest, args.output))


if __name__ == "__main__":
    main()
