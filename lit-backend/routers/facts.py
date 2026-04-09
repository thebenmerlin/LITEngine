"""
Case fact extraction router.

Endpoints:
  POST /api/v1/facts/extract          — extract structured profile from case text
  POST /api/v1/facts/extract/batch    — batch extract up to 5 cases concurrently
  GET  /api/v1/facts/status/<task_id> — poll async extraction task
  GET  /api/v1/facts/                 — module status

Handles InLegalBERT model cold start by returning 202 Accepted with a task_id
for polling when the model is warming up on the HF Inference API.
"""

import asyncio
from typing import List

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse

from models.schemas import (
    FactExtractRequest,
    FactBatchExtractRequest,
    StructuredCaseProfile,
    TaskStatus,
    StatusResponse,
)
from services.extractor import (
    extractor_service,
    ModelLoadingError,
    create_task,
    get_task,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/facts", tags=["Facts"])


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/", response_model=StatusResponse)
async def facts_status():
    """Check facts module status."""
    return {"status": "ok", "module": "facts"}


# ---------------------------------------------------------------------------
# Task polling
# ---------------------------------------------------------------------------


@router.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    Poll the status of an async extraction task.

    Returns the task status (pending / processing / completed / failed)
    and the result if available.
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found. Tasks are retained for 5 minutes.",
        )
    return task


# ---------------------------------------------------------------------------
# Single extraction
# ---------------------------------------------------------------------------


@router.post("/extract", response_model=StructuredCaseProfile)
async def extract_facts(request: FactExtractRequest, response: Response):
    """
    Extract structured legal elements from raw case text.

    Uses InLegalBERT via HF Inference API if available, with rule-based
    fallback. If the model is warming up (cold start), returns 202 Accepted
    with a task_id for polling.

    Example response:
    ```json
    {
      "parties": {
        "petitioner": "State of Maharashtra",
        "respondent": "Ramesh Kumar"
      },
      "legal_issues": [
        "Whether confession to police officer is admissible under Section 25 Evidence Act"
      ],
      "ipc_sections": ["Section 302", "Section 201"],
      "acts_referenced": [
        "Indian Penal Code, 1860",
        "Code of Criminal Procedure, 1973",
        "Indian Evidence Act, 1872"
      ],
      "court_level": "High Court",
      "case_type": "criminal",
      "key_facts": [
        "The deceased was last seen alive at 9:30 PM near the market area",
        "Post-mortem confirmed death due to strangulation"
      ],
      "relief_sought": "Quashing of FIR No. 45/2023",
      "metadata": {
        "extraction_method": "hybrid",
        "confidence": 0.82,
        "processing_time_ms": 3450
      }
    }
    ```
    """
    logger.info(
        f"Fact extraction requested: {len(request.case_text)} chars, "
        f"use_model={request.use_model}"
    )

    try:
        profile, meta = await extractor_service.extract(
            case_text=request.case_text,
            use_model=request.use_model,
        )
        profile.metadata = meta
        return profile

    except ModelLoadingError as exc:
        # Model is warming up — create async task and return 202
        task_id, task = create_task()
        logger.info(
            f"InLegalBERT model loading — returning 202, task_id={task_id}, "
            f"retry_after={exc.retry_after:.0f}s"
        )

        # Fire-and-forget background task
        asyncio.create_task(
            extractor_service.extract_async(
                task_id=task_id,
                case_text=request.case_text,
                use_model=request.use_model,
            )
        )

        return JSONResponse(
            status_code=202,
            content={
                "task_id": task_id,
                "status": "pending",
                "message": (
                    f"InLegalBERT model is warming up ({exc.retry_after:.0f}s). "
                    f"Poll GET /api/v1/facts/status/{task_id} for the result."
                ),
                "poll_url": f"/api/v1/facts/status/{task_id}",
            },
        )

    except Exception as exc:
        logger.error(f"Unexpected error during fact extraction: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------


@router.post("/extract/batch")
async def extract_facts_batch(request: FactBatchExtractRequest, response: Response):
    """
    Extract structured profiles for multiple cases concurrently.

    Processes up to 5 cases in parallel using asyncio.gather.
    If the model is warming up, returns 202 with task_id for each case.

    Returns a list of StructuredCaseProfile (or task references for 202s).
    """
    cases = request.cases
    if not cases:
        raise HTTPException(status_code=400, detail="No cases provided")

    if len(cases) > 5:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum 5 cases allowed, got {len(cases)}",
        )

    logger.info(f"Batch extraction requested: {len(cases)} cases")

    # Launch all extractions concurrently
    async def _extract_one(
        case_text: str, index: int
    ) -> dict:
        try:
            profile, meta = await extractor_service.extract(
                case_text=case_text,
                use_model=True,
            )
            profile.metadata = meta
            return {
                "index": index,
                "status": "completed",
                "result": profile.model_dump(),
            }
        except ModelLoadingError as exc:
            task_id, _ = create_task()
            asyncio.create_task(
                extractor_service.extract_async(
                    task_id=task_id,
                    case_text=case_text,
                    use_model=True,
                )
            )
            return {
                "index": index,
                "status": "pending",
                "task_id": task_id,
                "poll_url": f"/api/v1/facts/status/{task_id}",
                "message": f"Model warming up, retry_after={exc.retry_after:.0f}s",
            }
        except Exception as exc:
            logger.error(f"Batch extraction error for case {index}: {exc}")
            return {
                "index": index,
                "status": "failed",
                "error": str(exc),
            }

    results = await asyncio.gather(
        *[_extract_one(text, i) for i, text in enumerate(cases)]
    )

    # Check if any case returned 202 — if so, return 202 for the whole batch
    has_pending = any(r["status"] == "pending" for r in results)
    if has_pending:
        return JSONResponse(
            status_code=202,
            content={
                "status": "partial",
                "message": "Some cases queued due to model cold start.",
                "results": results,
            },
        )

    # All completed
    profiles = [StructuredCaseProfile(**r["result"]) for r in results]
    return profiles
