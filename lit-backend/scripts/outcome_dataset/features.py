"""
Feature assembly for the judicial-outcome training dataset.

Computes the *exact same* five features the live simulator uses
(services/simulator.py) by importing and calling its scoring functions
directly rather than re-implementing the formula — this guarantees the
training features stay bit-for-bit consistent with what the app already
computes and displays.

Two deliberate choices worth flagging:

1. Label-leakage mitigation: `extract_rules_only` and the argument graph
   are built from the judgment text *truncated before the operative-order
   sentence* found by labeling.py (with a buffer), not the full judgment
   text. Feeding the full text (including the court's own stated
   conclusion and disposal) into "case profile" features would leak the
   label into the features. Truncating gets us closer to what a
   pre-decision case description would contain, though it's an
   approximation, not a guarantee — the reasoning leading up to the
   operative paragraph can still foreshadow the outcome.

2. Precedent alignment has no live historical corpus to query against in
   this offline batch job, so it's approximated as a leave-one-out
   similarity search *within the collected batch itself*: each case's
   embedding is queried against a FAISS index built from every other
   case in the batch (via the same chunking/embedding path as
   services/embedder.py), and the same `_score_precedent_alignment`
   formula is applied to those hits. This is a real but imperfect proxy
   for "similarity to actual precedent" — flagged again in the run
   summary.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from models.schemas import SearchResult, StructuredCaseProfile
from services.embedder import EmbedderService, _chunk_text
from services.extractor import _extract_court_level_rules, extract_rules_only
from services.graph_builder import build_argument_graph
from services.simulator import (
    _score_argument_completeness,
    _score_case_complexity,
    _score_court_level,
    _score_precedent_alignment,
    _score_statutory_strength,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Extra characters trimmed back from the labeling match, on top of the
# match position itself, to also drop the immediately preceding sentence
# that often states the court's conclusion just before the formal
# disposal line (e.g. "...we therefore hold X. The appeal is allowed.").
LEAKAGE_BUFFER_CHARS = 400


def build_feature_text(full_text: str, label_match_start: Optional[int]) -> str:
    """Return the slice of judgment text to use for feature extraction,
    truncated before the operative-order sentence to reduce (not
    eliminate) label leakage into the features."""
    if label_match_start is None:
        return full_text
    cutoff = max(0, label_match_start - LEAKAGE_BUFFER_CHARS)
    return full_text[:cutoff]


def build_case_profile(feature_text: str, scraped_court: Optional[str]) -> StructuredCaseProfile:
    """Rule-based extraction only (no HF model call) — deterministic,
    fast, and works fully offline, matching how the live app already
    behaves without a configured HUGGINGFACE_API_KEY."""
    profile = extract_rules_only(feature_text)

    # Prefer the court name Kanoon itself reported (parsed from a
    # dedicated page element) over the regex-over-text fallback baked
    # into extract_rules_only.
    if scraped_court:
        normalized = _extract_court_level_rules(scraped_court)
        if normalized != "Unknown":
            profile.court_level = normalized

    return profile


def build_graph_stats(profile: StructuredCaseProfile) -> Dict[str, Any]:
    graph = build_argument_graph(profile)
    return {"node_count": graph["node_count"], "weak_nodes": graph["weak_nodes"]}


class PrecedentIndex:
    """Leave-one-out FAISS index over the collected batch, used to
    approximate the precedent-alignment feature. Wraps a fresh
    EmbedderService instance — deliberately NOT the live app's singleton
    — so this never touches fixtures/precedent_index.json."""

    def __init__(self) -> None:
        self.embedder = EmbedderService()
        self._doc_vectors: Dict[str, np.ndarray] = {}

    async def add_case(
        self,
        doc_id: str,
        title: str,
        url: str,
        court: Optional[str],
        date: Optional[str],
        feature_text: str,
    ) -> int:
        chunks = _chunk_text(feature_text)
        if not chunks:
            logger.warning(f"No chunks for doc {doc_id} — skipping in precedent index")
            return 0

        embeddings = await self.embedder.embed_texts(chunks)
        vectors = np.array(embeddings, dtype=np.float32)
        # Mean pooled BEFORE add_vectors normalizes in place, so the
        # centroid reflects the raw chunk embeddings.
        self._doc_vectors[doc_id] = vectors.mean(axis=0)

        chunk_metadata = [
            {
                "doc_id": doc_id,
                "title": title,
                "url": url,
                "court": court,
                "date": date,
                "text": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i, chunk in enumerate(chunks)
        ]
        self.embedder.add_vectors(vectors, chunk_metadata)
        return len(chunks)

    def leave_one_out_precedents(self, doc_id: str, top_k: int = 5) -> List[SearchResult]:
        if doc_id not in self._doc_vectors or self.embedder.is_empty:
            return []

        query_vec = self._doc_vectors[doc_id].tolist()
        # Over-fetch since several of the nearest hits will be the case's
        # own chunks (excluded below) or duplicate hits on the same doc.
        hits = self.embedder.search(query_vec, top_k=top_k + 15)

        results: List[SearchResult] = []
        seen_docs = {doc_id}
        for hit in hits:
            meta = hit["metadata"]
            hit_doc_id = meta.get("doc_id", "")
            if not hit_doc_id or hit_doc_id in seen_docs:
                continue
            seen_docs.add(hit_doc_id)
            results.append(
                SearchResult(
                    title=meta.get("title", ""),
                    url=meta.get("url", ""),
                    doc_id=hit_doc_id,
                    court=meta.get("court"),
                    date=meta.get("date"),
                    snippet=(meta.get("text", "") or "")[:200],
                    similarity_score=hit["similarity_score"],
                )
            )
            if len(results) >= top_k:
                break
        return results

    def save(self, path) -> None:
        self.embedder.save_index(path)


def assemble_features(
    profile: StructuredCaseProfile,
    graph_stats: Dict[str, Any],
    precedents: List[SearchResult],
) -> Dict[str, Any]:
    """Call the live simulator's own scoring functions — the resulting
    raw_score values ARE the five features the app already uses."""
    prec = _score_precedent_alignment(precedents)
    stat = _score_statutory_strength(profile)
    arg = _score_argument_completeness(graph_stats)
    complexity = _score_case_complexity(profile)
    court = _score_court_level(profile)

    return {
        "feature_precedent_alignment": prec["raw_score"],
        "feature_statutory_strength": stat["raw_score"],
        "feature_argument_completeness": arg["raw_score"],
        "feature_case_complexity": complexity["raw_score"],
        "feature_court_level": court["raw_score"],
        "ipc_section_count": len(profile.ipc_sections),
        "acts_referenced_count": len(profile.acts_referenced),
        "legal_issue_count": len(profile.legal_issues),
        "key_fact_count": len(profile.key_facts),
        "graph_node_count": graph_stats.get("node_count", 0),
        "graph_weak_node_count": len(graph_stats.get("weak_nodes", [])),
        "case_type": profile.case_type,
        "court_level_normalized": profile.court_level,
        "precedent_match_count": len(precedents),
    }
