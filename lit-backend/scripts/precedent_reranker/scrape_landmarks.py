"""
Identifies the most-frequently-cited precedents across the existing
650-judgment raw_cache (from the outcome-dataset sessions) and scrapes
those specific judgments — they aren't in the corpus themselves (the
corpus skews recent High Court decisions citing older landmarks), but
they're exactly the well-established precedents worth having ground
truth for.

Reuses the existing, already-fixed Kanoon scraper (services/kanoon.py)
and the existing on-disk raw_cache (scripts/outcome_dataset/scrape.py) —
no new scraping infrastructure, just a new selection of what to fetch.

Citation-string search on Indian Kanoon reliably surfaces the exact
matching judgment as the top result (it's a well-supported query
pattern on the site) — spot-checked before trusting this at scale.

    ./venv/bin/python3 -m scripts.precedent_reranker.scrape_landmarks
"""

import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset.scrape import RAW_CACHE_DIR, fetch_judgment, load_cached_judgment
from services.kanoon import kanoon_service
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "precedent_reranker"
LANDMARKS_MAP_PATH = DATA_DIR / "landmark_citation_map.json"

MIN_CITING_DOCS = 4
TOP_N_LANDMARKS = 70


def load_corpus() -> Dict[str, dict]:
    docs = {}
    for f in RAW_CACHE_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            docs[d["doc_id"]] = d
        except (json.JSONDecodeError, KeyError):
            continue
    return docs


def top_citation_strings(docs: Dict[str, dict], top_n: int, min_count: int) -> List[str]:
    counter: Counter = Counter()
    for d in docs.values():
        for c in d.get("citations", []):
            counter[c.strip().upper()] += 1
    ranked = [c for c, n in counter.most_common() if n >= min_count]
    return ranked[:top_n]


CITATION_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")


def _citation_year(citation: str) -> Optional[int]:
    m = CITATION_YEAR_RE.search(citation)
    return int(m.group(1)) if m else None


def _is_supreme_court_citation(citation: str) -> bool:
    c = citation.upper()
    if re.search(r"\bPC\b", c):
        return False  # Privy Council, not Supreme Court
    return "SCC" in c or "SCR" in c or bool(re.search(r"\bAIR\s+\d{4}\s+SC\b", c))


def _looks_valid(citation: str, detail) -> bool:
    """Guards against Kanoon's citation-string search sometimes surfacing a
    RECENT document that merely discusses/quotes the citation prominently,
    rather than the actual old landmark judgment itself — spot-checked and
    confirmed this happens for roughly half of naive top-1 matches. A
    genuine match's own decision date should be within ~2 years of the
    citation's reporter year (reporters publish shortly after decision),
    and for SCC/SCR/AIR-SC citations the court should actually be the
    Supreme Court."""
    cy = _citation_year(citation)
    if cy is None or not detail.date:
        return False
    try:
        doc_year = int(detail.date[:4])
    except ValueError:
        return False
    if abs(doc_year - cy) > 2:
        return False
    if _is_supreme_court_citation(citation):
        return bool(detail.court) and "supreme court" in detail.court.lower()
    return True


async def resolve_and_fetch_landmark(citation: str, existing_doc_ids: set) -> Optional[dict]:
    """Search Kanoon for the exact citation string; fetch the top result
    and validate it before trusting it as ground truth."""
    kanoon_service.use_fixtures = False
    results = None
    for attempt in range(2):
        try:
            results = await kanoon_service.search(citation, limit=3)
            break
        except Exception as exc:
            if attempt == 0:
                logger.warning(f"Search failed for citation {citation!r} (retrying): {exc}")
                await asyncio.sleep(2.0)
            else:
                logger.warning(f"Search failed for citation {citation!r}: {exc}")
                return None

    if not results:
        logger.warning(f"No search results for citation {citation!r}")
        return None

    top = results[0]
    if top.doc_id in existing_doc_ids:
        detail = load_cached_judgment(top.doc_id)
    else:
        detail = await fetch_judgment(top.doc_id)

    if detail is None:
        logger.warning(f"Failed to fetch judgment for citation {citation!r} (doc_id={top.doc_id})")
        return None

    if not _looks_valid(citation, detail):
        logger.warning(
            f"Citation {citation!r} -> doc {top.doc_id} ({detail.date}, {detail.court}) "
            "failed year/court validation, rejecting"
        )
        return None

    return {
        "citation": citation,
        "doc_id": detail.doc_id,
        "title": detail.title,
        "court": detail.court,
        "date": detail.date,
    }


async def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    docs = load_corpus()
    logger.info(f"Loaded {len(docs)} cached judgments from corpus")

    citations = top_citation_strings(docs, TOP_N_LANDMARKS, MIN_CITING_DOCS)
    logger.info(f"Top {len(citations)} citation strings (cited >= {MIN_CITING_DOCS}x): {citations[:5]}...")

    existing_doc_ids = set(docs.keys())
    landmarks = []
    for i, citation in enumerate(citations, 1):
        result = await resolve_and_fetch_landmark(citation, existing_doc_ids)
        if result:
            landmarks.append(result)
            logger.info(f"[{i}/{len(citations)}] {citation} -> {result['doc_id']}: {result['title'][:60]}")
        else:
            logger.warning(f"[{i}/{len(citations)}] {citation} -> FAILED, skipping")

    LANDMARKS_MAP_PATH.write_text(json.dumps(landmarks, indent=2), encoding="utf-8")
    logger.info(f"Resolved {len(landmarks)}/{len(citations)} landmarks, saved map to {LANDMARKS_MAP_PATH}")

    await kanoon_service.close()


if __name__ == "__main__":
    asyncio.run(main())
