from fastapi import APIRouter
from models.schemas import (
    GraphBuildRequest,
    GraphBuildResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    StatusResponse,
)
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
    Build a knowledge graph from legal text.

    Extracts entities (persons, organizations, statutes, cases)
    and their relationships to construct a structured graph.
    """
    logger.info(f"Building graph from text ({len(request.text)} chars)")
    # TODO: Implement NER and relationship extraction
    return GraphBuildResponse(
        graph={"nodes": [], "edges": []},
        node_count=0,
        edge_count=0,
    )


@router.post("/query", response_model=GraphQueryResponse)
async def query_graph(request: GraphQueryRequest):
    """
    Query the knowledge graph.

    Searches for entities and relationships matching the query.
    """
    logger.info(f"Graph query: '{request.query}'")
    # TODO: Implement graph query with traversal and filtering
    return GraphQueryResponse(
        nodes=[],
        edges=[],
        query=request.query,
    )
