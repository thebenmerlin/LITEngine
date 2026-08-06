"""
Builds relevance-labeled (query, landmark, label) triples from real
citation relationships: if judgment Q's own citations list contains
landmark L's reporter citation string, Q genuinely relied on L —
label=1. Every other (Q, L) pair where Q doesn't cite L is label=0.

This is a real, judicially-determined relevance signal (an actual
citation), not a synthetic proxy — see scrape_landmarks.py for why two
cheaper automated alternatives were tried and rejected (near-zero
cross-corpus citation-string matches; noisy party-name matching).

The evaluation task this sets up directly mirrors real precedent
search: "given this case, which of these known candidate precedents
did it actually rely on" — full cross product of {queries that cite
>=1 landmark} x {all landmarks}, most pairs are negative (a query only
cites a handful of the ~dozen landmarks), same imbalance-handling
approach (class_weight='balanced') as the outcome model.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset.scrape import RAW_CACHE_DIR

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "precedent_reranker"
LANDMARKS_MAP_PATH = DATA_DIR / "landmark_citation_map.json"


def load_landmarks() -> List[dict]:
    return json.loads(LANDMARKS_MAP_PATH.read_text(encoding="utf-8"))


def load_corpus() -> Dict[str, dict]:
    docs = {}
    for f in RAW_CACHE_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            docs[d["doc_id"]] = d
        except (json.JSONDecodeError, KeyError):
            continue
    return docs


def build_labeled_triples(
    docs: Dict[str, dict], landmarks: List[dict]
) -> Tuple[List[Tuple[str, str, int]], List[str]]:
    """
    Returns:
        triples: list of (query_doc_id, landmark_doc_id, label)
        query_ids: distinct query doc_ids that cite >= 1 landmark
            (queries citing zero landmarks carry no signal either way
            and are excluded — including them would just add label-0
            rows for every landmark with no counterbalancing positive,
            diluting the signal without adding information)
    """
    landmark_doc_ids = {l["doc_id"] for l in landmarks}
    citation_to_landmark_doc = {l["citation"]: l["doc_id"] for l in landmarks}

    query_cites: Dict[str, set] = {}
    for doc_id, d in docs.items():
        if doc_id in landmark_doc_ids:
            continue  # don't use a landmark as a query against itself/other landmarks
        doc_citations = {c.strip().upper() for c in d.get("citations", [])}
        cited_landmarks = {
            citation_to_landmark_doc[cite]
            for cite in doc_citations
            if cite in citation_to_landmark_doc
        }
        if cited_landmarks:
            query_cites[doc_id] = cited_landmarks

    triples: List[Tuple[str, str, int]] = []
    for query_id, cited_set in query_cites.items():
        for landmark in landmarks:
            label = 1 if landmark["doc_id"] in cited_set else 0
            triples.append((query_id, landmark["doc_id"], label))

    return triples, sorted(query_cites.keys())


if __name__ == "__main__":
    docs = load_corpus()
    landmarks = load_landmarks()
    triples, query_ids = build_labeled_triples(docs, landmarks)
    n_pos = sum(1 for _, _, l in triples if l == 1)
    print(f"Landmarks: {len(landmarks)}")
    print(f"Queries citing >=1 landmark: {len(query_ids)}")
    print(f"Total (query, landmark) pairs: {len(triples)} ({n_pos} positive, {len(triples)-n_pos} negative)")
