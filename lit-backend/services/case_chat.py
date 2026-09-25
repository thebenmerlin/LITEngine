"""
Case chat — retrieval-augmented Q&A grounded in a single case's text.

Reuses the app's existing embedding infrastructure (services.embedder:
same chunker, same HF-Inference-API-with-local-fallback embedder) so
retrieval quality and availability match the rest of the app exactly —
no separate embedding pathway. What's new here is generation: an
instruction-tuned chat model is called with the case's own retrieved
excerpts as its only source material, told to answer only from them and
to cite them inline (e.g. "[S1]"), and to say so plainly when the
excerpts don't contain the answer. If no HF key is configured or the
call fails, this falls back to returning the top excerpt itself rather
than failing the request — the same graceful-degradation shape as
services.extractor's InLegalBERT-unavailable fallback.
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

from config import get_settings
from services.embedder import _chunk_text, embedder_service
from utils.logger import get_logger

logger = get_logger(__name__)

CHAT_COMPLETIONS_URL = "https://router.huggingface.co/v1/chat/completions"

MAX_RETRIES = 2
RETRY_BASE_DELAY = 3.0

# Per-case (chunks, normalized embedding matrix) cache, keyed by a hash of
# the case text — repeat questions about the same case (the common case,
# since the frontend holds one case in the workspace at a time) don't
# re-embed every turn. Small bound since each entry is one case's chunks.
MAX_CACHED_CASES = 20
_case_index_cache: "OrderedDict[str, Tuple[List[str], np.ndarray]]" = OrderedDict()

SYSTEM_PROMPT = (
    "You are a legal research assistant answering questions about ONE specific "
    "court case. You are given numbered excerpts from that case's own judgment "
    "text — this is your only source of truth. Answer using only what the "
    "excerpts support, and cite the excerpts you rely on inline like [S1] or "
    "[S2]. If the excerpts don't contain the answer, say plainly that this "
    "case's text doesn't cover it — never guess or use outside knowledge."
)


def _case_key(case_text: str) -> str:
    return hashlib.sha256(case_text.strip().encode("utf-8")).hexdigest()


async def _get_or_build_index(case_text: str) -> Tuple[List[str], np.ndarray]:
    key = _case_key(case_text)
    if key in _case_index_cache:
        _case_index_cache.move_to_end(key)
        return _case_index_cache[key]

    chunks = _chunk_text(case_text)
    if not chunks:
        chunks = [case_text.strip()] if case_text.strip() else []
    if not chunks:
        return [], np.zeros((0, embedder_service.dimension), dtype=np.float32)

    embeddings = await embedder_service.embed_texts(chunks)
    matrix = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms  # pre-normalize once; queries normalize per-call

    _case_index_cache[key] = (chunks, matrix)
    _case_index_cache.move_to_end(key)
    if len(_case_index_cache) > MAX_CACHED_CASES:
        _case_index_cache.popitem(last=False)
    return chunks, matrix


async def _retrieve(case_text: str, question: str, top_k: int) -> List[Dict[str, Any]]:
    chunks, matrix = await _get_or_build_index(case_text)
    if not chunks:
        return []

    query_embeddings = await embedder_service.embed_texts([question])
    query_vec = np.array(query_embeddings[0], dtype=np.float32)
    norm = np.linalg.norm(query_vec)
    if norm > 0:
        query_vec = query_vec / norm

    top_k = min(top_k, len(chunks))
    scores = matrix @ query_vec
    top_indices = np.argsort(-scores)[:top_k]

    return [
        {"index": rank + 1, "text": chunks[i], "similarity_score": round(float(scores[i]), 4)}
        for rank, i in enumerate(top_indices)
    ]


def _extractive_fallback(sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "This case's text doesn't contain enough content to search."
    top = sources[0]
    return (
        "The generation model isn't available right now, so here is the most "
        f"relevant excerpt from the case instead [S1]:\n\n{top['text']}"
    )


class CaseChatService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.settings.HUGGINGFACE_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=45.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _generate(self, sources: List[Dict[str, Any]], question: str, history: List[Dict[str, str]]) -> str:
        excerpts = "\n\n".join(f"[S{s['index']}] {s['text']}" for s in sources)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({
            "role": "user",
            "content": f"Case excerpts:\n\n{excerpts}\n\nQuestion: {question}",
        })

        payload = {
            "model": self.settings.CHAT_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
        }

        client = await self._get_client()
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.post(CHAT_COMPLETIONS_URL, json=payload)
                if resp.status_code == 503:
                    wait = RETRY_BASE_DELAY * attempt
                    logger.warning(f"Chat model loading, retrying in {wait:.1f}s (attempt {attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                    last_exc = RuntimeError("model loading")
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:  # noqa: BLE001 — any failure here should fall back, not crash the request
                last_exc = exc
                logger.warning(f"Chat generation failed (attempt {attempt}/{MAX_RETRIES}): {exc}")
        raise RuntimeError(f"Chat generation unavailable: {last_exc}")

    async def ask(self, case_text: str, question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        started = time.time()
        top_k = self.settings.CHAT_TOP_K
        sources = await _retrieve(case_text, question, top_k)

        use_model = bool(self.settings.HUGGINGFACE_API_KEY and not self.settings.HUGGINGFACE_API_KEY.startswith("hf_your_"))
        if use_model:
            try:
                answer = await self._generate(sources, question, history)
                method = "generated"
            except Exception as exc:
                logger.warning(f"Falling back to extractive answer: {exc}")
                answer = _extractive_fallback(sources)
                method = "extractive"
        else:
            answer = _extractive_fallback(sources)
            method = "extractive"

        logger.info(f"case_chat.ask: method={method} sources={len(sources)} elapsed_ms={int((time.time()-started)*1000)}")
        return {"answer": answer, "sources": sources, "method": method}


case_chat_service = CaseChatService()
