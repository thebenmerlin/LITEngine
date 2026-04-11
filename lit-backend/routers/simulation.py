from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from models.schemas import (
    SimulationRequest,
    SimulationResponse,
    SimulationResult,
    StatusResponse,
)
from services.simulator import predict_outcome
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation"])


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
        f"graph_stats={'yes' if request.graph_stats else 'no'}"
    )

    try:
        result: SimulationResult = predict_outcome(
            profile=request.case_profile,
            precedents=request.precedents,
            graph_stats=request.graph_stats,
        )
    except Exception as exc:
        logger.error(f"Simulation prediction failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return SimulationResponse(
        result=result,
        processing_time_ms=0,  # heuristic — near-instant
        timestamp=datetime.now(timezone.utc),
    )
