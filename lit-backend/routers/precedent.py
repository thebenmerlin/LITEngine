"""Precedent router — semantic search + Kanoon fallback + FAISS index management."""

from fastapi import APIRouter, HTTPException
from models.schemas import (
    PrecedentSearchRequest,
    PrecedentSearchResponse,
    PrecedentMatch,
    IndexRequest,
    IndexResponse,
    IndexStats,
    SearchResult,
    JudgmentDetail,
    StatusResponse,
)
from services.embedder import embedder_service
from services.kanoon import kanoon_service
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/precedent", tags=["Precedent"])


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/", response_model=StatusResponse)
async def precedent_status():
    """Check precedent module status."""
    return {"status": "ok", "module": "precedent"}


# ---------------------------------------------------------------------------
# Semantic search  (FAISS → Kanoon fallback)
# ---------------------------------------------------------------------------


@router.post("/search", response_model=PrecedentSearchResponse)
async def search_precedents(request: PrecedentSearchRequest):
    """
    Search precedents using semantic similarity.

    Flow:
      1. Embed the query via HF Inference API (sentence-transformers/all-MiniLM-L6-v2)
      2. Search the FAISS index for top_k nearest neighbours
      3. If results < top_k and use_kanoon is True, supplement with
         keyword results from the Kanoon scraper
    """
    logger.info(
        f"Semantic precedent search: query='{request.query}', "
        f"top_k={request.top_k}, use_kanoon={request.use_kanoon}"
    )

    all_matches: list[PrecedentMatch] = []
    seen_doc_ids: set[str] = set()

    # -- Step 1: FAISS semantic search -----------------------------------------
    if embedder_service.is_empty:
        logger.info("FAISS index is empty — skipping semantic search")
    else:
        try:
            query_emb = await embedder_service._get_embedding(request.query)
        except Exception as exc:
            logger.error(f"Failed to embed query for FAISS search: {exc}")
            query_emb = None

        if query_emb is not None:
            faiss_results = embedder_service.search(query_emb, top_k=request.top_k)

            for hit in faiss_results:
                meta = hit["metadata"]
                doc_id = meta.get("doc_id", "")
                if doc_id in seen_doc_ids:
                    continue
                seen_doc_ids.add(doc_id)

                all_matches.append(
                    PrecedentMatch(
                        title=meta.get("title", ""),
                        url=meta.get("url", ""),
                        doc_id=doc_id,
                        court=meta.get("court"),
                        date=meta.get("date"),
                        snippet=meta.get("text", "")[:300],
                        similarity_score=hit["similarity_score"],
                        source="faiss",
                    )
                )

            logger.info(
                f"FAISS search returned {len(faiss_results)} hits "
                f"({len(all_matches)} unique docs)"
            )

    # -- Step 2: Kanoon fallback (supplement) ----------------------------------
    remaining = request.top_k - len(all_matches)
    if remaining > 0 and request.use_kanoon:
        logger.info(
            f"FAISS results ({len(all_matches)}) < top_k ({request.top_k}), "
            f"supplementing with {remaining} Kanoon results"
        )
        try:
            kanoon_results = await kanoon_service.search(
                query=request.query,
                court=request.court,
                year_from=request.year_from,
                year_to=request.year_to,
                limit=remaining,
            )
            for sr in kanoon_results:
                if sr.doc_id in seen_doc_ids:
                    continue
                seen_doc_ids.add(sr.doc_id)

                # Kanoon results don't have a semantic score — assign a low baseline
                all_matches.append(
                    PrecedentMatch(
                        title=sr.title,
                        url=sr.url,
                        doc_id=sr.doc_id,
                        court=sr.court,
                        date=sr.date,
                        snippet=sr.snippet,
                        similarity_score=0.0,
                        source="kanoon",
                    )
                )
        except HTTPException as exc:
            logger.warning(f"Kanoon fallback failed: {exc.detail}")
        except Exception as exc:
            logger.error(f"Unexpected Kanoon fallback error: {exc}")

    return PrecedentSearchResponse(
        results=all_matches,
        total=len(all_matches),
        query=request.query,
    )


# ---------------------------------------------------------------------------
# Judgment detail (pass-through to Kanoon service)
# ---------------------------------------------------------------------------


@router.get("/{doc_id}", response_model=JudgmentDetail)
async def get_precedent_detail(doc_id: str):
    """
    Fetch full judgment detail from Indian Kanoon.

    Parses the judgment page to extract text, bench, citations,
    and referenced acts/sections.
    """
    logger.info(f"Fetching judgment detail: doc_id={doc_id}")
    try:
        detail = await kanoon_service.get_judgment(doc_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error fetching detail for {doc_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return detail


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------


@router.post("/index", response_model=IndexResponse)
async def index_document(request: IndexRequest):
    """
    Fetch a judgment from Kanoon, chunk it, embed the chunks,
    and add them to the FAISS index.
    """
    doc_id = request.doc_id
    logger.info(f"Indexing document into FAISS: doc_id={doc_id}")

    # Check if already indexed
    existing_ids = embedder_service.get_unique_doc_ids()
    if doc_id in existing_ids:
        # Count chunks for this doc
        chunk_count = sum(
            1 for m in embedder_service._metadata
            if m.get("doc_id") == doc_id
        )
        logger.info(f"Doc {doc_id} already in index ({chunk_count} chunks)")
        return IndexResponse(indexed=True, doc_id=doc_id, chunk_count=chunk_count)

    # Fetch judgment from Kanoon
    try:
        judgment = await kanoon_service.get_judgment(doc_id)
    except HTTPException as exc:
        logger.error(f"Failed to fetch judgment {doc_id} from Kanoon: {exc.detail}")
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"Cannot index: {exc.detail}",
        )
    except Exception as exc:
        logger.error(f"Unexpected error fetching {doc_id} for indexing: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    # Prepare doc for embedding
    doc = {
        "id": doc_id,
        "text": judgment.text,
        "metadata": {
            "title": judgment.title,
            "url": judgment.url,
            "court": judgment.court,
            "date": judgment.date,
        },
    }

    chunk_count = await embedder_service.add_documents([doc])
    logger.info(
        f"Indexed doc {doc_id}: {chunk_count} chunks added to FAISS"
    )

    return IndexResponse(indexed=True, doc_id=doc_id, chunk_count=chunk_count)


@router.get("/index/stats", response_model=IndexStats)
async def index_stats():
    """Return current FAISS index statistics."""
    stats = embedder_service.get_stats()
    return IndexStats(**stats)
