from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from config import get_settings
from models.schemas import (
    OldVsNewComparison,
    SimulationRequest,
    SimulationResponse,
    SimulationResult,
    StatusResponse,
)
from services.simulator import predict_outcome
from services.outcome_model import (
    COMPONENT_NAME_TO_FEATURE_KEY,
    ml_result_to_simulation_result,
    predict_ml_outcome,
)
from services.precedent_filter import decision_before
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation"])

_VALID_PRIMARY = {"new_model", "old_heuristic"}


@router.get("/", response_model=StatusResponse)
async def simulation_status():
    """Check simulation module status."""
    return {"status": "ok", "module": "simulation"}


@router.post("/predict", response_model=SimulationResponse)
async def predict(request: SimulationRequest):
    """
    Predict a judicial outcome for the petitioner based on a
    StructuredCaseProfile, optional precedents, and optional graph stats.

    Returns an explainable score breakdown — every component is transparent.
    """
    logger.info(
        f"Predicting outcome: {len(request.case_profile.legal_issues)} issues, "
        f"{len(request.case_profile.ipc_sections)} sections, "
        f"{len(request.precedents)} precedents, "
        f"graph_stats={'yes' if request.graph_stats else 'no'}, "
        f"appellant_type={request.appellant_type}"
    )

    if request.filing_date and any(
        not decision_before(item.date, request.filing_date) for item in request.precedents
    ):
        raise HTTPException(status_code=422, detail="Precedents must have a known decision date before the appeal filing date")

    try:
        heuristic_result: SimulationResult = predict_outcome(
            profile=request.case_profile,
            precedents=request.precedents,
            graph_stats=request.graph_stats,
        )
    except Exception as exc:
        logger.error(f"Simulation prediction failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # Reuse the raw component scores the heuristic already computed —
    # the trained model consumes the same 5 features, not a re-extraction.
    raw_scores = {
        COMPONENT_NAME_TO_FEATURE_KEY[sc.component]: sc.raw_score
        for sc in heuristic_result.score_breakdown
        if sc.component in COMPONENT_NAME_TO_FEATURE_KEY
    }
    extraction_method = request.case_profile.metadata.extraction_method if request.case_profile.metadata else None
    ml_result = predict_ml_outcome(raw_scores, request.appellant_type, extraction_method, request.filing_date is not None)

    settings = get_settings()
    primary = settings.OUTCOME_MODEL_PRIMARY if settings.OUTCOME_MODEL_PRIMARY in _VALID_PRIMARY else "new_model"
    if not ml_result.model_loaded:
        # Trained model unavailable for any reason — always fall back to
        # the heuristic as primary, regardless of the configured setting.
        primary = "old_heuristic"

    top_level_result = heuristic_result if primary == "old_heuristic" else ml_result_to_simulation_result(ml_result)

    old_vs_new = OldVsNewComparison(
        primary=primary,
        old_heuristic=heuristic_result,
        new_model=ml_result,
    )

    return SimulationResponse(
        result=top_level_result,
        processing_time_ms=0,  # heuristic/model — near-instant
        timestamp=datetime.now(timezone.utc),
        old_vs_new=old_vs_new,
    )
