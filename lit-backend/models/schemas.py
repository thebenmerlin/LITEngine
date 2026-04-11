from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# --- Health & Common ---

class HealthResponse(BaseModel):
    app: str
    version: str
    status: str


class StatusResponse(BaseModel):
    status: str
    module: str


# --- Precedent Module ---

class PrecedentSearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language query or case description to search precedents with")
    top_k: int = Field(5, ge=1, le=50, description="Number of semantic results to return")
    use_kanoon: bool = Field(True, description="Fall back to Kanoon scraper if FAISS results < top_k")
    court: Optional[str] = Field(None, description="Filter Kanoon fallback by court")
    year_from: Optional[int] = Field(None, description="Start year filter for Kanoon fallback")
    year_to: Optional[int] = Field(None, description="End year filter for Kanoon fallback")
    limit: int = Field(10, ge=1, le=100, description="Max Kanoon results to fetch for supplementation")


class SearchResult(BaseModel):
    """A single result from an Indian Kanoon search."""
    title: str = Field(..., description="Case name / title")
    url: str = Field(..., description="Full URL to the judgment on indiankanoon.org")
    doc_id: str = Field(..., description="Document ID extracted from the URL")
    court: Optional[str] = Field(None, description="Name of the court")
    date: Optional[str] = Field(None, description="Date of judgment (YYYY-MM-DD)")
    snippet: Optional[str] = Field(None, description="Excerpt / snippet from the search result")
    similarity_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Semantic similarity score (0–1)")


class PrecedentMatch(BaseModel):
    """A precedent result enriched with a semantic similarity score."""
    title: str = Field(..., description="Case name / title")
    url: str = Field(..., description="Full URL to the judgment")
    doc_id: str = Field(..., description="Document ID")
    court: Optional[str] = Field(None, description="Name of the court")
    date: Optional[str] = Field(None, description="Date of judgment (YYYY-MM-DD)")
    snippet: Optional[str] = Field(None, description="Excerpt / snippet")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity score (0–1, higher is more similar)")
    source: str = Field(..., description="Origin of this result: 'faiss' or 'kanoon'")


class PrecedentSearchResponse(BaseModel):
    results: List[PrecedentMatch]
    total: int
    query: str


class IndexRequest(BaseModel):
    doc_id: str = Field(..., description="Document ID to fetch from Kanoon and embed into FAISS index")


class IndexResponse(BaseModel):
    indexed: bool
    doc_id: str
    chunk_count: int


class IndexStats(BaseModel):
    total_documents: int
    index_size_bytes: int


class JudgmentDetail(BaseModel):
    """Full judgment detail fetched from a single doc page."""
    doc_id: str
    title: str
    url: str
    court: Optional[str] = None
    date: Optional[str] = None
    bench: Optional[str] = None
    text: str = Field(..., description="Full judgment text")
    citations: List[str] = Field(default_factory=list, description="Citations referenced in the judgment")
    acts: List[str] = Field(default_factory=list, description="Acts / sections referenced")


class PrecedentResult(BaseModel):
    title: str
    citation: str
    court: str
    date: Optional[str] = None
    summary: str
    relevance_score: float
    source_url: Optional[str] = None


# --- Facts Module ---

class Parties(BaseModel):
    """Litigating parties extracted from a case."""
    petitioner: Optional[str] = Field(None, description="Name(s) of the petitioner/appellant")
    respondent: Optional[str] = Field(None, description="Name(s) of the respondent/respondent")


class StructuredCaseProfile(BaseModel):
    """
    Fully structured case profile extracted from raw legal text.

    Example output:
    ```json
    {
      "parties": {
        "petitioner": "State of Maharashtra",
        "respondent": "Ramesh Kumar @ Ramesh Arjun"
      },
      "legal_issues": [
        "Whether the confession made to a police officer is admissible under Section 25 of the Evidence Act",
        "Whether the investigation violated Section 167 CrPC timelines"
      ],
      "ipc_sections": ["Section 302", "Section 201", "Section 34"],
      "acts_referenced": [
        "Indian Penal Code, 1860",
        "Code of Criminal Procedure, 1973",
        "Indian Evidence Act, 1872"
      ],
      "court_level": "High Court",
      "case_type": "criminal",
      "key_facts": [
        "The deceased was last seen alive at 9:30 PM near the market area",
        "Post-mortem confirmed death due to strangulation",
        "The accused and deceased were known to each other for over 5 years"
      ],
      "relief_sought": "Quashing of FIR No. 45/2023 and grant of anticipatory bail under Section 438 CrPC",
      "metadata": {
        "extraction_method": "hybrid",
        "confidence": 0.82,
        "processing_time_ms": 3450
      }
    }
    ```
    """
    parties: Parties
    legal_issues: List[str] = Field(default_factory=list, description="Key legal questions/issues in the case")
    ipc_sections: List[str] = Field(default_factory=list, description="IPC/CrPC/CPC/Evidence Act sections mentioned")
    acts_referenced: List[str] = Field(default_factory=list, description="Statutes and Acts referenced in the case")
    court_level: str = Field("Unknown", description="Court level: Supreme Court / High Court / District Court / Tribunal")
    case_type: str = Field("other", description="Case classification: criminal / civil / constitutional / tax / labour / other")
    key_facts: List[str] = Field(default_factory=list, description="Bullet-point key facts extracted from the case")
    relief_sought: Optional[str] = Field(None, description="Prayer / relief sought by the petitioner")
    metadata: Optional["ExtractionMetadata"] = Field(None, description="Extraction metadata (method, confidence, timing)")


class ExtractionMetadata(BaseModel):
    """Metadata about how the case profile was extracted."""
    extraction_method: str = Field(..., description="Method used: 'model', 'hybrid', or 'rules'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall extraction confidence (0–1)")
    processing_time_ms: int = Field(..., ge=0, description="Total processing time in milliseconds")


class FactExtractRequest(BaseModel):
    case_text: str = Field(..., description="Raw case description / judgment text to extract structured facts from")
    use_model: bool = Field(True, description="Use InLegalBERT model (falls back to rules if unavailable)")


class FactBatchExtractRequest(BaseModel):
    cases: List[str] = Field(..., min_length=1, max_length=5, description="List of case texts to process (max 5)")


class TaskStatus(BaseModel):
    """Status of an async extraction task (during model cold start)."""
    task_id: str
    status: str = Field(..., description="One of: 'pending', 'processing', 'completed', 'failed'")
    result: Optional[StructuredCaseProfile] = None
    error: Optional[str] = None
    created_at: datetime


# --- Graph Module ---

class GraphNode(BaseModel):
    """A single node in the argument graph."""
    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Display text")
    type: str = Field(..., description="One of: CLAIM, EVIDENCE, STATUTE, PRECEDENT, ISSUE")
    color: str = Field(..., description="Hex color for rendering")
    shape: str = Field(..., description="Shape for rendering: rectangle, ellipse, diamond, hexagon, round-rectangle")
    weight: float = Field(0.5, ge=0.0, le=1.0, description="Importance score (0–1)")
    description: str = Field("", description="Short description of the node")
    weak: bool = Field(False, description="True if node has no supporting evidence edges")


class GraphEdge(BaseModel):
    """A directed edge between two graph nodes."""
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    label: str = Field(..., description="Edge label for rendering")
    type: str = Field(..., description="One of: supports, contradicts, cites, raises")
    strength: float = Field(0.5, ge=0.0, le=1.0, description="Connection strength (0–1)")


class GraphBuildRequest(BaseModel):
    case_profile: StructuredCaseProfile = Field(..., description="Structured case profile from fact extraction")
    precedents: List[SearchResult] = Field(
        default_factory=list,
        max_length=3,
        description="Optional precedent search results to add as PRECEDENT nodes (max 3)",
    )


class GraphBuildResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    weak_nodes: List[str] = Field(default_factory=list, description="Node ids flagged as weak (no supporting evidence)")
    node_count: int
    edge_count: int


class GraphQueryRequest(BaseModel):
    query: str = Field(..., description="Query to search the knowledge graph")
    limit: int = Field(10, ge=1, le=100)


class GraphQueryResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    query: str


# --- Simulation Module ---

class ScoreComponent(BaseModel):
    """One component of the judicial outcome scoring breakdown."""
    component: str = Field(..., description="Component name")
    weight: float = Field(..., ge=0.0, le=1.0, description="Component weight (0–1)")
    raw_score: float = Field(..., ge=0.0, le=1.0, description="Raw score for this component (0–1)")
    weighted_score: float = Field(..., ge=0.0, le=1.0, description="weight × raw_score")
    explanation: str = Field(..., description="Human-readable reason for this score")


class RiskAssessment(BaseModel):
    level: str = Field(..., description="One of: Favorable, Uncertain, Unfavorable")
    color: str = Field(..., description="Color for rendering: green, amber, red")


class SimulationRequest(BaseModel):
    """Request for a judicial outcome prediction."""
    case_profile: "StructuredCaseProfile" = Field(
        ..., description="Structured case profile from fact extraction"
    )
    precedents: List["SearchResult"] = Field(
        default_factory=list,
        max_length=10,
        description="Optional precedent search results (used for alignment scoring)",
    )
    graph_stats: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional: { 'node_count': int, 'weak_nodes': list[str] } from argument graph",
    )


class SimulationResult(BaseModel):
    """Full judicial outcome prediction with explainable scoring."""
    win_probability: float = Field(..., ge=0.0, le=1.0, description="Petitioner win probability (0–1, clamped to [0.05, 0.95])")
    risk_assessment: RiskAssessment
    score_breakdown: List[ScoreComponent]
    key_strengths: List[str] = Field(default_factory=list, description="Top 3 factors helping the case")
    key_weaknesses: List[str] = Field(default_factory=list, description="Top 3 factors hurting the case")
    recommendation: str = Field(..., description="1-2 sentence plain-English recommendation")


class SimulationResponse(BaseModel):
    result: SimulationResult
    processing_time_ms: float
    timestamp: datetime


# --- Embedding Module (internal use) ---

class EmbeddingRequest(BaseModel):
    texts: List[str] = Field(..., description="Texts to generate embeddings for")


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    dimension: int
