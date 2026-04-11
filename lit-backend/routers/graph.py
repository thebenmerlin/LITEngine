from fastapi import APIRouter, HTTPException

from models.schemas import (
    GraphBuildRequest,
    GraphBuildResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    StatusResponse,
)
from services.graph_builder import build_argument_graph
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["Graph"])


@router.get("/", response_model=StatusResponse)
async def graph_status():
    """Check graph module status."""
    return {"status": "ok", "module": "graph"}


@router.post("/build", response_model=GraphBuildResponse)
async def build_graph(request: GraphBuildRequest):
    """
    Build an argument graph from a StructuredCaseProfile.

    Creates nodes for issues, claims, statutes, evidence, and precedents,
    with edges representing supports/contradicts/cites/raises relationships.
    Flags weak claims (no supporting evidence).
    """
    logger.info(
        f"Building argument graph: {len(request.case_profile.legal_issues)} issues, "
        f"{len(request.case_profile.ipc_sections)} sections, "
        f"{len(request.case_profile.key_facts)} facts, "
        f"{len(request.precedents)} precedents"
    )

    try:
        result = build_argument_graph(
            profile=request.case_profile,
            precedents=request.precedents,
        )
    except Exception as exc:
        logger.error(f"Failed to build argument graph: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return GraphBuildResponse(**result)


@router.post("/query", response_model=GraphQueryResponse)
async def query_graph(request: GraphQueryRequest):
    """
    Query the knowledge graph.

    Searches for nodes and edges matching the query text.
    """
    logger.info(f"Graph query: '{request.query}'")
    # TODO: Implement graph query with traversal and filtering
    return GraphQueryResponse(
        nodes=[],
        edges=[],
        query=request.query,
    )
