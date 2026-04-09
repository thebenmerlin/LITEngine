"""
Case Fact Extraction Service — InLegalBERT + rule-based fallback.

Extracts structured legal elements from raw case text:
  • Parties (petitioner / respondent)
  • Legal issues
  • IPC / CrPC / CPC / Evidence Act sections
  • Acts referenced
  • Court level
  • Case type (criminal / civil / constitutional / tax / labour / other)
  • Key facts (bullet-point)
  • Relief sought

Primary: HF Inference API → law-ai/InLegalBERT
Fallback: regex-based rule extraction (always runs for IPC sections)
"""

import asyncio
import re
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import get_settings
from models.schemas import (
    ExtractionMetadata,
    Parties,
    StructuredCaseProfile,
    TaskStatus,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HF_INFLEGALBERT_URL = (
    "https://api-inference.huggingface.co/models/law-ai/InLegalBERT"
)

# NER entity group → schema field mapping
ENTITY_MAP: Dict[str, str] = {
    "LAW": "sections",
    "LAW_ACT": "acts",
    "ACT": "acts",
    "COURT": "court",
    "ORG": "acts",
    "PERSON": "parties",
    "PETITIONER": "petitioner",
    "RESPONDENT": "respondent",
    "JUDGE": "bench",
    "DATE": "dates",
    "ISSUE": "legal_issues",
    "PROVISION": "sections",
    "STATUTE": "acts",
    "RELIEF": "relief",
    "CASE_TYPE": "case_type",
}

# Confidence threshold below which we consider model results unreliable
MODEL_CONFIDENCE_THRESHOLD = 0.5

# Max retries for HF API calls
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5.0  # InLegalBERT is larger — longer backoff

# Valid case types
VALID_CASE_TYPES = {"criminal", "civil", "constitutional", "tax", "labour", "other"}

# ---------------------------------------------------------------------------
# In-memory task store for async extraction
# ---------------------------------------------------------------------------

_task_store: Dict[str, TaskStatus] = {}


def get_task(task_id: str) -> Optional[TaskStatus]:
    """Retrieve a task by ID."""
    return _task_store.get(task_id)


def create_task() -> Tuple[str, TaskStatus]:
    """Create a new pending task and store it."""
    task_id = uuid.uuid4().hex[:12]
    task = TaskStatus(
        task_id=task_id,
        status="pending",
        created_at=datetime.utcnow(),
    )
    _task_store[task_id] = task
    return task_id, task


def update_task(task_id: str, **kwargs) -> TaskStatus:
    """Update a task's fields."""
    task = _task_store.get(task_id)
    if task is None:
        raise KeyError(f"Task {task_id} not found")
    for key, value in kwargs.items():
        setattr(task, key, value)
    return task


def cleanup_old_tasks(max_age_seconds: int = 300) -> int:
    """Remove tasks older than max_age_seconds. Returns count removed."""
    now = datetime.utcnow()
    to_delete = [
        tid for tid, t in _task_store.items()
        if (now - t.created_at).total_seconds() > max_age_seconds
    ]
    for tid in to_delete:
        del _task_store[tid]
    return len(to_delete)


# ---------------------------------------------------------------------------
# Rule-based extractors
# ---------------------------------------------------------------------------

# --- IPC / CrPC / CPC / Evidence Act sections ---

IPC_SECTION_RE = re.compile(
    r"(?:Section|Sec\.?|u/?s\.?|under)\s+"
    r"(\d+[A-Za-z]?(?:\s*[,&/]\s*\d+[A-Za-z]?)*)"
    r"(?:\s*(?:IPC|CrPC|CPC|IEA|Evidence Act|Code))?",
    re.IGNORECASE,
)

IPC_SECTION_INLINE = re.compile(
    r"(\d{2,3})\s*(?:IPC|CrPC|CPC)",
    re.IGNORECASE,
)

# --- Acts ---

ACT_RE = re.compile(
    r"((?:Indian\s+(?:Penal\s+Code|Evidence\s+Act|Succession\s+Act|Contract\s+Act|"
    r"Stamp\s+Act|Trusts\s+Act|Partnership\s+Act|Arbitration\s*(?:and\s*)?Conciliation\s*Act)|"
    r"Code\s+of\s+(?:Criminal|Civil)\s+Procedure|"
    r"Constitution\s+of\s+India|"
    r"Companies\s+Act|"
    r"Information\s+Technology\s+Act|"
    r"National\s+Investigation\s+Agency\s*Act|"
    r"Prevention\s+of\s+Corruption\s+Act|"
    r"Prevention\s+of\s+Money\s+Laundering\s+Act|"
    r"Protection\s+of\s+Children\s+from\s+Sexual\s+Offences\s+Act|"
    r"(?:[\w\s]+?)\s+Act,\s*\d{4}))",
    re.IGNORECASE,
)

# --- Parties ---

PETITIONER_RE = re.compile(
    r"(?:petitioner|appellant|complainant|plaintiff)\s*[:=\-—]?\s*([^\n,]+?)"
    r"(?:\s+(?:versus|vs\.?|v\.|against|Respondent)|\s*$)",
    re.IGNORECASE,
)

RESPONDENT_RE = re.compile(
    r"(?:respondent|accused|defendant|reverspondent)\s*[:=\-—]?\s*([^\n,]+?)"
    r"(?:\s+(?:versus|vs\.?|v\.|against|Appellant|Petitioner)|\s*$)",
    re.IGNORECASE,
)

# The classic "X vs. Y" pattern — handles multi-line formatting
VS_PATTERN = re.compile(
    r"([A-Z][A-Za-z\s\.\,\&\-\—\@]+?)\s+(?:versus|vs\.?|v\.)\s+"
    r"([A-Z][A-Za-z\s\.\,\&\-\—\@]+?)"
    r"(?:\s+(?:CORAM|Date:|J\.|JJ\.|Bench|Hon|Order|FIR|Criminal|Civil|Writ|AIR|SCC|SCR)|\s*$)",
    re.DOTALL,
)

# --- Court ---

COURT_LEVEL_RE = re.compile(
    r"(Supreme Court of India|"
    r"Supreme Court|"
    r"(?:\w+\s+)?High Court of\s+\w+|"
    r"(?:\w+\s+)?High Court|"
    r"District Court|"
    r"District & Sessions Court|"
    r"Sessions Court|"
    r"Family Court|"
    r"Consumer\s+(?:Disputes\s+Redressal\s+)?Commission|"
    r"National\s+Green\s+Tribunal|"
    r"Central\s+Administrative\s+Tribunal|"
    r"NCLT|"
    r"NCLAT)",
    re.IGNORECASE,
)

# --- Case type keywords ---

CRIMINAL_KEYWORDS = re.compile(
    r"\b(criminal\s+(?:appeal|petition|writ|reference|review|"
    r"revision|complaint|case|prosecution|trial)|"
    r"FIR|chargesheet|charge\s+sheet|offence|accused|IPC|"
    r"bail|anticipatory\s+bail|cognizable|non[- ]bailable|"
    r"sessions\s+case|murder|rape|theft|cheating|"
    r"Section\s+302|Section\s+420|Section\s+307|"
    r"Section\s+376|Section\s+498A|Section\s+138)",
    re.IGNORECASE,
)

CIVIL_KEYWORDS = re.compile(
    r"\b(civil\s+(?:appeal|suit|petition|writ|revision)|"
    r"decree|injunction|specific\s+performance|"
    r"damages|partition|eviction|tenant|landlord|"
    r"property\s+dispute|title\s+suit)",
    re.IGNORECASE,
)

CONSTITUTIONAL_KEYWORDS = re.compile(
    r"\b(constitutional\s+(?:validity|challenge|bench)|"
    r"writ\s+petition|Article\s+32|Article\s+226|"
    r"Article\s+21|Article\s+14|Article\s+19|"
    r"fundamental\s+right|basic\s+structure|"
    r"judicial\s+review)",
    re.IGNORECASE,
)

TAX_KEYWORDS = re.compile(
    r"\b(income\s+tax|goods?\s+and\s+services?\s+tax|GST|"
    r"central\s+excise|customs\s+duty|tax\s+(?:appeal|tribunal)|"
    r"income\s+tax\s+appellate\s+tribunal|ITAT)",
    re.IGNORECASE,
)

LABOUR_KEYWORDS = re.compile(
    r"\b(labour\s+(?:court|dispute|tribunal)|"
    r"industrial\s+dispute|workman|employer|"
    r"termination\s+of\s+service|retrenchment|"
    r"minimum\s+wages?|employees['']?\s+provident\s+fund)",
    re.IGNORECASE,
)

# --- Key facts (sentence extraction) ---

SENTENCE_SPLITTER = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# --- Relief ---

RELIEF_RE = re.compile(
    r"(?:prayer|relief\s+sought|sought\s+relief|it\s+is\s+(?:hereby|respectfully)"
    r"\s+(?:prayed|submitted)|petitioner\s+prays|prays?\s+(?:that|for))"
    r"\s*[:.\-—]?\s*(.+?)(?:\n{2,}|Given\s+under|Dated\s*|Signature|$)",
    re.IGNORECASE | re.DOTALL,
)

# --- Legal issues ---

ISSUE_RE = re.compile(
    r"(?:issue|question|whether)\s+(?:is|arises|before\s+this\s+"
    r"(?:Court|bench))?\s*[:.\-—]?\s*(.+?)(?:\n{2,}|It\s+is|The\s+|Held\s*[:.])",
    re.IGNORECASE | re.DOTALL,
)


def _extract_sections_rules(text: str) -> List[str]:
    """Extract IPC/CrPC/CPC sections using regex (always reliable for statutes)."""
    sections: set[str] = set()

    # "Section 302 IPC", "u/s 420", "under Section 307"
    for m in IPC_SECTION_RE.finditer(text):
        section_text = m.group(0).strip().rstrip(",;.")
        # Normalize: collapse multi-section refs
        sections.add(section_text)

    # "302 IPC" (without "Section" prefix)
    for m in IPC_SECTION_INLINE.finditer(text):
        num = m.group(1)
        # Find what code follows
        start = m.end()
        remainder = text[start:start + 20].strip()
        code_match = re.match(r"(IPC|CrPC|CPC|IEA)", remainder, re.IGNORECASE)
        if code_match:
            sections.add(f"Section {num} {code_match.group(1)}")

    return sorted(sections)


def _extract_acts_rules(text: str) -> List[str]:
    """Extract Acts and statutes referenced."""
    acts: set[str] = set()
    for m in ACT_RE.finditer(text):
        act_name = m.group(1).strip().rstrip(",;.")
        # Normalize whitespace
        act_name = re.sub(r"\s+", " ", act_name)
        if len(act_name) > 4:  # filter noise
            acts.add(act_name)
    return sorted(acts)


def _extract_parties_rules(text: str) -> Parties:
    """Extract petitioner and respondent names."""
    petitioner = None
    respondent = None

    # "X vs. Y" pattern (most reliable)
    vs_match = VS_PATTERN.search(text)
    if vs_match:
        petitioner = vs_match.group(1).strip().rstrip(",;:")
        respondent = vs_match.group(2).strip().rstrip(",;:")

    # Explicit patterns
    if not petitioner:
        p_match = PETITIONER_RE.search(text)
        if p_match:
            petitioner = p_match.group(1).strip()

    if not respondent:
        r_match = RESPONDENT_RE.search(text)
        if r_match:
            respondent = r_match.group(1).strip()

    # Truncate long names
    if petitioner and len(petitioner) > 200:
        petitioner = petitioner[:200].rsplit(" ", 1)[0] + "..."
    if respondent and len(respondent) > 200:
        respondent = respondent[:200].rsplit(" ", 1)[0] + "..."

    return Parties(petitioner=petitioner, respondent=respondent)


def _extract_court_level_rules(text: str) -> str:
    """Detect court level from text."""
    m = COURT_LEVEL_RE.search(text)
    if m:
        court = m.group(1).strip()
        # Normalize
        court_lower = court.lower()
        if "supreme court" in court_lower:
            return "Supreme Court"
        if "high court" in court_lower:
            return "High Court"
        if "district" in court_lower or "sessions" in court_lower:
            return "District Court"
        if "tribunal" in court_lower or "nclt" in court_lower or "nclat" in court_lower:
            return "Tribunal"
        if "commission" in court_lower:
            return "Commission"
        if "family court" in court_lower:
            return "Family Court"
        return court
    return "Unknown"


def _extract_case_type_rules(text: str) -> str:
    """Classify case type based on keyword matching."""
    if CONSTITUTIONAL_KEYWORDS.search(text):
        return "constitutional"
    if CRIMINAL_KEYWORDS.search(text):
        return "criminal"
    if CIVIL_KEYWORDS.search(text):
        return "civil"
    if TAX_KEYWORDS.search(text):
        return "tax"
    if LABOUR_KEYWORDS.search(text):
        return "labour"
    return "other"


def _extract_key_facts(text: str, max_facts: int = 8) -> List[str]:
    """Extract key factual sentences from the text."""
    # Normalize: collapse newlines into spaces, then split on sentence boundaries
    normalized = re.sub(r"\s+", " ", text.strip())
    sentences = SENTENCE_SPLITTER.split(normalized)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20 and len(s.strip()) < 400]

    # Score sentences by presence of legally relevant signals
    scored: List[Tuple[float, str]] = []
    for s in sentences:
        score = 0.0
        s_lower = s.lower()
        # Factual signals
        if any(w in s_lower for w in ["deceased", "accused", "victim", "injured"]):
            score += 2.0
        if re.search(r"\b\d{1,2}\s*(?:AM|PM|a\.?m\.?|p\.?m\.?)\b", s, re.IGNORECASE):
            score += 1.5
        if re.search(r"\b(FIR|complaint|report|statement)\b", s, re.IGNORECASE):
            score += 1.0
        if re.search(r"\b(post.?mortem|medical|injury|weapon)\b", s, re.IGNORECASE):
            score += 1.0
        if re.search(r"\b(witness|testified|deposed|evidence)\b", s, re.IGNORECASE):
            score += 0.8
        # Penalize introductory / procedural sentences
        if re.search(r"\b(this\s+(?:appeal|petition|case)\s+(?:is|was|comes))\b", s, re.IGNORECASE):
            score -= 1.0

        scored.append((score, s))

    # Sort by score descending, take top max_facts
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [s for _, s in scored[:max_facts]]

    # Re-sort by original order to maintain narrative flow
    order = {s: i for i, s in enumerate(sentences)}
    selected.sort(key=lambda s: order.get(s, 999))

    return selected


def _extract_relief_rules(text: str) -> Optional[str]:
    """Extract the relief/prayer sought."""
    m = RELIEF_RE.search(text)
    if m:
        relief = m.group(1).strip()
        # Collapse to a single paragraph
        relief = re.sub(r"\s+", " ", relief)
        if len(relief) > 500:
            relief = relief[:500].rsplit(" ", 1)[0] + "..."
        return relief
    return None


def _extract_legal_issues_rules(text: str) -> List[str]:
    """Extract legal issues / questions framed in the text."""
    seen: set[str] = set()
    issues: List[str] = []

    def _add(text: str) -> bool:
        """Add if not already seen (normalized)."""
        norm = re.sub(r"\s+", " ", text.lower().strip())
        # Check for containment (avoid near-duplicates)
        for existing in seen:
            if norm in existing or existing in norm:
                # Keep the longer one
                if len(norm) > len(existing):
                    seen.discard(existing)
                    seen.add(norm)
                    issues.append(text)
                return False
        if norm not in seen:
            seen.add(norm)
            issues.append(text)
            return True
        return False

    # Pattern: "issue/question ... : ..."
    for m in ISSUE_RE.finditer(text):
        issue_text = m.group(1).strip()
        issue_text = re.sub(r"\s+", " ", issue_text)
        if 10 < len(issue_text) < 500:
            _add(issue_text)

    # Pattern: "Whether ...?" sentences
    whether_sentences = re.finditer(
        r"(Whether\s+.+?\?|[Tt]he\s+(?:main|principal|key)\s+(?:issue|question)\s+(?:is|was|arises)\s+(?:that\s+)?(.+?)(?:\n\n|\.+\s|Held))",
        text,
        re.DOTALL,
    )
    for m in whether_sentences:
        issue_text = (m.group(1) or m.group(2) or "").strip()
        issue_text = re.sub(r"\s+", " ", issue_text)
        if 10 < len(issue_text) < 500:
            _add(issue_text)

    return issues[:5]


def extract_rules_only(text: str) -> StructuredCaseProfile:
    """
    Pure rule-based extraction. Used as fallback when model is unavailable,
    and always merged for IPC sections regardless.
    """
    return StructuredCaseProfile(
        parties=_extract_parties_rules(text),
        legal_issues=_extract_legal_issues_rules(text),
        ipc_sections=_extract_sections_rules(text),
        acts_referenced=_extract_acts_rules(text),
        court_level=_extract_court_level_rules(text),
        case_type=_extract_case_type_rules(text),
        key_facts=_extract_key_facts(text),
        relief_sought=_extract_relief_rules(text),
    )


# ---------------------------------------------------------------------------
# HF Inference API — InLegalBERT
# ---------------------------------------------------------------------------


class _ExtractorService:
    """InLegalBERT-based case fact extractor with rule-based fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.HUGGINGFACE_API_KEY
        self._use_hf_api = bool(
            self.api_key and not self.api_key.startswith("hf_your_")
        )
        self._client: Optional[httpx.AsyncClient] = None

        if not self._use_hf_api:
            logger.warning(
                "No valid HUGGINGFACE_API_KEY — InLegalBERT model will be skipped; "
                "rule-based extraction only."
            )

    # -- HTTP client ------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "LIT-Backend/0.1",
                },
                timeout=45.0,  # InLegalBERT can be slow
            )
            logger.info("Created async httpx client for InLegalBERT")
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("Closed httpx client")

    # -- InLegalBERT API call --------------------------------------------------

    async def _call_inlegalbert(self, text: str, attempt: int = 1) -> Dict[str, Any]:
        """
        Call the InLegalBERT model via HF Inference API.

        Raises:
            RuntimeError: if all retries exhausted
            ModelLoadingError: if model is warming up (503) — caller should poll
        """
        payload = {"inputs": text}
        client = await self._get_client()

        try:
            resp = await client.post(HF_INFLEGALBERT_URL, json=payload)

            if resp.status_code == 503:
                wait = resp.headers.get("retry-after", "20")
                try:
                    wait_sec = float(wait)
                except (ValueError, TypeError):
                    wait_sec = 20.0
                raise ModelLoadingError(
                    f"InLegalBERT model is warming up. Retry after {wait_sec}s.",
                    retry_after=wait_sec,
                )

            if resp.status_code == 404:
                raise RuntimeError(
                    "InLegalBERT model not available on HF Inference API. "
                    "The model may not be deployed or may require a paid plan. "
                    "Falling back to rule-based extraction."
                )

            resp.raise_for_status()
            return resp.json()

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"Rate limited, backing off {delay}s (attempt {attempt}/{MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                return await self._call_inlegalbert(text, attempt + 1)
            raise RuntimeError(f"InLegalBERT API error: {exc}") from exc

        except httpx.RequestError as exc:
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"InLegalBERT request error: {exc}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
                return await self._call_inlegalbert(text, attempt + 1)
            raise RuntimeError(
                f"Failed to reach InLegalBERT API after {MAX_RETRIES} attempts: {exc}"
            ) from exc

    # -- Parse model output ----------------------------------------------------

    def _parse_ner_output(self, result: Any, text: str) -> Dict[str, Any]:
        """
        Parse InLegalBERT token-classification output into structured fields.

        HF token-classification API returns:
          [{"entity_group": "LAW", "word": "Section 302", "score": 0.95, ...}]
        """
        if not isinstance(result, list):
            return {}

        sections: set[str] = set()
        acts: set[str] = set()
        petitioner: Optional[str] = None
        respondent: Optional[str] = None
        legal_issues: List[str] = []
        court_raw: Optional[str] = None
        avg_score = 0.0
        score_count = 0

        for entity in result:
            if not isinstance(entity, dict):
                continue

            group = entity.get("entity_group", entity.get("entity", "")).upper()
            word = entity.get("word", entity.get("entity_str", "")).strip()
            score = entity.get("score", 0.0)

            if not word or len(word) < 2:
                continue

            avg_score += score
            score_count += 1

            # Map to fields
            if group in ("LAW", "PROVISION"):
                sections.add(word)
            elif group in ("ACT", "LAW_ACT", "STATUTE", "ORG"):
                acts.add(word)
            elif group in ("PETITIONER", "PERSON"):
                if petitioner is None and score > 0.3:
                    petitioner = word
            elif group in ("RESPONDENT",):
                if respondent is None and score > 0.3:
                    respondent = word
            elif group == "ISSUE":
                legal_issues.append(word)
            elif group == "COURT":
                court_raw = word
            elif group == "RELIEF":
                pass  # merged later
            elif group == "CASE_TYPE":
                pass  # validated later

        overall_confidence = avg_score / score_count if score_count > 0 else 0.0

        return {
            "sections": sorted(sections),
            "acts": sorted(acts),
            "petitioner": petitioner,
            "respondent": respondent,
            "legal_issues": legal_issues[:5],
            "court_raw": court_raw,
            "confidence": round(min(overall_confidence, 1.0), 4),
        }

    # -- Core extraction -------------------------------------------------------

    async def _extract_with_model(self, text: str) -> Tuple[StructuredCaseProfile, str, float]:
        """
        Extract using InLegalBERT model.

        Returns:
            (StructuredCaseProfile, extraction_method, confidence)
        """
        result = await self._call_inlegalbert(text)
        model_data = self._parse_ner_output(result, text)

        # Also run rules — we always merge for sections
        rules_profile = extract_rules_only(text)

        # Merge: model takes precedence, rules fill gaps
        # Sections: always prefer rules (regex is more reliable for statutes)
        ipc_sections = rules_profile.ipc_sections if rules_profile.ipc_sections else model_data.get("sections", [])
        if model_data.get("sections"):
            # Merge unique
            ipc_sections = sorted(set(ipc_sections) | set(model_data["sections"]))

        # Acts: merge both
        model_acts = set(model_data.get("acts", []))
        rule_acts = set(rules_profile.acts_referenced)
        acts_referenced = sorted(model_acts | rule_acts)

        # Parties: model first, rules as fallback
        parties = Parties(
            petitioner=model_data.get("petitioner") or rules_profile.parties.petitioner,
            respondent=model_data.get("respondent") or rules_profile.parties.respondent,
        )

        # Legal issues: prefer model, fallback to rules
        legal_issues = model_data.get("legal_issues", [])
        if not legal_issues:
            legal_issues = rules_profile.legal_issues

        # Court level: normalize model output, fallback to rules
        court_level = rules_profile.court_level
        court_raw = model_data.get("court_raw")
        if court_raw:
            # Try to match against known court levels
            cl = _extract_court_level_rules(court_raw)
            if cl != "Unknown":
                court_level = cl

        # Case type: prefer rules (keyword matching is more reliable)
        case_type = rules_profile.case_type

        # Key facts and relief: rules only (model doesn't typically extract these)
        key_facts = rules_profile.key_facts
        relief_sought = rules_profile.relief_sought

        # Determine method
        model_conf = model_data.get("confidence", 0.0)
        if model_conf >= MODEL_CONFIDENCE_THRESHOLD:
            method = "hybrid"
            confidence = round((model_conf + 0.7) / 2, 4)  # blend with rule confidence
        else:
            method = "rules"
            confidence = 0.6  # default for rules-only

        profile = StructuredCaseProfile(
            parties=parties,
            legal_issues=legal_issues,
            ipc_sections=ipc_sections,
            acts_referenced=acts_referenced,
            court_level=court_level,
            case_type=case_type,
            key_facts=key_facts,
            relief_sought=relief_sought,
        )

        return profile, method, confidence

    async def extract(
        self,
        case_text: str,
        use_model: bool = True,
    ) -> Tuple[StructuredCaseProfile, ExtractionMetadata]:
        """
        Extract structured case profile from raw text.

        Args:
            case_text: The raw case description / judgment text
            use_model: Whether to attempt InLegalBERT extraction

        Returns:
            (StructuredCaseProfile, ExtractionMetadata)
        """
        start_ms = int(time.time() * 1000)

        if not case_text.strip():
            profile = StructuredCaseProfile(parties=Parties())
            meta = ExtractionMetadata(
                extraction_method="rules",
                confidence=0.0,
                processing_time_ms=int(time.time() * 1000) - start_ms,
            )
            return profile, meta

        if use_model and self._use_hf_api:
            try:
                profile, method, confidence = await self._extract_with_model(case_text)
            except ModelLoadingError:
                # Model is warming up — caller should handle via task system
                raise
            except RuntimeError as exc:
                logger.warning(f"InLegalBERT failed, using rules: {exc}")
                profile = extract_rules_only(case_text)
                method = "rules"
                confidence = 0.5
        else:
            profile = extract_rules_only(case_text)
            method = "rules"
            confidence = 0.5

        elapsed = int(time.time() * 1000) - start_ms
        meta = ExtractionMetadata(
            extraction_method=method,
            confidence=confidence,
            processing_time_ms=elapsed,
        )

        logger.info(
            f"Extraction complete: method={method}, confidence={confidence:.4f}, "
            f"time={elapsed}ms, sections={len(profile.ipc_sections)}, "
            f"acts={len(profile.acts_referenced)}, facts={len(profile.key_facts)}"
        )

        return profile, meta

    async def extract_async(
        self,
        task_id: str,
        case_text: str,
        use_model: bool = True,
    ) -> None:
        """
        Run extraction in background and update task store.

        Designed for handling model cold start — returns 202 Accepted
        immediately, then processes in background.
        """
        update_task(task_id, status="processing")

        try:
            profile, meta = await self.extract(case_text, use_model=use_model)
            profile.metadata = meta
            update_task(task_id, status="completed", result=profile)
        except Exception as exc:
            logger.error(f"Async extraction failed for task {task_id}: {exc}")
            update_task(task_id, status="failed", error=str(exc))


class ModelLoadingError(Exception):
    """Raised when HF model is still loading (HTTP 503)."""

    def __init__(self, message: str, retry_after: float = 20.0):
        super().__init__(message)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

extractor_service = _ExtractorService()
