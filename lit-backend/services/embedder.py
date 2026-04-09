"""
Embedder service — Hugging Face Inference API + FAISS semantic search.

Provides:
  • Embedding generation via the HF Inference API
    (model: sentence-transformers/all-MiniLM-L6-v2, dim=384)
  • FAISS IndexFlatL2 for fast L2 nearest-neighbour search
  • Automatic text chunking of long judgments
  • Index persistence to JSON (fixtures/precedent_index.json)
  • Retry with exponential backoff for HF API rate limits
"""

import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import httpx
import numpy as np

from config import get_settings
from utils.cache import cache
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HF_API_URL = (
    "https://api-inference.huggingface.co/models/"
    "sentence-transformers/all-MiniLM-L6-v2"
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension

# Chunking defaults
CHUNK_WORD_SIZE = 500
CHUNK_WORD_OVERLAP = 50

# Retry defaults
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds (2, 4, 8, ...)

INDEX_FILE = Path(__file__).resolve().parent.parent / "fixtures" / "precedent_index.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _l2_distance_to_similarity(distance: float) -> float:
    """Convert FAISS L2 (squared Euclidean) distance to a [0, 1] similarity score.

    Uses sigmoid-style mapping:  sim = 1 / (1 + distance)
    - distance 0 → similarity 1.0
    - distance ∞ → similarity 0.0
    """
    return 1.0 / (1.0 + distance)


def _chunk_text(text: str, chunk_size: int = CHUNK_WORD_SIZE,
                overlap: int = CHUNK_WORD_OVERLAP) -> List[str]:
    """Split text into overlapping word-level chunks.

    Attempts sentence-boundary-aware splitting:
      1. Split on sentence terminators (. ! ? followed by space or newline)
      2. Group sentences into chunks up to chunk_size words
      3. If a single sentence exceeds chunk_size, hard-split it
    """
    if not text or not text.strip():
        return []

    # Sentence-level split (non-destructive — keeps terminators)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: List[str] = []
    current_words: List[str] = []
    current_count = 0

    for sentence in sentences:
        s_words = sentence.split()
        s_len = len(s_words)

        # If a single sentence is longer than chunk_size, hard-split it
        if s_len > chunk_size:
            # Flush current buffer first
            if current_words:
                chunks.append(" ".join(current_words))
            current_words = []
            current_count = 0
            # Hard-split the long sentence
            for i in range(0, s_len, chunk_size):
                chunk_words = s_words[i:i + chunk_size]
                chunks.append(" ".join(chunk_words))
            continue

        # If adding this sentence would overflow the chunk
        if current_count + s_len > chunk_size and current_words:
            chunks.append(" ".join(current_words))
            # Overlap: keep last `overlap` words from previous chunk
            overlap_words = current_words[-overlap:] if len(current_words) > overlap else list(current_words)
            current_words = overlap_words + s_words
            current_count = len(current_words)
        else:
            current_words.extend(s_words)
            current_count += s_len

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmbedderService:
    """Hugging Face Inference API embedder with FAISS index management.

    Primary embedding source: HF Inference API (async, via httpx).
    Fallback: local SentenceTransformer model when no valid API key is set.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.HUGGINGFACE_API_KEY
        self.model_name = MODEL_NAME
        self.dimension = EMBEDDING_DIM

        # Decide mode: "hf_api" or "local"
        self._use_hf_api = bool(
            self.api_key and not self.api_key.startswith("hf_your_")
        )
        self._local_model = None
        if not self._use_hf_api:
            logger.warning(
                "No valid HUGGINGFACE_API_KEY — falling back to "
                "local SentenceTransformer model for embeddings"
            )

        # FAISS state
        self._index: Optional[faiss.IndexFlatL2] = None
        self._metadata: List[Dict[str, Any]] = []  # parallel to FAISS vectors

        # HTTP client (lazy, only needed for HF API mode)
        self._client: Optional[httpx.AsyncClient] = None

    # -- Embedding source selection --------------------------------------------

    def _get_local_model(self):
        """Lazy-load the local SentenceTransformer model."""
        if self._local_model is None:
            logger.info(f"Loading local embedding model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(self.model_name)
                logger.info("Local embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load local embedding model: {e}")
                raise
        return self._local_model

    async def _get_embedding_local(self, text: str) -> List[float]:
        """Generate embedding using local SentenceTransformer model."""
        model = self._get_local_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    # -- HTTP client ------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "LIT-Backend/0.1",
                },
                timeout=30.0,
            )
            logger.info("Created async httpx client for HF Inference API")
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("Closed httpx client")

    # -- Embedding via HF Inference API ----------------------------------------

    async def _get_embedding(self, text: str) -> List[float]:
        """Embed a single string.

        Primary: HF Inference API with retry + backoff.
        Fallback: local SentenceTransformer model when no valid API key.
        """
        if not self._use_hf_api:
            return await self._get_embedding_local(text)

        payload = {"inputs": text}
        last_exc: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            client = await self._get_client()
            try:
                resp = await client.post(HF_API_URL, json=payload)

                # HF API returns 503 when model is loading — wait and retry
                if resp.status_code == 503:
                    wait = resp.headers.get("retry-after", str(RETRY_BASE_DELAY * attempt))
                    try:
                        wait_sec = float(wait)
                    except (ValueError, TypeError):
                        wait_sec = RETRY_BASE_DELAY * attempt
                    logger.warning(
                        f"HF model loading, retrying in {wait_sec:.1f}s "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait_sec)
                    last_exc = Exception(f"HF model loading (HTTP {resp.status_code})")
                    continue

                resp.raise_for_status()
                result = resp.json()

                # The API can return a list of embeddings or a dict with "embeddings" key
                if isinstance(result, list) and result and isinstance(result[0], list):
                    return result[0]
                if isinstance(result, dict) and "embeddings" in result:
                    embeddings = result["embeddings"]
                    if isinstance(embeddings, list) and embeddings:
                        return embeddings[0]

                raise ValueError(f"Unexpected HF API response shape: {type(result)}")

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # Rate limited — exponential backoff
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Rate limited by HF API, backing off {delay}s "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    last_exc = exc
                    continue
                logger.error(f"HF API HTTP error: {exc}")
                last_exc = exc
                break  # non-retryable HTTP error

            except httpx.RequestError as exc:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"HF API request error: {exc}, retrying in {delay}s "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                last_exc = exc

            except Exception as exc:
                logger.error(f"Unexpected error during HF API call: {exc}")
                last_exc = exc
                break

        raise RuntimeError(
            f"Failed to get embedding after {MAX_RETRIES} attempts. "
            f"Last error: {last_exc}"
        )

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts sequentially (HF free tier has batch limits)."""
        embeddings: List[List[float]] = []
        for text in texts:
            emb = await self._get_embedding(text)
            embeddings.append(emb)
        logger.info(f"Embedded {len(embeddings)} texts via HF Inference API")
        return embeddings

    # -- FAISS index management ------------------------------------------------

    def _ensure_index(self) -> None:
        """Create an empty FAISS index if one doesn't exist."""
        if self._index is None:
            self._index = faiss.IndexFlatL2(self.dimension)
            logger.info(f"Created new FAISS IndexFlatL2 (dim={self.dimension})")

    @property
    def is_empty(self) -> bool:
        """True if index has no vectors."""
        if self._index is None:
            return True
        return self._index.ntotal == 0

    @property
    def total_vectors(self) -> int:
        """Total number of vectors in the index."""
        if self._index is None:
            return 0
        return self._index.ntotal

    def add_vectors(self, vectors: np.ndarray, metadata: List[Dict[str, Any]]) -> int:
        """Add embedding vectors to the FAISS index with parallel metadata.

        Args:
            vectors: numpy array of shape (n, dim), dtype float32
            metadata: list of dicts, one per vector

        Returns:
            Number of vectors added
        """
        self._ensure_index()

        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)

        faiss.normalize_L2(vectors)  # L2-normalize for consistent distances
        self._index.add(vectors)
        self._metadata.extend(metadata)

        logger.info(
            f"Added {len(vectors)} vectors to FAISS index "
            f"(total now: {self._index.ntotal})"
        )
        return len(vectors)

    def search(self, query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        """Search the FAISS index for nearest neighbours.

        Args:
            query_embedding: 384-dim embedding vector
            top_k: number of results to return

        Returns:
            List of dicts with keys:
                - metadata: the stored metadata dict
                - distance: L2 squared distance
                - similarity_score: normalised similarity in [0, 1]
        """
        if self.is_empty:
            logger.warning("FAISS index is empty — nothing to search")
            return []

        top_k = min(top_k, self._index.ntotal)
        query_vec = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vec)

        distances, indices = self._index.search(query_vec, top_k)

        results: List[Dict[str, Any]] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for padded results
                continue
            meta = self._metadata[idx]
            results.append({
                "metadata": meta,
                "distance": float(dist),
                "similarity_score": round(_l2_distance_to_similarity(float(dist)), 6),
            })

        logger.debug(f"FAISS search returned {len(results)} results (top_k={top_k})")
        return results

    # -- Document ingestion ----------------------------------------------------

    async def add_documents(self, docs: List[Dict[str, Any]]) -> int:
        """Embed and add a list of documents to the FAISS index.

        Each doc dict must have:
            - id: unique document identifier
            - text: the full text to embed (will be chunked)
            - metadata: dict of extra metadata (title, court, date, url, …)

        Returns:
            Total number of chunk-vectors added to the index
        """
        total_added = 0

        for doc in docs:
            doc_id = doc["id"]
            text = doc["text"]
            meta = doc.get("metadata", {})

            chunks = _chunk_text(text)
            if not chunks:
                logger.warning(f"No chunks extracted for doc {doc_id}, skipping")
                continue

            logger.info(
                f"Doc {doc_id}: splitting into {len(chunks)} chunks "
                f"({len(text.split())} words)"
            )

            # Embed chunks sequentially
            embeddings = await self.embed_texts(chunks)

            vectors = np.array(embeddings, dtype=np.float32)
            chunk_metadata = []
            for ci, (emb, chunk_text) in enumerate(zip(embeddings, chunks)):
                chunk_meta = {
                    "doc_id": doc_id,
                    "title": meta.get("title", ""),
                    "url": meta.get("url", ""),
                    "court": meta.get("court"),
                    "date": meta.get("date"),
                    "text": chunk_text,
                    "chunk_index": ci,
                    "total_chunks": len(chunks),
                }
                chunk_metadata.append(chunk_meta)

            self.add_vectors(vectors, chunk_metadata)
            total_added += len(chunks)

        # Persist after ingestion
        self.save_index()
        return total_added

    # -- Persistence -----------------------------------------------------------

    def save_index(self, path: Optional[Path] = None) -> None:
        """Save FAISS index vectors + metadata to a JSON file."""
        path = path or INDEX_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.is_empty:
            logger.info("FAISS index is empty, nothing to save")
            return

        # Extract all vectors from FAISS
        n = self._index.ntotal
        vectors_np = np.zeros((n, self.dimension), dtype=np.float32)
        if n > 0:
            # Reconstruct vectors from the index
            for i in range(n):
                vectors_np[i] = self._index.reconstruct(i)

        data = {
            "model": self.model_name,
            "dimension": self.dimension,
            "vectors": vectors_np.tolist(),
            "metadata": self._metadata,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        size_kb = path.stat().st_size / 1024
        logger.info(f"Saved FAISS index ({n} vectors) to {path} ({size_kb:.1f} KB)")

    def load_index(self, path: Optional[Path] = None) -> bool:
        """Load FAISS index from a JSON file.

        Returns True if loaded successfully, False if file not found or invalid.
        """
        path = path or INDEX_FILE

        if not path.exists():
            logger.info(f"Index file not found: {path}")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            vectors = data.get("vectors", [])
            metadata = data.get("metadata", [])
            dimension = data.get("dimension", self.dimension)

            if not vectors:
                logger.warning(f"Index file {path} has no vectors")
                return False

            if len(vectors) != len(metadata):
                logger.error(
                    f"Index vector count ({len(vectors)}) != "
                    f"metadata count ({len(metadata)})"
                )
                return False

            self._index = faiss.IndexFlatL2(dimension)
            vectors_np = np.array(vectors, dtype=np.float32)
            self._index.add(vectors_np)
            self._metadata = metadata

            logger.info(
                f"Loaded FAISS index from {path}: "
                f"{len(vectors)} vectors, {len(set(m['doc_id'] for m in metadata))} unique docs"
            )
            return True

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(f"Failed to load index from {path}: {exc}")
            return False

    def get_unique_doc_ids(self) -> List[str]:
        """Return sorted list of unique doc_ids currently in the index."""
        ids = set()
        for m in self._metadata:
            if "doc_id" in m:
                ids.add(m["doc_id"])
        return sorted(ids)

    def get_stats(self) -> Dict[str, int]:
        """Return index statistics."""
        total_documents = len(self.get_unique_doc_ids())
        index_size_bytes = 0
        if INDEX_FILE.exists():
            index_size_bytes = INDEX_FILE.stat().st_size
        elif self._index is not None:
            # Estimate: n * dim * 4 bytes (float32)
            index_size_bytes = self._index.ntotal * self.dimension * 4

        return {
            "total_documents": total_documents,
            "index_size_bytes": index_size_bytes,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

embedder_service = EmbedderService()
