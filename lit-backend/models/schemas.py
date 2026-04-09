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

class GraphBuildRequest(BaseModel):
    text: str = Field(..., description="Text to build knowledge graph from")
    entity_types: Optional[List[str]] = Field(
        None,
        description="Entity types to extract (e.g., 'person', 'organization', 'statute', 'case')"
    )


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: Optional[Dict[str, Any]] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    weight: Optional[float] = None


class KnowledgeGraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphBuildResponse(BaseModel):
    graph: KnowledgeGraph
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

class SimulationRequest(BaseModel):
    facts: str = Field(..., description="Case facts to simulate")
    scenario_type: str = Field(
        "outcome",
        description="Type of simulation: 'outcome', 'precedent_match', 'counter_argument'"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional simulation parameters"
    )


class SimulationResult(BaseModel):
    scenario_type: str
    outcome: str
    confidence: float
    reasoning: str
    relevant_precedents: Optional[List[str]] = None
    risk_factors: Optional[List[str]] = None


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
