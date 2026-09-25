"""
Extract the impugned (lower-court) judgment citation from a Supreme Court
criminal-appeal judgment's own text.

This is the linchpin of the "lower-court-judgment-as-case-text" predecision
design: for an SC criminal appeal, the High Court judgment it is appealing
genuinely existed before the SC's decision and is not the decision being
predicted, so it can legitimately serve as pre-decision case text once
independently located and verified — never guessed or synthesized.

Two things must be found near each other in the SC judgment's own text:
  1. the High Court's identity ("High Court of X" / "X High Court"), and
  2. a Criminal Appeal/Revision/Reference number + year that belongs to
     THAT High Court proceeding (not the SC's own SLP/appeal number, which
     is deliberately excluded from the number pattern below).

Returns None rather than guessing when either signal is missing or when
multiple distinct HC citations conflict (batch judgments citing several
different HC matters) — the caller should skip such cases, not force a
match.
"""

import re
from datetime import date
from typing import NamedTuple, Optional, Tuple

SEARCH_WINDOW_CHARS = 20000  # impugned-judgment recitals are always in the
                              # opening paragraphs/headnote, never deep in
                              # the reasoning — widened to comfortably cover
                              # official Supreme Court Reports' long
                              # editorial headnotes before the recital

# Family keyword -> canonical label used both for candidate filtering
# against raw_cache's `court` field and for building the live search query.
HC_FAMILIES = {
    "gujarat": "Gujarat",
    "bombay": "Bombay", "maharashtra": "Bombay", "goa": "Bombay",
    "madras": "Madras", "tamil nadu": "Madras", "pondicherry": "Madras",
    "punjab": "Punjab-Haryana", "haryana": "Punjab-Haryana", "chandigarh": "Punjab-Haryana",
    "madhya pradesh": "Madhya Pradesh",
    "allahabad": "Allahabad", "uttar pradesh": "Allahabad",
    "karnataka": "Karnataka",
    "andhra pradesh": "Andhra Pradesh", "telangana": "Andhra Pradesh",
    "patna": "Patna", "bihar": "Patna",
    "jharkhand": "Jharkhand",
    "delhi": "Delhi",
    "kerala": "Kerala",
    "chhattisgarh": "Chattisgarh", "chattisgarh": "Chattisgarh",
    "himachal pradesh": "Himachal Pradesh",
    "jammu": "Jammu & Kashmir", "kashmir": "Jammu & Kashmir",
    "calcutta": "Calcutta", "west bengal": "Calcutta",
    "gauhati": "Gauhati", "assam": "Gauhati",
    "orissa": "Orissa", "odisha": "Orissa",
    "rajasthan": "Rajasthan",
    "tripura": "Tripura",
    "uttarakhand": "Uttarakhand", "uttaranchal": "Uttarakhand",
    "sikkim": "Sikkim",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "nagaland": "Nagaland",
}
# Longest keys first so "andhra pradesh" matches before a hypothetical
# shorter overlapping key would.
_FAMILY_KEYS_BY_LEN = sorted(HC_FAMILIES, key=len, reverse=True)

_HC_NAME_PATTERNS = [
    re.compile(r"\bHigh\s+Court\s+of\s+(?:Judicature\s+(?:at|of)\s+)?([A-Z][A-Za-z]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z]+)?(?:\s+[A-Z][A-Za-z]+)?)\b"),
    re.compile(r"\b([A-Z][A-Za-z]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z]+)?(?:\s+[A-Z][A-Za-z]+)?)\s+High\s+Court\b"),
]

# Deliberately excludes "SLP"/"Special Leave Petition"/plain "Appeal No."
# (the SC's own number) — only case-types that are exclusively High-Court-
# or-below proceedings. Covers both Kanoon-scraped-judgment phrasing
# (Crl.A./Criminal Revision/Criminal Reference) and official Supreme Court
# Reports phrasing, which favors compact registry abbreviations (CRLAP,
# CONFC = Criminal Confirmation Case, SC No. = Sessions Case) in a
# "CRIMINAL APPELLATE JURISDICTION ... From the Judgment and Order dated
# ... in CRLAP No.X of Y" recital.
_CASE_NO_RE = re.compile(
    r"\b(?:criminal\s+appeal|crl\.?\s*a(?:ppeal)?\.?|crlap|cra|crr|"
    r"criminal\s+revision(?:\s+petition)?|crl\.?\s*rev(?:ision)?\.?(?:\s*petition)?|"
    r"criminal\s+reference|crl\.?\s*ref(?:erence)?\.?|confc|sc)\s*\.?\s*nos?\.?\s*[:\-]?\s*"
    r"(\d+(?:[\-/][A-Za-z0-9]+)?(?:[\-,]\s*\d+(?:[\-/][A-Za-z0-9]+)?)*)\s*(?:of|/)\s*(\d{4})",
    re.IGNORECASE,
)

_DATED_RE = re.compile(
    r"\b(?:dated|on)\s+(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+\w+,?\s+\d{4})",
    re.IGNORECASE,
)

_PROXIMITY_CHARS = 320
_DATE_PROXIMITY_CHARS = 150


class ImpugnedCitation(NamedTuple):
    hc_family: str          # canonical label, e.g. "Bombay"
    hc_name_raw: str        # exact text matched, e.g. "Bombay High Court"
    case_number: str        # e.g. "1746-SB"
    case_year: str          # e.g. "2005"
    dated_raw: Optional[str]


def _family_for(name_text: str) -> Optional[str]:
    lowered = name_text.lower()
    for key in _FAMILY_KEYS_BY_LEN:
        if key in lowered:
            return HC_FAMILIES[key]
    return None


def extract_impugned_citation(text: str, own_case_number_year: Optional[Tuple[str, str]] = None) -> Optional[ImpugnedCitation]:
    """Find a single, unambiguous HC-name + case-number pairing near each
    other in the opening portion of an SC judgment. Returns None if no HC
    name is found, no case number is found nearby, or more than one
    distinct (family, number, year) triple is found (batch/ambiguous).

    `own_case_number_year`: the SC's OWN (digits, year) docket number, when
    known from a structured source (e.g. the bulk corpus's own "Case No"
    metadata field) — excluded from candidacy wherever it appears. Some
    judgments restate the SC's own number a second time right next to "of
    the High Court" without ever giving the HC's own number in a findable
    spot (confirmed against real data: "CRIMINAL APPELLATE JURISDICTION:
    Criminal Appeal No.1617 of 2023. From the Judgment and Order dated
    23.05.2022 of the High Court" — no HC case number at all here), so
    relying only on "drop the first occurrence" isn't enough when the true
    number is available to check against directly."""
    window = text[:SEARCH_WINDOW_CHARS]

    name_hits = []
    for pattern in _HC_NAME_PATTERNS:
        for m in pattern.finditer(window):
            family = _family_for(m.group(1))
            if family:
                name_hits.append((m.start(), m.end(), family, m.group(0)))

    if not name_hits:
        return None

    number_hits = [(m.start(), m.end(), m.group(1), m.group(2)) for m in _CASE_NO_RE.finditer(window)]
    if not number_hits:
        return None

    if own_case_number_year:
        own_digits, own_year = own_case_number_year
        number_hits = [h for h in number_hits if not (_primary_digits(h[2]) == own_digits and h[3] == own_year)]
        if not number_hits:
            return None

    # The SC's OWN docket number is always the first case-number-shaped
    # match in the document — it sits in the cause title/header, which
    # precedes any recital of the judgment under appeal in both
    # Kanoon-scraped judgments and official Supreme Court Reports text.
    # Drop it so it never gets paired with an HC name. If only one number
    # was found at all, there's nothing left to safely pair — don't guess
    # whether it's the SC's own number or genuinely the HC's.
    number_hits.sort(key=lambda h: h[0])
    number_hits = number_hits[1:]
    if not number_hits:
        return None

    # Collect every valid (family, number, year) pairing with its gap.
    # Deliberately permissive about MULTIPLE numbers pairing with the same
    # family — Indian HC judgments routinely carry companion case numbers
    # for one proceeding (e.g. a death-sentence "Criminal Reference"
    # decided together with the convict's own "Criminal Appeal"), which
    # isn't the kind of ambiguity worth rejecting on. What *is* rejected is
    # numbers pairing with more than one distinct HC family nearby (a
    # batch judgment genuinely citing different HC matters) — final
    # correctness is enforced downstream by verifying the chosen number
    # literally appears in the located HC judgment's own caption, not by
    # being maximally conservative here.
    #
    # Distance is symmetric (not directional): Kanoon-scraped judgments
    # tend to state the HC's name BEFORE its case number ("passed by the
    # High Court of X ... in Criminal Appeal No. Y of Z"), while official
    # Supreme Court Reports recitals do the reverse ("...in CRLAP No.88 of
    # 2015 ... of the High Court of Judicature at Bombay") — sometimes
    # listing several companion numbers before ever naming the court.
    pairings = []  # (gap, family, raw_name, number, year, span_start, span_end)
    for n_start, n_end, family, raw_name in name_hits:
        for c_start, c_end, number, year in number_hits:
            gap = max(0, max(n_start, c_start) - min(n_end, c_end))
            if gap <= _PROXIMITY_CHARS:
                pairings.append((gap, family, raw_name, number.strip(), year, min(n_start, c_start), max(n_end, c_end)))

    if not pairings:
        return None

    families_involved = {p[1] for p in pairings}
    if len(families_involved) != 1:
        return None

    gap, family, raw_name, number, year, span_start, span_end = min(pairings, key=lambda p: p[0])
    dated_match = None
    date_search_start = max(0, span_start - _DATE_PROXIMITY_CHARS)
    date_search_end = min(len(window), span_end + _DATE_PROXIMITY_CHARS)
    dm = _DATED_RE.search(window[date_search_start:date_search_end])
    if dm:
        dated_match = dm.group(1)
    return ImpugnedCitation(family, raw_name, number, year, dated_match)


def _primary_digits(number: str) -> str:
    """Leading digit run of a case number, ignoring suffixes like
    "-SB"/"/2" or a leading item in a "428-430" range — e.g. "1746-SB" ->
    "1746", "428-430" -> "428"."""
    m = re.match(r"\d+", number)
    return m.group(0) if m else number


def court_matches_family(court_field: str, family: str) -> bool:
    """True if a raw_cache-style `court` string plausibly belongs to the
    named HC family (e.g. "Punjab-Haryana High Court" for family
    "Punjab-Haryana", "Andhra Pradesh High Court - Amravati" for family
    "Andhra Pradesh")."""
    if not court_field:
        return False
    lowered = court_field.lower()
    for token in re.split(r"[\s\-]+", family.lower()):
        if len(token) > 2 and token in lowered:
            return True
    return False


_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_ORDINAL_SUFFIX_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_NUMERIC_DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")
_TEXT_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})")


def parse_loose_date(raw: Optional[str]) -> Optional[date]:
    """Parse either an ISO YYYY-MM-DD (what Kanoon's own normalized search
    results/judgment dates use) or the free-form day-first 'dated ...'
    strings extracted alongside a citation (DD.MM.YYYY, DD/MM/YYYY,
    DD-MM-YYYY, or 'DD Month, YYYY', optionally with an ordinal suffix)
    into a date, or None if unparseable."""
    if not raw:
        return None
    cleaned = _ORDINAL_SUFFIX_RE.sub(r"\1", raw).strip()
    m = _ISO_DATE_RE.match(cleaned)
    if m:
        y, mo, d = m.groups()
        try:
            return date(int(y), int(mo), int(d))
        except ValueError:
            return None
    m = _NUMERIC_DATE_RE.match(cleaned)
    if m:
        d, mo, y = m.groups()
        year = int(y)
        if year < 100:
            year += 2000 if year < 50 else 1900
        try:
            return date(year, int(mo), int(d))
        except ValueError:
            return None
    m = _TEXT_DATE_RE.match(cleaned)
    if m:
        d, month_name, y = m.groups()
        month = _MONTHS.get(month_name.lower())
        if month:
            try:
                return date(int(y), month, int(d))
            except ValueError:
                return None
    return None


def verify_citation_in_text(candidate_text: str, citation: ImpugnedCitation) -> bool:
    """Confirm the extracted case number+year literally appears (as the
    candidate document's OWN case number, not merely mentioned somewhere)
    near the top of a candidate HC judgment's text. This is the actual
    correctness gate for a match — extraction only proposes a candidate,
    this proves it."""
    caption = candidate_text[:3000]
    expected_digits = _primary_digits(citation.case_number)
    for m in _CASE_NO_RE.finditer(caption):
        if _primary_digits(m.group(1)) == expected_digits and m.group(2) == citation.case_year:
            return True
    return False
