import os
import re
import json
import asyncio
import random
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from config import get_settings
from models.schemas import SearchResult, JudgmentDetail
from utils.cache import cache
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KANOON_SEARCH_URL = "https://indiankanoon.org/search/"
KANOON_DOC_URL = "https://indiankanoon.org/doc/{doc_id}/"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Patterns for extracting metadata from judgment pages
DATE_PATTERNS = [
    # "Date: 24-04-1973" or "Date: 24 April 1973"
    re.compile(r"Date\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE),
    # "Dated: 24.04.1973"
    re.compile(r"Dated\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE),
]

BENCH_PATTERNS = [
    # "Bench: Sikri, J., Shelat, J."
    re.compile(r"(?:Bench|Coram)\s*:\s*(.+?)(?:\n{2}|$)", re.IGNORECASE),
    # "Before: Chief Justice ..."
    re.compile(r"Before\s*:\s*(.+?)(?:\n{2}|$)", re.IGNORECASE),
]

COURT_PATTERNS = [
    re.compile(r"(?:Court|Reported in)\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE),
    re.compile(
        r"(Supreme Court of India|[\w\s]+High Court|[\w\s]+Bench)",
        re.IGNORECASE,
    ),
]

CITATION_PATTERNS = [
    # AIR 1973 SC 1461, (1973) 4 SCC 225, [1973] Suppl. SCR 1
    re.compile(r"\bAIR\s+\d{4}\s+\w+\s+\d+\b"),
    re.compile(r"\(\d{4}\)\s+\d+\s+SCC\s+\d+"),
    re.compile(r"\[\d{4}\][\w\s\.]+\bSCR\b[\w\s\d\.]*"),
    re.compile(r"\b(\d{4})\s+Cr[Ll]?J\s+\d+\b"),
]

SECTION_PATTERNS = [
    re.compile(
        r"(?:Article|Section|Section[s]?|Clause|Order)\s+"
        r"\d+[A-Za-z]?(?:\(\d+\))?(?:\([A-Za-z]\))?"
        r"(?:\s+of\s+[\w\s,]+?)?(?:\s*Act)?(?:\s*,\s*\d{4})?",
        re.IGNORECASE,
    ),
    re.compile(
        r"[\w\s]+Act\s*,?\s*\d{4}",
        re.IGNORECASE,
    ),
]

FIXTURES_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "kanoon_sample.json"

CACHE_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _extract_doc_id(url: str) -> Optional[str]:
    """Pull the numeric doc id out of an indiankanoon URL."""
    match = re.search(r"/doc/(\d+)/?", url)
    return match.group(1) if match else None


def _normalize_date(raw: str) -> Optional[str]:
    """Try to return a YYYY-MM-DD string from a loose date string."""
    raw = raw.strip()
    # DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            return raw
    # DD Month YYYY
    m = re.match(
        r"(\d{1,2})\s+"
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+"
        r"(\d{4})",
        raw,
        re.IGNORECASE,
    )
    if m:
        try:
            dt = datetime.strptime(raw.strip(), "%d %B %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return raw
    return raw or None


def _clean_text(element) -> str:
    """Return cleaned inner text from a BeautifulSoup element."""
    text = element.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class KanoonService:
    """Scraper for indiankanoon.org with caching, fixtures fallback, and async httpx."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.use_fixtures = os.getenv("USE_FIXTURES", "").lower() == "true"
        self._client: Optional[httpx.AsyncClient] = None

        if self.use_fixtures:
            logger.warning("USE_FIXTURES=true — serving data from fixtures only")

    # -- client ----------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                timeout=30.0,
                follow_redirects=True,
                http2=True,
            )
            logger.info("Created async httpx client with browser headers")
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Closed httpx client")

    # -- polite delay ----------------------------------------------------------

    @staticmethod
    async def _delay() -> None:
        """Sleep 0.5–1 s to be respectful to the remote server."""
        await asyncio.sleep(random.uniform(0.5, 1.0))

    # -- fixtures --------------------------------------------------------------

    def _load_fixtures(self) -> Dict[str, Any]:
        with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    async def _fixture_search(self, query: str, limit: int) -> List[SearchResult]:
        data = self._load_fixtures()
        results = data.get("search_results", [])
        # Simple substring match on title or snippet
        q = query.lower()
        matched = [
            r for r in results
            if q in r["title"].lower() or q in r.get("snippet", "").lower()
        ]
        # If nothing matches, return all up to limit
        if not matched:
            matched = results
        return [SearchResult(**r) for r in matched[:limit]]

    async def _fixture_detail(self, doc_id: str) -> Optional[JudgmentDetail]:
        data = self._load_fixtures()
        details = data.get("judgment_details", {})
        detail = details.get(doc_id)
        if detail is None:
            return None
        return JudgmentDetail(**detail)

    # -- live scraping ---------------------------------------------------------

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch URL and return HTML text, or None on failure."""
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error fetching {url}: {exc}")
            return None

    def _parse_search_results(self, html: str, limit: int) -> List[SearchResult]:
        """Parse the HTML from a search results page into SearchResult list."""
        soup = BeautifulSoup(html, "html.parser")
        results: List[SearchResult] = []

        # Indian Kanoon search results are typically inside <div class="result">
        # or inside specific container divs. We try multiple selectors.
        containers = (
            soup.select("div.result")
            or soup.select("div.search-result")
            or soup.select("div.doc")
            or soup.select("div[itemprop='result']")
        )

        if not containers:
            # Fallback: look for <p> tags containing <a> links to /doc/
            for para in soup.select("p"):
                link = para.find("a", href=re.compile(r"/doc/\d+/"))
                if link:
                    title = _clean_text(link) or _clean_text(para)
                    url = link.get("href", "")
                    if url and not url.startswith("http"):
                        url = "https://indiankanoon.org" + url
                    snippet = _clean_text(para).replace(title, "").strip()
                    doc_id = _extract_doc_id(url)
                    if doc_id:
                        results.append(
                            SearchResult(
                                title=title,
                                url=url,
                                doc_id=doc_id,
                                court=None,
                                date=None,
                                snippet=snippet[:500] if snippet else None,
                            )
                        )
            return results[:limit]

        for container in containers:
            # Title / link
            link = container.find("a", href=re.compile(r"/doc/\d+/"))
            title = _clean_text(link) if link else _clean_text(container)
            href = link.get("href", "") if link else ""
            if href and not href.startswith("http"):
                href = "https://indiankanoon.org" + href

            doc_id = _extract_doc_id(href)

            # Court
            court = None
            court_el = container.find(
                True, class_=re.compile(r"court|bench", re.I)
            ) or container.find(
                True, string=re.compile(r"(Supreme Court|High Court)", re.I)
            )
            if court_el:
                court = _clean_text(court_el)

            # Date
            date = None
            date_el = container.find(
                True, class_=re.compile(r"date", re.I)
            )
            if date_el:
                date = _normalize_date(_clean_text(date_el))

            # Snippet
            snippet_el = container.find(
                True, class_=re.compile(r"snippet|excerpt|fragment", re.I)
            )
            snippet = _clean_text(snippet_el) if snippet_el else _clean_text(container)
            # Remove title from snippet
            snippet = snippet.replace(title, "").strip()[:500] or None

            if doc_id:
                results.append(
                    SearchResult(
                        title=title,
                        url=href,
                        doc_id=doc_id,
                        court=court,
                        date=date,
                        snippet=snippet,
                    )
                )

        return results[:limit]

    def _parse_judgment_detail(self, html: str, doc_id: str) -> JudgmentDetail:
        """Parse a single judgment page into a JudgmentDetail."""
        soup = BeautifulSoup(html, "html.parser")

        # Title — usually in the first <h1> or <h2>
        title_el = soup.find("h1") or soup.find("h2")
        title = _clean_text(title_el) if title_el else f"Judgment {doc_id}"

        # URL
        url = KANOON_DOC_URL.format(doc_id=doc_id)

        # Full text — try content div, then body
        content = (
            soup.find("div", id="content")
            or soup.find("div", class_=re.compile(r"content|main|article", re.I))
            or soup.find("article")
            or soup.find("body")
        )
        text = _clean_text(content) if content else ""

        # Court
        court = None
        for pat in COURT_PATTERNS:
            m = pat.search(text)
            if m:
                court = m.group(1).strip()
                break

        # Date
        date = None
        for pat in DATE_PATTERNS:
            m = pat.search(text)
            if m:
                date = _normalize_date(m.group(1).strip())
                break

        # Bench
        bench = None
        for pat in BENCH_PATTERNS:
            m = pat.search(text)
            if m:
                bench = m.group(1).strip()
                break

        # Citations
        citations = []
        for pat in CITATION_PATTERNS:
            citations.extend(m.group() for m in pat.finditer(text))
        citations = sorted(set(citations))

        # Acts / Sections
        acts = []
        for pat in SECTION_PATTERNS:
            acts.extend(m.group().strip().rstrip(",") for m in pat.finditer(text))
        acts = sorted(set(acts))

        return JudgmentDetail(
            doc_id=doc_id,
            title=title,
            url=url,
            court=court,
            date=date,
            bench=bench,
            text=text,
            citations=citations,
            acts=acts,
        )

    # -- public API ------------------------------------------------------------

    async def search(
        self,
        query: str,
        court: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        Search Indian Kanoon and return parsed results.

        Uses cache first, then fixtures (if enabled), then live scraping.
        """
        # Build a cache key from the search params
        cache_key = (
            f"kanoon:search:{query}:{court}:{year_from}:{year_to}:{limit}"
        )

        # 1) Check cache
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            logger.info(f"Cache hit for search: {cache_key}")
            return [SearchResult(**r) for r in cached_results]

        # 2) Fixtures
        if self.use_fixtures:
            logger.info(f"Serving fixture search for query='{query}'")
            results = await self._fixture_search(query, limit)
            cache.set(cache_key, [r.model_dump() for r in results], ttl=CACHE_TTL_SECONDS)
            return results

        # 3) Live search
        params = {"formInput": query, "order": "date"}
        if court:
            params["court"] = court
        if year_from:
            params["minYear"] = year_from
        if year_to:
            params["maxYear"] = year_to

        logger.info(f"Live search on Kanoon: query='{query}', params={params}")
        await self._delay()

        client = await self._get_client()
        try:
            resp = await client.get(KANOON_SEARCH_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(f"Kanoon search failed: {exc}")
            raise HTTPException(
                status_code=502,
                detail=f"Unable to reach Indian Kanoon: {exc}. "
                       "Try USE_FIXTURES=true for offline mode.",
            )

        results = self._parse_search_results(resp.text, limit)
        logger.info(f"Parsed {len(results)} search results for query='{query}'")

        # Cache the raw dicts
        cache.set(cache_key, [r.model_dump() for r in results], ttl=CACHE_TTL_SECONDS)
        return results

    async def get_judgment(self, doc_id: str) -> JudgmentDetail:
        """
        Fetch and parse a full judgment page.

        Uses cache first, then fixtures (if enabled), then live scraping.
        """
        cache_key = f"kanoon:doc:{doc_id}"

        # 1) Check cache
        cached_detail = cache.get(cache_key)
        if cached_detail is not None:
            logger.info(f"Cache hit for doc: {doc_id}")
            return JudgmentDetail(**cached_detail)

        # 2) Fixtures
        if self.use_fixtures:
            logger.info(f"Serving fixture detail for doc_id={doc_id}")
            detail = await self._fixture_detail(doc_id)
            if detail is not None:
                cache.set(cache_key, detail.model_dump(), ttl=CACHE_TTL_SECONDS)
                return detail
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found in fixtures.",
            )

        # 3) Live fetch
        url = KANOON_DOC_URL.format(doc_id=doc_id)
        logger.info(f"Fetching judgment from {url}")
        await self._delay()

        html = await self._fetch_html(url)
        if html is None:
            raise HTTPException(
                status_code=502,
                detail=f"Unable to fetch judgment {doc_id} from Indian Kanoon. "
                       "Try USE_FIXTURES=true for offline mode.",
            )

        detail = self._parse_judgment_detail(html, doc_id)
        logger.info(
            f"Parsed judgment: doc_id={doc_id}, title='{detail.title}', "
            f"court={detail.court}, citations={len(detail.citations)}, "
            f"acts={len(detail.acts)}"
        )

        cache.set(cache_key, detail.model_dump(), ttl=CACHE_TTL_SECONDS)
        return detail


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

kanoon_service = KanoonService()
