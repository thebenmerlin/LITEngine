"""
Near-duplicate detection across the collected judgment batch.

Indian Kanoon sometimes indexes the SAME underlying judgment multiple
times under different doc_ids — once per named appellant in a
multi-accused case (e.g. a batch criminal appeal covering 10 co-accused
gets one Kanoon entry per accused, each reproducing the full judgment
text). These have different case_ids, different titles, but near-
identical body text.

Validated against two known clusters while building this (see
scripts/outcome_dataset/build_dataset_v2.py Step 0 audit):
  - True duplicates score ~0.999-1.0 on 8-word-shingle Jaccard similarity.
  - Companion-but-distinct judgments (same court/bench/date, shared
    background narrative from a related case, but different appeal
    numbers and different actual disposals) score ~0.20-0.32 — well
    above the random-pair baseline (~0.001) but nowhere near a true
    duplicate.
  - Random unrelated case pairs score ~0.001 mean, ~0.02 max.

A threshold of 0.85 sits comfortably in the gap between those two
clusters, so it's used as the default — low enough to never miss a true
duplicate (0.999+), high enough to never merge two merely-related
companion judgments (<=0.32).
"""

import re
from typing import Dict, List, Set, Tuple

SHINGLE_SIZE = 8
DEFAULT_THRESHOLD = 0.85


def _shingles(text: str, k: int = SHINGLE_SIZE) -> Set[Tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    if len(words) < k:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + k]) for i in range(len(words) - k + 1)}


def _jaccard(a: Set, b: Set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


class UnionFind:
    def __init__(self, items: List[str]):
        self._parent = {x: x for x in items}

    def find(self, x: str) -> str:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for x in self._parent:
            out.setdefault(self.find(x), []).append(x)
        return out


def find_duplicate_clusters(
    doc_texts: Dict[str, str],
    doc_dates: Dict[str, str],
    threshold: float = DEFAULT_THRESHOLD,
) -> List[List[str]]:
    """
    Find clusters of near-duplicate doc_ids.

    Comparisons are bucketed by decision date first — true duplicates
    (the same judgment re-indexed under different appellant names) always
    share the exact same decision date, so this avoids an O(n^2) sweep
    across the full batch while losing no true positives.

    Returns:
        List of clusters, each a list of >=2 doc_ids. Singletons (no
        duplicate found) are not included.
    """
    by_date: Dict[str, List[str]] = {}
    for doc_id, date in doc_dates.items():
        if not date:
            continue
        by_date.setdefault(date, []).append(doc_id)

    shingle_cache: Dict[str, Set] = {}

    def get_shingles(doc_id: str) -> Set:
        if doc_id not in shingle_cache:
            shingle_cache[doc_id] = _shingles(doc_texts[doc_id])
        return shingle_cache[doc_id]

    uf = UnionFind(list(doc_texts.keys()))

    for date, ids in by_date.items():
        if len(ids) < 2:
            continue
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                sim = _jaccard(get_shingles(a), get_shingles(b))
                if sim >= threshold:
                    uf.union(a, b)

    clusters = [members for members in uf.groups().values() if len(members) > 1]
    return clusters


def pick_cluster_representative(
    cluster: List[str],
    labels: Dict[str, str],
    confidences: Dict[str, float],
) -> Tuple[str, str, float]:
    """
    Collapse a duplicate cluster to a single (representative_doc_id,
    label, confidence).

    If all non-"unclear" labels in the cluster agree, use that label at
    the highest confidence seen for it. If they disagree, the cluster's
    true outcome is ambiguous from our extraction — report "unclear"
    rather than arbitrarily picking a side, and use the representative
    with the highest raw confidence (for its snippet/evidence) so the
    row is still traceable to real text.
    """
    concrete = [c for c in cluster if labels.get(c) != "unclear"]
    distinct_labels = {labels[c] for c in concrete}

    if len(distinct_labels) == 1:
        agreed_label = next(iter(distinct_labels))
        best = max(concrete, key=lambda c: confidences.get(c, 0.0))
        return best, agreed_label, confidences.get(best, 0.0)

    if len(distinct_labels) > 1:
        # Genuine disagreement within a duplicate cluster — shouldn't
        # normally happen (same text -> same extracted label), but if it
        # does (e.g. one copy's text got truncated differently), don't
        # guess.
        best = max(cluster, key=lambda c: confidences.get(c, 0.0))
        return best, "unclear", 0.3

    # All members are "unclear"
    best = max(cluster, key=lambda c: confidences.get(c, 0.0))
    return best, "unclear", confidences.get(best, 0.0)
