"""
Raw judgment collection for the outcome-labeling dataset.

Reuses services.kanoon.KanoonService for search + document fetch (rather
than writing a parallel scraper), and adds a persistent on-disk cache —
separate from KanoonService's in-memory TTLCache, which doesn't survive
process restarts — so re-running this script never re-fetches a judgment
we already have.
"""

import asyncio
import json
from pathlib import Path
from typing import List, Optional, Set

from models.schemas import JudgmentDetail, SearchResult
from services.kanoon import kanoon_service
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_CACHE_DIR = DATA_DIR / "raw_cache"
RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Criminal-appeal-flavored search queries, rotated to get topical spread
# rather than paginating one query hundreds of pages deep.
SEARCH_QUERIES = [
    "criminal appeal conviction",
    "criminal appeal acquittal",
    "criminal appeal sentence reduced",
    "criminal appeal bail",
    "criminal revision petition",
    "appeal against conviction IPC",
    "criminal appeal high court dismissed",
    "criminal appeal supreme court allowed",
]

MAX_PAGES_PER_QUERY = 25
MAX_CONSECUTIVE_FAILURES = 6


def _cache_path(doc_id: str) -> Path:
    return RAW_CACHE_DIR / f"{doc_id}.json"


def load_cached_judgment(doc_id: str) -> Optional[JudgmentDetail]:
    path = _cache_path(doc_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return JudgmentDetail(**data)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning(f"Corrupt raw cache for {doc_id}, will re-fetch: {exc}")
        return None


def save_cached_judgment(doc_id: str, detail: JudgmentDetail) -> None:
    _cache_path(doc_id).write_text(
        json.dumps(detail.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def collect_doc_ids(target_count: int, seen: Optional[Set[str]] = None) -> List[SearchResult]:
    """Search across the rotating query list, paginating each until
    `target_count` unique doc_ids are collected or the queries run dry."""
    kanoon_service.use_fixtures = False  # force live scraping for this script

    seen = set(seen) if seen else set()
    collected: List[SearchResult] = []
    consecutive_failures = 0

    for query in SEARCH_QUERIES:
        if len(collected) >= target_count:
            break
        empty_pages_in_a_row = 0
        for pagenum in range(MAX_PAGES_PER_QUERY):
            if len(collected) >= target_count:
                break
            try:
                results = await kanoon_service.search(query, pagenum=pagenum, limit=20)
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                logger.warning(f"Search failed (query={query!r}, page={pagenum}): {exc}")
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error("Too many consecutive search failures — aborting collection.")
                    return collected
                continue

            if not results:
                empty_pages_in_a_row += 1
                if empty_pages_in_a_row >= 2:
                    break
                continue
            empty_pages_in_a_row = 0

            new_count = 0
            for r in results:
                if r.doc_id not in seen:
                    seen.add(r.doc_id)
                    collected.append(r)
                    new_count += 1

            logger.info(
                f"query={query!r} page={pagenum}: +{new_count} new "
                f"(total {len(collected)}/{target_count})"
            )
            if new_count == 0:
                break  # fully duplicate page — this query is exhausted

    return collected


async def fetch_judgment(doc_id: str, retries: int = 1) -> Optional[JudgmentDetail]:
    """Fetch full judgment detail, using the on-disk cache first.

    Live fetch failures observed in practice come in short transient
    bursts rather than a persistently dead endpoint, so one short-delay
    retry noticeably improves yield without materially slowing the run.
    """
    cached = load_cached_judgment(doc_id)
    if cached is not None:
        return cached

    kanoon_service.use_fixtures = False
    detail = None
    for attempt in range(retries + 1):
        try:
            detail = await kanoon_service.get_judgment(doc_id)
            break
        except Exception as exc:
            if attempt < retries:
                logger.warning(f"Fetch failed for {doc_id} (attempt {attempt + 1}), retrying: {exc}")
                await asyncio.sleep(2.0)
            else:
                logger.warning(f"Failed to fetch judgment {doc_id}: {exc}")
                return None

    save_cached_judgment(doc_id, detail)
    return detail
