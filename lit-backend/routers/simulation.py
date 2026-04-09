from fastapi import APIRouter
from datetime import datetime
from models.schemas import (
    SimulationRequest,
    SimulationResponse,
    StatusResponse,
)
from services.simulator import simulator_service
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation"])


@router.get("/", response_model=StatusResponse)
async def simulation_status():
    """Check simulation module status."""
    return {"status": "ok", "module": "simulation"}


@router.post("/run", response_model=SimulationResponse)
async def run_simulation(request: SimulationRequest):
    """
    Run a legal case simulation.

    Analyzes case facts and simulates outcomes, finds relevant
    precedents, or generates counter-arguments.
    """
    logger.info(
        f"Running simulation: type='{request.scenario_type}', "
        f"facts={len(request.facts)} chars"
    )
    result = await simulator_service.run_simulation(
        facts=request.facts,
        scenario_type=request.scenario_type,
        parameters=request.parameters,
    )
    return SimulationResponse(**result)
