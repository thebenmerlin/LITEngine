"""
Outcome model service — serves the trained logistic regression
classifier (outcome_classifier_binary.joblib, see
scripts/outcome_dataset/train_model_binary.py) for the live
judicial-outcome simulation endpoint.

Consumes the SAME 5 raw component scores the existing heuristic
(services/simulator.py) already computes — does not recompute feature
extraction. appellant_type is a direct request input (never inferred
from case text; that inference heuristic only existed for labeling
historical Kanoon judgments during dataset construction).

Loads the model once at import time. If loading fails for any reason,
`is_model_loaded()` reports False and `predict_ml_outcome()` returns a
clearly-marked fallback stub instead of raising — callers (the /predict
router) are expected to fall back to the heuristic when this happens,
never to error the endpoint.
"""

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.schemas import MLFeatureContribution, MLModelResult, ScoreComponent, SimulationResult
from services.simulator import PROB_MAX, PROB_MIN
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "outcome_dataset" / "model" / "outcome_classifier_binary.joblib"
)
MODEL_PATH = Path(get_settings().OUTCOME_MODEL_PATH).expanduser() if get_settings().OUTCOME_MODEL_PATH else DEFAULT_MODEL_PATH

# Must exactly match scripts/outcome_dataset/train_model.py's
# FEATURE_COLUMNS / APPELLANT_CATEGORIES / feature_names_out() ordering —
# the ColumnTransformer inside the loaded pipeline was fit with this
# exact column order. Hardcoded here (not imported from scripts/) since
# services/ is live-path code and shouldn't depend on offline tooling.
FEATURE_ORDER = [
    "precedent_alignment",
    "statutory_strength",
    "argument_completeness",
    "case_complexity",
    "court_level",
]
APPELLANT_TYPE_CATEGORIES = ["accused_appeal", "state_appeal", "unclear"]
EXPECTED_CLASSES = ["dismissed", "succeeds"]

FEATURE_DISPLAY_NAMES: Dict[str, str] = {
    "precedent_alignment": "Precedent Alignment",
    "statutory_strength": "Statutory Strength",
    "argument_completeness": "Argument Completeness",
    "case_complexity": "Case Complexity",
    "court_level": "Court Level",
    "appellant_type=accused_appeal": "Appellant Type: Accused's Own Appeal",
    "appellant_type=state_appeal": "Appellant Type: State/Complainant Appeal",
    "appellant_type=unclear": "Appellant Type: Unspecified",
}

# services/simulator.py's ScoreComponent.component strings -> our feature keys
COMPONENT_NAME_TO_FEATURE_KEY: Dict[str, str] = {
    "Precedent Alignment": "precedent_alignment",
    "Statutory Strength": "statutory_strength",
    "Argument Completeness": "argument_completeness",
    "Case Complexity": "case_complexity",
    "Court Level": "court_level",
}

TOP_N_EXPLANATION = 3


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_pipeline = None
_load_error: Optional[str] = None


def _validate_filing_promotion(pipeline) -> None:
    if not getattr(pipeline, "requires_filing_date", False):
        return
    report_path = MODEL_PATH.parent / "evaluation_report.json"
    metadata_path = MODEL_PATH.parent / "feature_metadata.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not report.get("promotion_gate_passed") or report.get("candidate_version") != pipeline.version:
        raise ValueError("filing-based model has no passing holdout report")
    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != report.get("candidate_sha256"):
        raise ValueError("model artifact differs from evaluated artifact")
    index_path = get_settings().PRECEDENT_INDEX_PATH
    if not index_path or not Path(index_path).expanduser().is_file():
        raise ValueError("evaluated precedent index is not configured")
    index_hash = hashlib.sha256(Path(index_path).expanduser().read_bytes()).hexdigest()
    if index_hash != metadata.get("precedent_index_sha256"):
        raise ValueError("serving precedent index differs from evaluated index")


def _load_model() -> None:
    global _pipeline, _load_error
    try:
        import joblib  # local import: only needed if a model file exists
    except ImportError as exc:
        _load_error = f"joblib not installed: {exc}"
        logger.warning(f"Outcome model unavailable — {_load_error}. Falling back to heuristic only.")
        return

    if not MODEL_PATH.exists():
        _load_error = f"model file not found at {MODEL_PATH}"
        logger.warning(f"Outcome model unavailable — {_load_error}. Falling back to heuristic only.")
        return

    try:
        pipeline = joblib.load(MODEL_PATH)
        clf = pipeline.named_steps["clf"]
        classes = list(clf.classes_)
        if classes != EXPECTED_CLASSES:
            raise ValueError(f"unexpected classes_ {classes}, expected {EXPECTED_CLASSES}")
        n_features_expected = len(FEATURE_ORDER) + len(APPELLANT_TYPE_CATEGORIES)
        if clf.coef_.shape[-1] != n_features_expected:
            raise ValueError(f"unexpected coef_ shape {clf.coef_.shape}, expected last dim {n_features_expected}")
        if hasattr(pipeline, "feature_order") and tuple(pipeline.feature_order) != tuple(FEATURE_ORDER + ["appellant_type"]):
            raise ValueError("model feature order does not match the serving contract")
        _validate_filing_promotion(pipeline)
    except Exception as exc:
        _load_error = f"failed to load/validate {MODEL_PATH}: {exc}"
        logger.warning(f"Outcome model unavailable — {_load_error}. Falling back to heuristic only.")
        return

    _pipeline = pipeline
    logger.info(f"Loaded outcome model from {MODEL_PATH}")


_load_model()


def is_model_loaded() -> bool:
    return _pipeline is not None


# ---------------------------------------------------------------------------
# Explanation helpers
# ---------------------------------------------------------------------------

def _qualitative(value: float) -> str:
    if value >= 0.75:
        return "High"
    if value >= 0.45:
        return "Moderate"
    return "Low"


def _direction_phrase(contribution: float) -> str:
    return "succeeds" if contribution >= 0 else "dismissed"


def _sentence_for(feature_key: str, value: float, contribution: float) -> str:
    display = FEATURE_DISPLAY_NAMES.get(feature_key, feature_key)
    direction = _direction_phrase(contribution)

    if feature_key.startswith("appellant_type="):
        if value < 0.5:
            return f"{display} (not applicable here) had no effect."
        phrasing = {
            "appellant_type=accused_appeal": "This is the accused's own appeal against conviction",
            "appellant_type=state_appeal": "This is a State/complainant appeal against acquittal",
            "appellant_type=unclear": "Appellant type wasn't specified",
        }[feature_key]
        return f"{phrasing}, which pushed toward '{direction}'."

    return f"{_qualitative(value)} {display.lower()} ({value:.2f}) pushed toward '{direction}'."


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def _fallback_result() -> MLModelResult:
    return MLModelResult(
        predicted_class="unknown",
        probability=0.0,
        probabilities={"dismissed": 0.0, "succeeds": 0.0},
        feature_contributions=[],
        explanation_sentences=[
            "The trained model is currently unavailable — showing the heuristic result only."
        ],
        key_strengths=[],
        key_weaknesses=[],
        recommendation="Trained model unavailable this session — see the heuristic result.",
        model_loaded=False,
        model_version=None,
    )


def predict_ml_outcome(
    raw_scores: Dict[str, float], appellant_type: str,
    extraction_method: Optional[str] = None, filing_date_provided: bool = False,
) -> MLModelResult:
    """
    Args:
        raw_scores: the 5 component raw_score values (0-1) already
            computed by services.simulator.predict_outcome — keys must
            match FEATURE_ORDER.
        appellant_type: "accused_appeal" | "state_appeal" | "unclear",
            a direct user input, never inferred from text here.
    """
    if _pipeline is None:
        return _fallback_result()
    if getattr(_pipeline, "requires_filing_date", False) and not filing_date_provided:
        logger.warning("Filing-based outcome model requires an appeal filing date")
        return _fallback_result()

    expected_method = getattr(_pipeline, "extraction_method", None)
    if expected_method and extraction_method != expected_method:
        logger.warning(f"Outcome model expects {expected_method} extraction; received {extraction_method}")
        return _fallback_result()

    missing = [f for f in FEATURE_ORDER if f not in raw_scores]
    if missing:
        logger.warning(f"predict_ml_outcome: missing raw scores {missing} — falling back")
        return _fallback_result()

    if appellant_type not in APPELLANT_TYPE_CATEGORIES:
        appellant_type = "unclear"

    import numpy as np

    X = np.array([[raw_scores[f] for f in FEATURE_ORDER] + [appellant_type]], dtype=object)

    try:
        proba = _pipeline.predict_proba(X)[0]
        predicted = _pipeline.predict(X)[0]
        classes = list(_pipeline.named_steps["clf"].classes_)
        probabilities = {cls: float(p) for cls, p in zip(classes, proba)}

        transformed = _pipeline.named_steps["preprocess"].transform(X)[0]
        clf = _pipeline.named_steps["clf"]
        coef = clf.coef_[0]  # binary: single row, corresponds to classes_[1] ("succeeds")
        feature_keys = FEATURE_ORDER + [f"appellant_type={c}" for c in APPELLANT_TYPE_CATEGORIES]

        contributions: List[MLFeatureContribution] = []
        for key, coef_i, value_i in zip(feature_keys, coef, transformed):
            contribution = float(coef_i) * float(value_i)
            contributions.append(
                MLFeatureContribution(
                    feature=key,
                    display_name=FEATURE_DISPLAY_NAMES.get(key, key),
                    value=float(value_i),
                    contribution=contribution,
                    explanation=_sentence_for(key, float(value_i), contribution),
                )
            )
    except Exception as exc:
        logger.error(f"predict_ml_outcome: inference failed, falling back: {exc}")
        return _fallback_result()

    contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
    # Zero-value one-hot features (the inactive appellant_type categories)
    # never explain anything for this prediction — drop them from the
    # ranked/explanation views, but they're still in feature_contributions
    # for completeness (harmless, contribution is exactly 0).
    active = [c for c in contributions if abs(c.contribution) > 1e-9]

    explanation_sentences = [c.explanation for c in active[:TOP_N_EXPLANATION]]
    key_strengths = [c.explanation for c in active if c.contribution > 0][:3]
    key_weaknesses = [c.explanation for c in active if c.contribution < 0][:3]

    p_succeeds = probabilities.get("succeeds", 0.0)
    if p_succeeds >= 0.7:
        base = "The case appears favorable — the model estimates a good chance of success."
    elif p_succeeds >= 0.5:
        base = "The outcome is uncertain per the trained model — success depends on the weaker factors below."
    else:
        base = "The trained model estimates significant headwinds for this appeal."
    recommendation = base
    if key_weaknesses:
        recommendation += f" Consider addressing: {key_weaknesses[0].lower()}"

    return MLModelResult(
        predicted_class=str(predicted),
        probability=float(probabilities[str(predicted)]),
        probabilities=probabilities,
        feature_contributions=contributions,
        explanation_sentences=explanation_sentences,
        key_strengths=key_strengths,
        key_weaknesses=key_weaknesses,
        recommendation=recommendation,
        model_loaded=True,
        model_version=getattr(_pipeline, "version", MODEL_PATH.name),
    )


# ---------------------------------------------------------------------------
# Reshape into the legacy SimulationResult shape (for when this model is
# "primary" and needs to populate the top-level response.result field)
# ---------------------------------------------------------------------------

def _risk_from_probability(p: float) -> Dict[str, str]:
    if p >= 0.7:
        return {"level": "Favorable", "color": "green"}
    if p >= 0.5:
        return {"level": "Uncertain", "color": "amber"}
    return {"level": "Unfavorable", "color": "red"}


def ml_result_to_simulation_result(ml_result: MLModelResult) -> SimulationResult:
    """
    Projects the new model's output into the existing SimulationResult
    shape so it can populate the top-level (legacy) response field
    without a frontend schema change.

    win_probability / risk_assessment / key_strengths / key_weaknesses /
    recommendation map naturally (win_probability = P(succeeds) — this
    case's own appeal, regardless of who filed it).

    score_breakdown does NOT map cleanly: ScoreComponent.weight is a
    fixed a-priori importance and weighted_score = weight x raw_score,
    both always in [0,1], summing across components to (roughly)
    win_probability. The trained model's per-feature contributions are
    signed log-odds terms specific to THIS prediction, not fixed global
    weights, and can be negative. To stay within ScoreComponent's [0,1]
    constraint without silently misrepresenting the data:
      - raw_score = the feature's own raw value (unchanged meaning)
      - weight = weighted_score = |contribution| / sum(|contributions|)
        — this case's share of total model influence, not a fixed
        weight. Always >= 0, sums to ~1 across components.
      - direction (which way it pushed) is carried in `explanation`
        text, not in the bar value, since the bar can't go negative.
    This is a deliberate, documented reshape — see training write-up.
    """
    probability = ml_result.probabilities.get("succeeds", ml_result.probability)
    probability = max(PROB_MIN, min(PROB_MAX, probability))

    total_abs = sum(abs(c.contribution) for c in ml_result.feature_contributions) or 1.0
    breakdown = [
        ScoreComponent(
            component=c.display_name,
            weight=round(abs(c.contribution) / total_abs, 4),
            raw_score=round(max(0.0, min(1.0, c.value)), 4),
            weighted_score=round(abs(c.contribution) / total_abs, 4),
            explanation=c.explanation,
        )
        for c in ml_result.feature_contributions
        if abs(c.contribution) > 1e-9
    ]

    risk = _risk_from_probability(probability)

    return SimulationResult(
        win_probability=round(probability, 4),
        risk_assessment=risk,
        score_breakdown=breakdown,
        key_strengths=ml_result.key_strengths,
        key_weaknesses=ml_result.key_weaknesses,
        recommendation=ml_result.recommendation,
    )
