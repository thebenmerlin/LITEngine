"""Case chat router — retrieval-augmented Q&A grounded in one case's text."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from models.schemas import CaseUploadResponse, ChatRequest, ChatResponse
from services.case_chat import case_chat_service
from services.document_extract import extract_text
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/upload", response_model=CaseUploadResponse)
async def upload_case(file: UploadFile = File(...)):
    content = await file.read()
    text = extract_text(file.filename, content)
    logger.info(f"Uploaded case document: {file.filename} ({len(text.split())} words)")
    return {"text": text, "filename": file.filename, "word_count": len(text.split())}


@router.post("/ask", response_model=ChatResponse)
async def ask(request: ChatRequest):
    if not request.case_text.strip():
        raise HTTPException(status_code=400, detail="case_text is empty")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")

    history = [{"role": m.role, "content": m.content} for m in request.history]
    result = await case_chat_service.ask(request.case_text, request.question, history)
    return result
