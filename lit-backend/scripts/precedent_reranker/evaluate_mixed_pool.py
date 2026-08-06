"""
Second evaluation design, run after the landmark-only evaluation
(evaluate.py) showed the hybrid re-ranker losing to plain cosine on
every metric, with all-zero court_score coefficients — diagnosed as an
artifact of the candidate pool: ranking among 38 hand-picked, all-
prestigious Supreme Court landmarks is a narrow, atypical task (every
candidate is "important," court level and citation-worthiness don't
vary), unlike real precedent search where most candidates are
plausible-looking but irrelevant and court level genuinely varies.

This adds a fixed pool of 100 random "distractor" documents (sampled
once, shared across all queries — not per-query, for efficiency and
determinism) from the general corpus to each query's candidate set.
Distractors are treated as label=0 (not cited) — an accepted, standard
simplifying assumption of citation-based silver labeling: a distractor
COULD in principle be tangentially relevant without being cited, but
absent citation there's no ground-truth signal either way, so it's
scored as a negative like any other non-cited candidate.

Both this result and the landmark-only result are reported side by
side in the final write-up — not cherry-picking whichever looks
better.

    ./venv/bin/python3 -m scripts.precedent_reranker.evaluate_mixed_pool
"""

import json
import math
import random
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset.scrape import load_cached_judgment
from scripts.precedent_reranker.citation_labels import build_labeled_triples, load_corpus, load_landmarks
from scripts.precedent_reranker.evaluate import build_embeddings, ndcg_at_k, precision_at_k
from scripts.precedent_reranker.hybrid_scorer import (
    FEATURE_NAMES,
    extract_pair_features,
    fit_hybrid_weights,
    get_weight_report,
    hybrid_score,
)
from services.extractor import _extract_court_level_rules
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "precedent_reranker"
RESULTS_JSON = DATA_DIR / "evaluation_results_mixed_pool.json"
RESULTS_MD = DATA_DIR / "evaluation_results_mixed_pool.md"

N_DISTRACTORS = 100
N_SPLITS = 5
K_VALUES = [3, 5]
REFERENCE_DATE = date(2026, 8, 7)
RANDOM_STATE = 42


def sample_distractors(docs: Dict[str, dict], landmark_ids: set, query_ids: set, n: int) -> List[str]:
    # Exclude query_ids too — otherwise a query doc could land in its own
    # candidate pool as a trivial cosine=1.0 self-match (not counted as
    # relevant since it's not a landmark, but noise worth avoiding).
    rng = random.Random(RANDOM_STATE)
    pool = [d for d in docs if d not in landmark_ids and d not in query_ids]
    rng.shuffle(pool)
    return pool[:n]


async def main() -> None:
    docs = load_corpus()
    landmarks = load_landmarks()
    triples, query_ids = build_labeled_triples(docs, landmarks)
    landmark_ids = [l["doc_id"] for l in landmarks]

    distractor_ids = sample_distractors(docs, set(landmark_ids), set(query_ids), N_DISTRACTORS)
    candidate_pool = landmark_ids + distractor_ids
    logger.info(f"Candidate pool: {len(landmark_ids)} landmarks + {len(distractor_ids)} distractors = {len(candidate_pool)}")

    # Extend triples with (query, distractor, 0) for every query x distractor
    extended_triples = list(triples)
    for query_id in query_ids:
        for distractor_id in distractor_ids:
            extended_triples.append((query_id, distractor_id, 0))

    all_doc_ids = sorted(set(query_ids) | set(candidate_pool))
    texts, court_levels, dates = {}, {}, {}
    for doc_id in all_doc_ids:
        d = docs.get(doc_id) or load_cached_judgment(doc_id)
        text = d["text"] if isinstance(d, dict) else d.text
        texts[doc_id] = text
        court = (d.get("court") if isinstance(d, dict) else d.court) or ""
        court_levels[doc_id] = _extract_court_level_rules(court) if court else "Unknown"
        dates[doc_id] = d.get("date") if isinstance(d, dict) else d.date

    logger.info(f"Building embeddings for {len(all_doc_ids)} unique documents...")
    embeddings = await build_embeddings(all_doc_ids, texts)

    logger.info(f"Computing pairwise features for {len(extended_triples)} (query, candidate) pairs...")
    pair_features: Dict[Tuple[str, str], Dict[str, float]] = {}
    for query_id, candidate_id, _ in extended_triples:
        key = (query_id, candidate_id)
        if key in pair_features:
            continue
        pair_features[key] = extract_pair_features(
            query_embedding=embeddings[query_id],
            candidate_embedding=embeddings[candidate_id],
            query_text=texts[query_id],
            candidate_text=texts[candidate_id],
            candidate_date=dates[candidate_id],
            reference_date=REFERENCE_DATE,
            query_court_level=court_levels[query_id],
            candidate_court_level=court_levels[candidate_id],
        )

    court_variety = {court_levels[c] for c in candidate_pool}
    logger.info(f"Candidate pool court-level variety: {court_variety}")

    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    query_arr = np.array(query_ids)

    fold_results = {"baseline": {}, "hybrid": {}}
    for approach in fold_results:
        for k in K_VALUES:
            fold_results[approach][f"p@{k}"] = []
            fold_results[approach][f"ndcg@{k}"] = []

    weight_reports = []

    for fold_idx, (train_idx, test_idx) in enumerate(kf.split(query_arr)):
        train_queries = set(query_arr[train_idx])
        test_queries = set(query_arr[test_idx])

        train_rows, train_labels = [], []
        for q, c, label in extended_triples:
            if q in train_queries:
                train_rows.append(pair_features[(q, c)])
                train_labels.append(label)

        pipeline = fit_hybrid_weights(train_rows, train_labels)
        weight_reports.append(get_weight_report(pipeline))

        for query_id in test_queries:
            relevant_set = {l for q, l, label in triples if q == query_id and label == 1}
            if not relevant_set:
                continue

            baseline_ranked = sorted(
                candidate_pool, key=lambda c: pair_features[(query_id, c)]["cosine_similarity"], reverse=True
            )
            hybrid_ranked = sorted(
                candidate_pool, key=lambda c: hybrid_score(pipeline, pair_features[(query_id, c)]), reverse=True
            )

            for k in K_VALUES:
                fold_results["baseline"][f"p@{k}"].append(precision_at_k(baseline_ranked, relevant_set, k))
                fold_results["baseline"][f"ndcg@{k}"].append(ndcg_at_k(baseline_ranked, relevant_set, k))
                fold_results["hybrid"][f"p@{k}"].append(precision_at_k(hybrid_ranked, relevant_set, k))
                fold_results["hybrid"][f"ndcg@{k}"].append(ndcg_at_k(hybrid_ranked, relevant_set, k))

        logger.info(f"Fold {fold_idx+1}/{N_SPLITS}: {len(train_queries)} train, {len(test_queries)} test queries")

    summary = {
        "n_landmarks": len(landmark_ids),
        "n_distractors": len(distractor_ids),
        "candidate_pool_size": len(candidate_pool),
        "n_queries": len(query_ids),
    }
    for approach in ["baseline", "hybrid"]:
        summary[approach] = {
            metric: {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)}
            for metric, v in fold_results[approach].items() if v
        }
    avg_weights = {name: float(np.mean([wr[name] for wr in weight_reports])) for name in FEATURE_NAMES}
    summary["avg_standardized_coefficients"] = avg_weights

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = ["# Precedent hybrid re-ranker — MIXED POOL evaluation (landmarks + 100 random distractors)", ""]
    lines.append(f"- Candidate pool: {len(landmark_ids)} landmarks + {len(distractor_ids)} distractors = {len(candidate_pool)}")
    lines.append(f"- Queries: {len(query_ids)} | {N_SPLITS}-fold, query-level split")
    lines.append("")
    lines.append("| Metric | Cosine baseline | Hybrid re-ranker |")
    lines.append("|---|---|---|")
    for k in K_VALUES:
        b, h = summary["baseline"][f"p@{k}"], summary["hybrid"][f"p@{k}"]
        lines.append(f"| precision@{k} | {b['mean']:.3f} ± {b['std']:.3f} | {h['mean']:.3f} ± {h['std']:.3f} |")
    for k in K_VALUES:
        b, h = summary["baseline"][f"ndcg@{k}"], summary["hybrid"][f"ndcg@{k}"]
        lines.append(f"| nDCG@{k} | {b['mean']:.3f} ± {b['std']:.3f} | {h['mean']:.3f} ± {h['std']:.3f} |")
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
