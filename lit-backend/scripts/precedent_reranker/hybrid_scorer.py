"""
Hybrid precedent re-ranking: combines (a) embedding cosine similarity,
(b) statute/section overlap, (c) court hierarchy + same-court bonus, and
(d) recency into a single relevance score, with weights FIT on labeled
relevance pairs (not hand-picked) via logistic regression — same
approach and same rigor as the outcome-model work, not another
hand-picked formula.

Reuses services.extractor's rule-based section/act extraction and
services.embedder's EmbedderService (a fresh instance, not the live
singleton — mirrors the pattern already established in
scripts/outcome_dataset/features.py's PrecedentIndex) rather than
rebuilding either.
"""

import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from services.extractor import _extract_acts_rules, _extract_court_level_rules, _extract_sections_rules

# ---------------------------------------------------------------------------
# Individual signals
# ---------------------------------------------------------------------------

COURT_LEVEL_SCORE = {
    "Supreme Court": 1.0,
    "High Court": 0.7,
    "Tribunal": 0.55,
    "Commission": 0.55,
    "Family Court": 0.45,
    "District Court": 0.4,
    "Unknown": 0.3,
}
SAME_COURT_BONUS = 0.15

RECENCY_HALF_LIFE_YEARS = 15.0


def statute_set(text: str) -> set:
    """IPC/CrPC/CPC sections + referenced Acts, as a single comparable set."""
    return set(_extract_sections_rules(text)) | set(_extract_acts_rules(text))


def statute_overlap(query_statutes: set, candidate_statutes: set) -> float:
    if not query_statutes and not candidate_statutes:
        return 0.0
    union = query_statutes | candidate_statutes
    if not union:
        return 0.0
    return len(query_statutes & candidate_statutes) / len(union)


def court_score(query_court_level: str, candidate_court_level: str) -> float:
    base = COURT_LEVEL_SCORE.get(candidate_court_level, COURT_LEVEL_SCORE["Unknown"])
    bonus = SAME_COURT_BONUS if (
        query_court_level != "Unknown"
        and query_court_level == candidate_court_level
    ) else 0.0
    return min(1.0, base + bonus)


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    m = _DATE_RE.match(date_str)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def recency_score(candidate_date_str: Optional[str], reference_date: date, half_life_years: float = RECENCY_HALF_LIFE_YEARS) -> float:
    """Exponential decay by age — precedents don't go stale as fast as
    news, but very old ones score lower. Unknown date -> neutral 0.5."""
    d = _parse_date(candidate_date_str)
    if d is None:
        return 0.5
    age_years = max(0.0, (reference_date - d).days / 365.25)
    return 0.5 ** (age_years / half_life_years)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    na, nb = np.linalg.norm(vec_a), np.linalg.norm(vec_b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (na * nb))


# ---------------------------------------------------------------------------
# Pair feature extraction
# ---------------------------------------------------------------------------

FEATURE_NAMES = ["cosine_similarity", "statute_overlap", "court_score", "recency_score"]


def extract_pair_features(
    query_embedding: np.ndarray,
    candidate_embedding: np.ndarray,
    query_text: str,
    candidate_text: str,
    candidate_date: Optional[str],
    reference_date: date,
    query_court_level: Optional[str] = None,
    candidate_court_level: Optional[str] = None,
) -> Dict[str, float]:
    q_statutes = statute_set(query_text)
    c_statutes = statute_set(candidate_text)

    q_court = query_court_level or _extract_court_level_rules(query_text)
    c_court = candidate_court_level or _extract_court_level_rules(candidate_text)

    return {
        "cosine_similarity": cosine_similarity(query_embedding, candidate_embedding),
        "statute_overlap": statute_overlap(q_statutes, c_statutes),
        "court_score": court_score(q_court, c_court),
        "recency_score": recency_score(candidate_date, reference_date),
    }


# ---------------------------------------------------------------------------
# Weight fitting (logistic regression — same approach as the outcome model)
# ---------------------------------------------------------------------------

def fit_hybrid_weights(feature_rows: List[Dict[str, float]], labels: List[int]):
    """Fits a logistic regression mapping the 4 signals -> P(relevant).
    Returns the fitted sklearn Pipeline; the re-ranking score for a pair
    is simply predict_proba(...)[1] — consistent with how the outcome
    model's probability doubles as its score."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    X = np.array([[row[f] for f in FEATURE_NAMES] for row in feature_rows])
    y = np.array(labels)

    pipeline = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(l1_ratio=0.0, C=1.0, class_weight="balanced", max_iter=2000, random_state=42)),
    ])
    pipeline.fit(X, y)
    return pipeline


def hybrid_score(pipeline, features: Dict[str, float]) -> float:
    X = np.array([[features[f] for f in FEATURE_NAMES]])
    return float(pipeline.predict_proba(X)[0, 1])


def get_weight_report(pipeline) -> Dict[str, float]:
    """Human-readable standardized coefficients (bigger |value| = more
    influential, since inputs are standardized before the logistic
    regression sees them)."""
    clf = pipeline.named_steps["clf"]
    return {name: float(coef) for name, coef in zip(FEATURE_NAMES, clf.coef_[0])}
