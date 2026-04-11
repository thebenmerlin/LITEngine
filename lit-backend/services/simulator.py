"""
Judicial outcome simulation — heuristic scoring engine.

Computes an explainable win_probability for the petitioner based on:
  1. Precedent Alignment (35%)
  2. Statutory Strength (25%)
  3. Argument Completeness (20%)
  4. Case Complexity Penalty (10%)
  5. Court Level Factor (10%)

Every component returns a raw score, weight, weighted score, and
human-readable explanation. The result is fully transparent — no black box.
"""

from typing import Any, Dict, List, Optional

from models.schemas import (
    RiskAssessment,
    ScoreComponent,
    SearchResult,
    SimulationResult,
    StructuredCaseProfile,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Component weights
# ---------------------------------------------------------------------------

WEIGHTS = {
    "precedent_alignment": 0.35,
    "statutory_strength": 0.25,
    "argument_completeness": 0.20,
    "case_complexity": 0.10,
    "court_level": 0.10,
}

# Final probability clamp — never exactly 0 or 1
PROB_MIN = 0.05
PROB_MAX = 0.95

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = PROB_MIN, hi: float = PROB_MAX) -> float:
    return max(lo, min(hi, value))


def _score_precedent_alignment(
    precedents: List[SearchResult],
) -> Dict[str, Any]:
    """
    Precedent Alignment Score (weight: 35%)

    Average similarity of top precedents.
    - If best precedent > 0.8: +0.1 boost.
    - If no precedents: neutral 0.4.
    """
    weight = WEIGHTS["precedent_alignment"]

    if not precedents:
        raw = 0.4
        explanation = "No similar precedents found — neutral baseline applied."
    else:
        sims = [p.similarity_score for p in precedents if p.similarity_score is not None]
        if not sims:
            raw = 0.4
            explanation = "Precedent similarity scores unavailable — neutral baseline."
        else:
            raw = sum(sims) / len(sims)
            best = max(sims)
            if best > 0.8:
                raw = min(raw + 0.1, 1.0)
                explanation = (
                    f"Average similarity {raw:.2f}; strongest precedent at {best:.2f} "
                    f"(boosted +0.10 for high alignment)."
                )
            else:
                explanation = (
                    f"Average similarity {raw:.2f} across {len(sims)} precedent(s)."
                )

    return {
        "component": "Precedent Alignment",
        "weight": weight,
        "raw_score": round(raw, 4),
        "weighted_score": round(raw * weight, 4),
        "explanation": explanation,
    }


def _score_statutory_strength(profile: StructuredCaseProfile) -> Dict[str, Any]:
    """
    Statutory Strength Score (weight: 25%)

    Based on count of IPC/statute references:
      0 refs: 0.3,  1-2 refs: 0.5,  3-4 refs: 0.7,  5+: 0.85
    Criminal cases with IPC sections get +0.05.
    """
    weight = WEIGHTS["statutory_strength"]
    ref_count = len(profile.ipc_sections) + len(profile.acts_referenced)

    if ref_count == 0:
        raw = 0.3
        base_text = "No statutory references extracted."
    elif ref_count <= 2:
        raw = 0.5
        base_text = f"{ref_count} statute(s) referenced — moderate foundation."
    elif ref_count <= 4:
        raw = 0.7
        base_text = f"{ref_count} statutes referenced — solid statutory basis."
    else:
        raw = 0.85
        base_text = f"{ref_count} statutes referenced — strong statutory coverage."

    # Criminal + IPC boost
    if profile.case_type == "criminal" and profile.ipc_sections:
        raw = min(raw + 0.05, 1.0)
        base_text += " Criminal case with IPC sections (+0.05)."

    return {
        "component": "Statutory Strength",
        "weight": weight,
        "raw_score": round(raw, 4),
        "weighted_score": round(raw * weight, 4),
        "explanation": base_text,
    }


def _score_argument_completeness(
    graph_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Argument Completeness Score (weight: 20%)

    Ratio of strong (non-weak) nodes to total nodes in the argument graph.
    If no graph stats provided, default to 0.5 (neutral).
    """
    weight = WEIGHTS["argument_completeness"]

    if not graph_stats or graph_stats.get("node_count", 0) == 0:
        raw = 0.5
        explanation = "No argument graph provided — neutral baseline."
    else:
        total = graph_stats["node_count"]
        weak_count = len(graph_stats.get("weak_nodes", []))
        strong = total - weak_count
        raw = strong / total if total > 0 else 0.5

        if weak_count == 0:
            explanation = f"All {total} nodes are strong — no unsupported arguments."
        else:
            explanation = (
                f"{strong}/{total} nodes are supported; {weak_count} weak node(s) "
                f"lack evidentiary backing."
            )

    return {
        "component": "Argument Completeness",
        "weight": weight,
        "raw_score": round(raw, 4),
        "weighted_score": round(raw * weight, 4),
        "explanation": explanation,
    }


def _score_case_complexity(profile: StructuredCaseProfile) -> Dict[str, Any]:
    """
    Case Complexity Penalty (weight: 10%)

    More legal issues = higher complexity = slight penalty:
      1-2 issues: 0.8,  3-4 issues: 0.65,  5+: 0.5
    """
    weight = WEIGHTS["case_complexity"]
    issue_count = len(profile.legal_issues)

    if issue_count <= 2:
        raw = 0.8
        explanation = f"Only {issue_count} legal issue(s) — focused, manageable case."
    elif issue_count <= 4:
        raw = 0.65
        explanation = f"{issue_count} legal issues — moderate complexity."
    else:
        raw = 0.5
        explanation = f"{issue_count} legal issues — high complexity, multiple angles."

    return {
        "component": "Case Complexity",
        "weight": weight,
        "raw_score": round(raw, 4),
        "weighted_score": round(raw * weight, 4),
        "explanation": explanation,
    }


def _score_court_level(profile: StructuredCaseProfile) -> Dict[str, Any]:
    """
    Court Level Factor (weight: 10%)

    Supreme Court: 0.5 (hardest to win), High Court: 0.6, District Court: 0.7
    """
    weight = WEIGHTS["court_level"]
    court = (profile.court_level or "").lower()

    if "supreme" in court:
        raw = 0.5
        explanation = "Supreme Court — high bar, rigorous scrutiny."
    elif "high" in court:
        raw = 0.6
        explanation = "High Court — moderate bar, established appellate review."
    elif "district" in court or "sessions" in court:
        raw = 0.7
        explanation = "District/Sessions Court — lower bar, fact-finding stage."
    else:
        raw = 0.55
        explanation = f"Unknown court level ('{profile.court_level}') — conservative estimate."

    return {
        "component": "Court Level",
        "weight": weight,
        "raw_score": round(raw, 4),
        "weighted_score": round(raw * weight, 4),
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Strengths, weaknesses, recommendation
# ---------------------------------------------------------------------------

def _extract_strengths(
    breakdown: List[ScoreComponent],
    profile: StructuredCaseProfile,
    precedents: List[SearchResult],
) -> List[str]:
    """Return top 3 strengths (highest weighted scores with positive framing)."""
    candidates: List[tuple[float, str]] = []

    for sc in breakdown:
        if sc.weighted_score >= 0.1:
            candidates.append((sc.weighted_score, sc.explanation))

    # Additional domain-specific strengths
    if precedents:
        best_sim = max(p.similarity_score or 0 for p in precedents)
        if best_sim > 0.75:
            candidates.append((0.15, "Strong precedent alignment with past judgments."))
    if profile.relief_sought and len(profile.relief_sought) > 10:
        candidates.append((0.12, "Specific relief sought — clear prayer for remedy."))
    if len(profile.key_facts) >= 3:
        candidates.append((0.12, f"{len(profile.key_facts)} key facts extracted — solid evidentiary base."))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in candidates[:3]]


def _extract_weaknesses(
    breakdown: List[ScoreComponent],
    profile: StructuredCaseProfile,
    graph_stats: Optional[Dict[str, Any]],
) -> List[str]:
    """Return top 3 weaknesses (lowest weighted scores with diagnostic framing)."""
    candidates: List[tuple[float, str]] = []

    for sc in breakdown:
        if sc.weighted_score < 0.15:
            candidates.append((sc.weighted_score, sc.explanation))

    # Additional domain-specific weaknesses
    if not profile.ipc_sections and not profile.acts_referenced:
        candidates.append((0.05, "No statutory references — weak legal foundation."))
    if not profile.parties.petitioner and not profile.parties.respondent:
        candidates.append((0.05, "Parties not identified — case framing incomplete."))
    if graph_stats and len(graph_stats.get("weak_nodes", [])) > 0:
        weak_count = len(graph_stats["weak_nodes"])
        candidates.append((0.08, f"{weak_count} unsupported argument node(s) in the graph."))
    if not profile.relief_sought:
        candidates.append((0.06, "No relief sought — unclear remedy being pursued."))

    candidates.sort(key=lambda x: x[0])
    return [text for _, text in candidates[:3]]


def _generate_recommendation(
    win_prob: float,
    weaknesses: List[str],
    strengths: List[str],
) -> str:
    """Plain-English recommendation in 1-2 sentences."""
    if win_prob >= 0.7:
        base = "The case appears favorable for the petitioner."
    elif win_prob >= 0.5:
        base = "The outcome is uncertain — success depends on how the court weighs key issues."
    else:
        base = "The case faces significant headwinds — the petitioner's position is weak."

    if weaknesses:
        # Pick the most actionable weakness
        fix = weaknesses[0]
        return f"{base} Consider addressing: {fix.lower()}"
    return base


# ---------------------------------------------------------------------------
# Main scoring engine
# ---------------------------------------------------------------------------

def predict_outcome(
    profile: StructuredCaseProfile,
    precedents: Optional[List[SearchResult]] = None,
    graph_stats: Optional[Dict[str, Any]] = None,
) -> SimulationResult:
    """
    Compute an explainable judicial outcome prediction.

    Args:
        profile: Structured case profile from fact extraction
        precedents: Optional precedent search results (top matches)
        graph_stats: Optional { node_count, weak_nodes } from argument graph

    Returns:
        SimulationResult with full scoring breakdown
    """
    prec_list = precedents or []

    # Compute all 5 components
    breakdown: List[ScoreComponent] = []

    comp = _score_precedent_alignment(prec_list)
    breakdown.append(ScoreComponent(**comp))

    comp = _score_statutory_strength(profile)
    breakdown.append(ScoreComponent(**comp))

    comp = _score_argument_completeness(graph_stats)
    breakdown.append(ScoreComponent(**comp))

    comp = _score_case_complexity(profile)
    breakdown.append(ScoreComponent(**comp))

    comp = _score_court_level(profile)
    breakdown.append(ScoreComponent(**comp))

    # Weighted sum
    win_probability = sum(c.weighted_score for c in breakdown)
    win_probability = _clamp(round(win_probability, 4))

    # Risk assessment
    if win_probability >= 0.7:
        risk = RiskAssessment(level="Favorable", color="green")
    elif win_probability >= 0.5:
        risk = RiskAssessment(level="Uncertain", color="amber")
    else:
        risk = RiskAssessment(level="Unfavorable", color="red")

    # Strengths & weaknesses
    strengths = _extract_strengths(breakdown, profile, prec_list)
    weaknesses = _extract_weaknesses(breakdown, profile, graph_stats)
    recommendation = _generate_recommendation(win_probability, weaknesses, strengths)

    logger.info(
        f"Outcome prediction: win_prob={win_probability:.2f}, "
        f"risk={risk.level}, "
        f"strengths={len(strengths)}, weaknesses={len(weaknesses)}"
    )

    return SimulationResult(
        win_probability=win_probability,
        risk_assessment=risk,
        score_breakdown=breakdown,
        key_strengths=strengths,
        key_weaknesses=weaknesses,
        recommendation=recommendation,
    )
