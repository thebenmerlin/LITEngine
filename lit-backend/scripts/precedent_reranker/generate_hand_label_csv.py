"""
Generates a hand-labeling CSV — the secondary validation set from the
labeling plan: harder, non-landmark candidates for you to judge
directly, since the citation-graph labels (scripts/precedent_reranker/
citation_labels.py) only cover "did the query cite one of the 38
famous, all-Supreme-Court landmarks" and can't tell us whether the
re-ranker is doing anything useful on the far more common case of
distinguishing among ordinary, non-landmark candidates.

Picks ~12 diverse query cases (spanning different courts/statute areas)
and for each, ranks a pool of ~150 other corpus documents by plain
cosine similarity, keeping the top 8 (plausible-looking candidates,
the hard cases) + 2 random far-ranked ones (clear negatives, for
scale/calibration). Relevance column is left BLANK for you to fill in
(0 = not relevant, 1 = somewhat relevant, 2 = highly relevant).

    ./venv/bin/python3 -m scripts.precedent_reranker.generate_hand_label_csv
"""

import csv
import random
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.precedent_reranker.citation_labels import load_corpus, load_landmarks
from scripts.precedent_reranker.evaluate import build_embeddings
from scripts.precedent_reranker.hybrid_scorer import cosine_similarity
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "precedent_reranker"
OUTPUT_CSV = DATA_DIR / "hand_label_pairs.csv"

N_QUERIES = 12
CANDIDATE_POOL_SIZE = 150
TOP_K_CANDIDATES = 8
N_FAR_CANDIDATES = 2
RANDOM_STATE = 42

CSV_COLUMNS = [
    "query_id", "query_title", "query_snippet",
    "candidate_id", "candidate_title", "candidate_snippet",
    "cosine_rank", "cosine_similarity",
    "relevance",  # BLANK for you to fill in: 0 / 1 / 2
]


def snippet(text: str, n: int = 300) -> str:
    return " ".join(text.split())[:n]


def pick_diverse_queries(docs: Dict[str, dict], landmark_ids: set, n: int) -> List[str]:
    rng = random.Random(RANDOM_STATE)
    candidates = [
        doc_id for doc_id, d in docs.items()
        if doc_id not in landmark_ids and len(d.get("text", "")) > 2000
    ]
    # Spread across distinct courts for topical variety rather than pure random
    by_court: Dict[str, List[str]] = {}
    for doc_id in candidates:
        court = docs[doc_id].get("court") or "Unknown"
        by_court.setdefault(court, []).append(doc_id)
    courts = list(by_court.keys())
    rng.shuffle(courts)

    picked = []
    ci = 0
    while len(picked) < n and courts:
        court = courts[ci % len(courts)]
        pool = by_court[court]
        if pool:
            picked.append(pool.pop(rng.randrange(len(pool))))
        if not pool:
            courts.remove(court)
            ci = 0
            continue
        ci += 1
    return picked[:n]


async def main() -> None:
    docs = load_corpus()
    landmarks = load_landmarks()
    landmark_ids = {l["doc_id"] for l in landmarks}

    query_ids = pick_diverse_queries(docs, landmark_ids, N_QUERIES)
    logger.info(f"Picked {len(query_ids)} diverse queries: {query_ids}")

    rng = random.Random(RANDOM_STATE)
    remaining = [d for d in docs if d not in landmark_ids and d not in query_ids]
    rng.shuffle(remaining)
    candidate_pool = remaining[:CANDIDATE_POOL_SIZE]

    all_doc_ids = sorted(set(query_ids) | set(candidate_pool))
    texts = {doc_id: docs[doc_id]["text"] for doc_id in all_doc_ids}
    logger.info(f"Building embeddings for {len(all_doc_ids)} documents...")
    embeddings = await build_embeddings(all_doc_ids, texts)

    rows = []
    for query_id in query_ids:
        q_emb = embeddings[query_id]
        ranked = sorted(
            candidate_pool,
            key=lambda c: cosine_similarity(q_emb, embeddings[c]),
            reverse=True,
        )
        top = ranked[:TOP_K_CANDIDATES]
        far = ranked[-N_FAR_CANDIDATES:] if len(ranked) > N_FAR_CANDIDATES else []
        selected = top + far

        for rank, candidate_id in enumerate(selected, 1):
            sim = cosine_similarity(q_emb, embeddings[candidate_id])
            rows.append({
                "query_id": query_id,
                "query_title": docs[query_id]["title"],
                "query_snippet": snippet(docs[query_id]["text"]),
                "candidate_id": candidate_id,
                "candidate_title": docs[candidate_id]["title"],
                "candidate_snippet": snippet(docs[candidate_id]["text"]),
                "cosine_rank": rank if candidate_id in top else f"far({ranked.index(candidate_id)+1}/{len(ranked)})",
                "cosine_similarity": round(sim, 4),
                "relevance": "",
            })

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    logger.info(f"Wrote {len(rows)} (query, candidate) pairs across {len(query_ids)} queries to {OUTPUT_CSV}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
