"""
Evaluates the hybrid re-ranker against the plain-cosine baseline on
citation-graph-derived relevance labels: for each query judgment that
cites >=1 scraped landmark, rank ALL landmarks by (a) plain cosine
similarity [baseline] and (b) the fitted hybrid score, then compare
precision@k / nDCG@k against the true citation set.

Query-level K-fold: weights are fit on TRAIN queries' pairs only and
evaluated on TEST queries never seen during fitting — same discipline
as the outcome-model sessions (no evaluating on what you fit on).

    ./venv/bin/python3 -m scripts.precedent_reranker.evaluate
"""

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset.scrape import load_cached_judgment
from scripts.precedent_reranker.citation_labels import build_labeled_triples, load_corpus, load_landmarks
from scripts.precedent_reranker.hybrid_scorer import (
    FEATURE_NAMES,
    extract_pair_features,
    fit_hybrid_weights,
    get_weight_report,
    hybrid_score,
)
from services.embedder import EmbedderService, _chunk_text
from services.extractor import _extract_court_level_rules
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "precedent_reranker"
RESULTS_JSON = DATA_DIR / "evaluation_results.json"
RESULTS_MD = DATA_DIR / "evaluation_results.md"

N_SPLITS = 5
K_VALUES = [3, 5]
REFERENCE_DATE = date(2026, 8, 7)  # "today" per session context — fixed for reproducibility
RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Embeddings (mirrors scripts/outcome_dataset/features.py's PrecedentIndex
# pattern: chunk + embed + mean-pool to one doc-level vector, via a fresh
# EmbedderService instance — reuses the existing embedding pipeline,
# doesn't touch the live singleton or rebuild anything)
# ---------------------------------------------------------------------------

async def embed_doc(embedder: EmbedderService, text: str) -> np.ndarray:
    chunks = _chunk_text(text)
    if not chunks:
        return np.zeros(embedder.dimension, dtype=np.float32)
    embeddings = await embedder.embed_texts(chunks)
    return np.mean(np.array(embeddings, dtype=np.float32), axis=0)


async def build_embeddings(doc_ids: List[str], texts: Dict[str, str]) -> Dict[str, np.ndarray]:
    embedder = EmbedderService()
    vectors = {}
    for i, doc_id in enumerate(doc_ids, 1):
        vectors[doc_id] = await embed_doc(embedder, texts[doc_id])
        if i % 20 == 0 or i == len(doc_ids):
            logger.info(f"Embedded {i}/{len(doc_ids)} docs")
    return vectors


# ---------------------------------------------------------------------------
# Ranking metrics
# ---------------------------------------------------------------------------

def precision_at_k(ranked_ids: List[str], relevant_set: set, k: int) -> float:
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    return sum(1 for d in top_k if d in relevant_set) / len(top_k)


def ndcg_at_k(ranked_ids: List[str], relevant_set: set, k: int) -> float:
    def dcg(ids: List[str]) -> float:
        return sum(
            (1.0 if doc_id in relevant_set else 0.0) / math.log2(i + 2)
            for i, doc_id in enumerate(ids)
        )

    actual = dcg(ranked_ids[:k])
    ideal_order = sorted(ranked_ids, key=lambda d: d not in relevant_set)  # relevant first
    ideal = dcg(ideal_order[:k])
    return actual / ideal if ideal > 0 else 0.0


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

async def main() -> None:
    docs = load_corpus()
    landmarks = load_landmarks()
    triples, query_ids = build_labeled_triples(docs, landmarks)

    n_pos = sum(1 for _, _, l in triples if l == 1)
    logger.info(
        f"Landmarks: {len(landmarks)} | Queries citing >=1 landmark: {len(query_ids)} | "
        f"Pairs: {len(triples)} ({n_pos} positive)"
    )

    if len(query_ids) < N_SPLITS:
        logger.error(f"Only {len(query_ids)} queries available — not enough for {N_SPLITS}-fold. Aborting.")
        return

    # -- Embeddings: all queries + all landmarks, computed once ------------------
    landmark_ids = [l["doc_id"] for l in landmarks]
    all_doc_ids = sorted(set(query_ids) | set(landmark_ids))
    texts = {}
    court_levels = {}
    dates = {}
    for doc_id in all_doc_ids:
        d = docs.get(doc_id) or load_cached_judgment(doc_id)
        text = d["text"] if isinstance(d, dict) else d.text
        texts[doc_id] = text
        court = (d.get("court") if isinstance(d, dict) else d.court) or ""
        court_levels[doc_id] = _extract_court_level_rules(court) if court else "Unknown"
        dates[doc_id] = d.get("date") if isinstance(d, dict) else d.date

    logger.info(f"Building embeddings for {len(all_doc_ids)} unique documents (queries + landmarks)...")
    embeddings = await build_embeddings(all_doc_ids, texts)

    # -- Precompute pair features for every (query, landmark) pair ---------------
    logger.info("Computing pairwise hybrid features for all (query, landmark) pairs...")
    pair_features: Dict[Tuple[str, str], Dict[str, float]] = {}
    for query_id, landmark_id, _ in triples:
        key = (query_id, landmark_id)
        if key in pair_features:
            continue
        pair_features[key] = extract_pair_features(
            query_embedding=embeddings[query_id],
            candidate_embedding=embeddings[landmark_id],
            query_text=texts[query_id],
            candidate_text=texts[landmark_id],
            candidate_date=dates[landmark_id],
            reference_date=REFERENCE_DATE,
            query_court_level=court_levels[query_id],
            candidate_court_level=court_levels[landmark_id],
        )

    # -- Query-level K-fold: fit on train queries, evaluate on test queries ------
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    query_arr = np.array(query_ids)

    fold_results = {"baseline": {f"p@{k}": [] for k in K_VALUES}, "hybrid": {f"p@{k}": [] for k in K_VALUES}}
    for k in K_VALUES:
        fold_results["baseline"][f"ndcg@{k}"] = []
        fold_results["hybrid"][f"ndcg@{k}"] = []

    weight_reports = []

    for fold_idx, (train_idx, test_idx) in enumerate(kf.split(query_arr)):
        train_queries = set(query_arr[train_idx])
        test_queries = set(query_arr[test_idx])

        train_rows, train_labels = [], []
        for q, l, label in triples:
            if q in train_queries:
                train_rows.append(pair_features[(q, l)])
                train_labels.append(label)

        pipeline = fit_hybrid_weights(train_rows, train_labels)
        weight_reports.append(get_weight_report(pipeline))

        for query_id in test_queries:
            relevant_set = {l for q, l, label in triples if q == query_id and label == 1}
            if not relevant_set:
                continue

            candidates = landmark_ids
            baseline_ranked = sorted(
                candidates, key=lambda c: pair_features[(query_id, c)]["cosine_similarity"], reverse=True
            )
            hybrid_ranked = sorted(
                candidates, key=lambda c: hybrid_score(pipeline, pair_features[(query_id, c)]), reverse=True
            )

            for k in K_VALUES:
                fold_results["baseline"][f"p@{k}"].append(precision_at_k(baseline_ranked, relevant_set, k))
                fold_results["baseline"][f"ndcg@{k}"].append(ndcg_at_k(baseline_ranked, relevant_set, k))
                fold_results["hybrid"][f"p@{k}"].append(precision_at_k(hybrid_ranked, relevant_set, k))
                fold_results["hybrid"][f"ndcg@{k}"].append(ndcg_at_k(hybrid_ranked, relevant_set, k))

        logger.info(f"Fold {fold_idx+1}/{N_SPLITS}: {len(train_queries)} train queries, {len(test_queries)} test queries")

    # -- Aggregate ------------------------------------------------------------
    summary = {"n_landmarks": len(landmarks), "n_queries": len(query_ids), "n_pairs": len(triples), "n_positive_pairs": n_pos}
    for approach in ["baseline", "hybrid"]:
        summary[approach] = {}
        for metric, values in fold_results[approach].items():
            summary[approach][metric] = {
                "mean": float(np.mean(values)) if values else None,
                "std": float(np.std(values)) if values else None,
                "n": len(values),
            }

    avg_weights = {name: float(np.mean([wr[name] for wr in weight_reports])) for name in FEATURE_NAMES}
    summary["avg_standardized_coefficients"] = avg_weights

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = ["# Precedent hybrid re-ranker — evaluation results", ""]
    lines.append(f"- Landmarks: {len(landmarks)} | Queries: {len(query_ids)} | Pairs: {len(triples)} ({n_pos} positive)")
    lines.append(f"- {N_SPLITS}-fold, query-level split (weights fit on train queries only, never evaluated on)")
    lines.append("")
    lines.append("| Metric | Cosine baseline | Hybrid re-ranker |")
    lines.append("|---|---|---|")
    for k in K_VALUES:
        b_p = summary["baseline"][f"p@{k}"]
        h_p = summary["hybrid"][f"p@{k}"]
        lines.append(f"| precision@{k} | {b_p['mean']:.3f} ± {b_p['std']:.3f} | {h_p['mean']:.3f} ± {h_p['std']:.3f} |")
    for k in K_VALUES:
        b_n = summary["baseline"][f"ndcg@{k}"]
        h_n = summary["hybrid"][f"ndcg@{k}"]
        lines.append(f"| nDCG@{k} | {b_n['mean']:.3f} ± {b_n['std']:.3f} | {h_n['mean']:.3f} ± {h_n['std']:.3f} |")
    lines.append("")
    lines.append("## Average standardized coefficients (fit across folds)")
    lines.append("")
    for name, val in avg_weights.items():
        lines.append(f"- {name}: {val:+.3f}")
    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    logger.info(f"Saved results to {RESULTS_JSON} and {RESULTS_MD}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
