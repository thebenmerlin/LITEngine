"""
Outcome-label extraction for the judicial-outcome training dataset.

Indian appellate judgments almost always state their disposal in a
formulaic way near the very end of the text — "the appeal is allowed",
"the appeal is dismissed", "the appeal is partly allowed" — often
preceded by "In the result," / "In view of the above,". This module
looks for that operative language and returns a label with a confidence
score and the matched snippet, rather than ever forcing a guess.

Labels: "allowed" | "dismissed" | "partly_allowed" | "unclear"
"unclear" covers both "no disposal language found" and "conflicting
disposal language found" (e.g. a batch judgment disposing of multiple
appeals differently) — both are genuinely ambiguous for a single-label
row and are left for manual review rather than guessed.
"""

import re
from typing import List, Optional, Pattern

# Order matters at the call site: "partly allowed" is checked before the
# plain "allowed" patterns, since "allowed" is a substring of "partly
# allowed" and would otherwise always win.

_DISPOSAL_SUBJECT = r"(?:appeals?|petitions?|revisions?|writ\s+petitions?|slps?|special\s+leave\s+petitions?)"
_DISPOSAL_VERB = r"(?:is|are|stands?|stand)"
# Active-voice disposal: "we (hereby/therefore/accordingly) dismiss/allow
# the appeal(s)", as distinct from the passive "the appeal is dismissed".
_ACTIVE_SUBJECT = r"(?:we|this\s+court|the\s+court)"
_ACTIVE_ADVERBS = r"(?:hereby\s+|therefore\s+|accordingly\s+)*"

# NOTE: the gap patterns use plain "." (any char) rather than "[^.]" —
# case captions routinely contain periods as abbreviations ("Appeal No.
# 45 of 2019 is dismissed"), and by the time text reaches this module it
# has already been whitespace-collapsed to a single line (see
# kanoon.py's _clean_text), so a period no longer reliably marks a real
# sentence boundary either way. The tight character caps below do the
# actual work of keeping matches local to one clause.
PARTLY_ALLOWED_PATTERNS: List[Pattern] = [
    re.compile(
        rf"\b{_DISPOSAL_SUBJECT}\b.{{0,50}}?\b{_DISPOSAL_VERB}\b.{{0,20}}?\bpartl?y\s+allowed\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{_ACTIVE_SUBJECT}\b\s+{_ACTIVE_ADVERBS}partl?y\s+allow\b",
        re.IGNORECASE,
    ),
    re.compile(r"\ballowed\s+in\s+part\b", re.IGNORECASE),
    re.compile(r"\bpartially\s+allowed\b", re.IGNORECASE),
    re.compile(r"\bpartly\s+allowed\b", re.IGNORECASE),
    re.compile(r"\ballowed\s+to\s+the\s+extent\s+(?:indicated|mentioned|stated)\b", re.IGNORECASE),
]

DISMISSED_PATTERNS: List[Pattern] = [
    re.compile(
        rf"\b{_DISPOSAL_SUBJECT}\b.{{0,50}}?\b{_DISPOSAL_VERB}\b.{{0,20}}?\bdismissed\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{_ACTIVE_SUBJECT}\b\s+{_ACTIVE_ADVERBS}dismiss\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bappeal\s+(?:accordingly\s+)?fails?\b", re.IGNORECASE),
    re.compile(r"\bdismissed\s+accordingly\b", re.IGNORECASE),
    re.compile(r"\bfind\s+no\s+merit\b.{0,60}?\bdismissed\b", re.IGNORECASE),
    # "Rule" here is the Rule Nisi issued on admission of a petition/
    # revision — discharging it means the petition is rejected. A
    # distinct idiom from "appeal is dismissed", common in older
    # Gujarat/Bombay High Court judgments.
    re.compile(r"\brule\s+(?:is\s+)?(?:hereby\s+)?discharged\b", re.IGNORECASE),
]

ALLOWED_PATTERNS: List[Pattern] = [
    re.compile(
        rf"\b{_DISPOSAL_SUBJECT}\b.{{0,50}}?\b{_DISPOSAL_VERB}\b.{{0,20}}?\ballowed\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{_ACTIVE_SUBJECT}\b\s+{_ACTIVE_ADVERBS}allow\b",
        re.IGNORECASE,
    ),
    re.compile(r"\ballowed\s+accordingly\b", re.IGNORECASE),
    re.compile(r"\bappeal\s+(?:accordingly\s+)?succeeds?\b", re.IGNORECASE),
    # Rule Nisi made absolute = the petition/revision is granted.
    re.compile(r"\brule\s+(?:is\s+)?(?:hereby\s+)?made\s+absolute\b", re.IGNORECASE),
]

# Confidence tiers by distance (in characters) from the end of the
# judgment text — operative orders are almost always the very last thing
# in the document, so a match far from the end is less trustworthy (it
# may be describing a lower court's order, or a submission, rather than
# this court's own disposal).
_TIER_1_CHARS = 800    # near-certain: right at the end of the document
_TIER_2_CHARS = 2500   # likely: still within the closing paragraphs
_CONFIDENCE_TIER_1 = 0.9
_CONFIDENCE_TIER_2 = 0.75
_CONFIDENCE_TIER_3 = 0.5  # match found, but far from the end of the text
_CONFIDENCE_CONFLICT = 0.3
_CONFIDENCE_NONE = 0.0
# How far from the end a match can be and still plausibly compete as a
# rival disposal signal (see the conflict-candidacy filter below).
_CONFLICT_CANDIDACY_CHARS = 10000

SNIPPET_CONTEXT_CHARS = 200

# A single Kanoon doc_id can be a judgment disposing of several appeals
# together (e.g. co-accused tried jointly), each with its own outcome —
# "Appeal No. 197 of 1982 is partly allowed... Appeal No. 198 of 1982
# dismissed." A clean single-pattern match in that situation is real, but
# describes only ONE of the appeals; labeling the whole document with it
# is an oversimplification. Detect >1 distinct appeal/petition numbers
# near the end of the text and cap confidence accordingly.
_APPEAL_NUMBER_RE = re.compile(
    r"\b(?:crl\.?\s*)?(?:appeal|petition|revision)\s+no\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)
_MULTI_APPEAL_WINDOW_CHARS = 4000
_CONFIDENCE_MULTI_APPEAL_CAP = 0.4


def _has_multiple_appeal_numbers(text: str) -> bool:
    window = text[-_MULTI_APPEAL_WINDOW_CHARS:]
    numbers = {m.groups() for m in _APPEAL_NUMBER_RE.finditer(window)}
    return len(numbers) > 1


# --- False-positive exclusion filters ---------------------------------------
#
# A raw pattern match on "appeal ... is dismissed"-shaped text can still be
# the WRONG thing to key off of. Found by auditing the 0.4-0.6 confidence
# band against known-bad examples (case_id 1646937, 42135575, 26694354,
# 5420603, 126952627 among others): negated statutory boilerplate
# ("appeal... is NOT dismissed summarily" — quoting CrPC s.384/385's
# procedure, not a disposal), hypothetical/conditional framing ("if, and
# when, the appeal ... is allowed"), interim relief being mistaken for the
# final disposal ("application for suspension of sentence ... is allowed"),
# and abstract legal-principle statements about SLP dismissals in general
# ("when a petition seeking leave to appeal is dismissed, it is an
# expression of opinion that...") rather than this case's own outcome.
#
# Each checks a window AROUND the candidate match span — not just before
# match.start() — since the outcome keyword (dismissed/allowed) sits at
# the END of the matched span, and that's what negation/conditionals
# actually attach to.

_EXCLUSION_LOOKBACK_CHARS = 90
_EXCLUSION_LOOKAHEAD_CHARS = 20
# Safety cap on how far back a clause can extend when no boundary is
# found (shouldn't normally bind — the clause-boundary search below does
# the real work).
_CLOSE_LOOKBACK_MAX_CHARS = 150
# Text reaching this module is whitespace-collapsed (see kanoon.py's
# _clean_text), so real sentence-ending periods are indistinguishable
# from abbreviation periods ("No.") by punctuation alone. But a period
# followed by a capital letter or a digit (numbered paragraphs like
# "21. The appeal...") is a reasonable proxy for "starts a new clause" —
# good enough to stop negation/conditional/tense checks from bleeding
# into an entirely unrelated preceding sentence.
_CLAUSE_BOUNDARY_RE = re.compile(r"[.;]\s+(?=[A-Z0-9])")

_NEGATION_RE = re.compile(r"\b(?:not|never|cannot|can\s+not|no\s+longer)\b", re.IGNORECASE)
_CONDITIONAL_RE = re.compile(
    r"\b(?:if|when|unless|should|could|would|may|in\s+the\s+event(?:\s+of)?|in\s+case)\b",
    re.IGNORECASE,
)
_PAST_TENSE_RE = re.compile(r"\b(?:was|were)\b", re.IGNORECASE)
_INTERIM_RELIEF_RE = re.compile(
    r"\b(?:suspension\s+of\s+sentence|stay\s+(?:of|application)|interim\s+(?:relief|order|application)|"
    r"bail\s+application|application\s+for\s+(?:suspension|stay|bail|interim)|"
    r"during\s+(?:the\s+)?pendency|pending\s+disposal)\b",
    re.IGNORECASE,
)
_SLP_PRINCIPLE_RE = re.compile(
    r"\b(?:petition|slp|special\s+leave\s+petition)\s+seeking\s+(?:grant\s+of\s+)?leave\s+to\s+appeal\s+is\s+dismissed\b",
    re.IGNORECASE,
)
_PROCEDURAL_BOILERPLATE_RE = re.compile(
    r"\bsection\s+38[45]\b|\bsummarily\s+dismissed\b",
    re.IGNORECASE,
)


_CLOSE_WINDOW_CHARS = 35


def _current_clause_before(text: str, start: int) -> str:
    """Text from the nearest preceding clause boundary up to `start`,
    so negation/conditional/tense checks don't bleed into an unrelated
    earlier sentence that merely happens to sit within a fixed char
    window. The subject...verb...outcome gap patterns are loose enough
    that match.start() itself can land in an unrelated earlier clause
    (the "subject" half of the match), so on top of the clause boundary
    this is also capped to the last _CLOSE_WINDOW_CHARS — negation/
    conditional/tense words need to be *close* to what they're modifying,
    not just technically in the same run-on sentence."""
    window_start = max(0, start - _CLOSE_LOOKBACK_MAX_CHARS)
    window = text[window_start:start]
    boundaries = list(_CLAUSE_BOUNDARY_RE.finditer(window))
    clause = window[boundaries[-1].end():] if boundaries else window
    return clause[-_CLOSE_WINDOW_CHARS:]


# Negation needs its own much tighter, match-end-anchored window: the
# subject...verb...outcome gap patterns are loose enough that the match
# can legitimately contain an unrelated "not" earlier in a compound
# sentence — "we do NOT find any merit in these appeals which are
# dismissed" negates "merit", not "dismissed"; "appeal is NOT
# maintainable ... and is hereby dismissed" negates "maintainable", not
# "dismissed". Only a "not"/"never" immediately adjacent to the outcome
# word itself ("is NOT dismissed") should exclude the match.
_NEGATION_WINDOW_CHARS = 20


def _is_excluded_context(text: str, start: int, end: int) -> bool:
    clause_before = _current_clause_before(text, start)
    negation_window = text[max(0, end - _NEGATION_WINDOW_CHARS):end]
    window = text[max(0, start - _EXCLUSION_LOOKBACK_CHARS):min(len(text), end + _EXCLUSION_LOOKAHEAD_CHARS)]

    if _NEGATION_RE.search(negation_window):
        return True
    if _CONDITIONAL_RE.search(clause_before):
        return True
    if _PAST_TENSE_RE.search(clause_before):
        return True
    if _INTERIM_RELIEF_RE.search(window):
        return True
    if _SLP_PRINCIPLE_RE.search(window):
        return True
    if _PROCEDURAL_BOILERPLATE_RE.search(window):
        return True
    return False


def _best_match(patterns: List[Pattern], text: str):
    """Return the match (across all patterns) closest to the end of text,
    skipping any candidate whose surrounding context looks like negation,
    a hypothetical, an interim order, or other non-disposal language."""
    candidates = []
    for pat in patterns:
        for m in pat.finditer(text):
            candidates.append(m)
    candidates.sort(key=lambda m: m.start(), reverse=True)
    for m in candidates:
        if not _is_excluded_context(text, m.start(), m.end()):
            return m
    return None


def extract_outcome_label(text: str) -> dict:
    """
    Classify a judgment's disposal from its full text.

    Returns:
        {
            "label": "allowed" | "dismissed" | "partly_allowed" | "unclear",
            "confidence": float in [0, 1],
            "snippet": str,          # evidence text around the matched phrase
            "match_start": Optional[int],  # char offset of the match, for
                                            # truncating feature-extraction
                                            # input before this point
        }
    """
    if not text or not text.strip():
        return {"label": "unclear", "confidence": _CONFIDENCE_NONE, "snippet": "", "match_start": None}

    partly_m = _best_match(PARTLY_ALLOWED_PATTERNS, text)
    dismissed_m = _best_match(DISMISSED_PATTERNS, text)
    allowed_m = _best_match(ALLOWED_PATTERNS, text)

    # A match deep in case background/history (e.g. a prior interim
    # order mentioned near the start of a long judgment) shouldn't be
    # treated as competing against one that's actually near the end —
    # it's very unlikely to be this court's own operative order. Drop it
    # from conflict consideration if it's well beyond the "closing
    # paragraphs" zone while the other candidate is right there.
    if dismissed_m is not None and allowed_m is not None:
        dismissed_dist = len(text) - dismissed_m.end()
        allowed_dist = len(text) - allowed_m.end()
        if dismissed_dist > _CONFLICT_CANDIDACY_CHARS and allowed_dist <= _CONFLICT_CANDIDACY_CHARS:
            dismissed_m = None
        elif allowed_dist > _CONFLICT_CANDIDACY_CHARS and dismissed_dist <= _CONFLICT_CANDIDACY_CHARS:
            allowed_m = None

    conflict = False
    if partly_m is not None:
        label = "partly_allowed"
        match = partly_m
    elif dismissed_m is not None and allowed_m is not None:
        # Both a "dismissed" and a plain "allowed" disposal phrase were
        # found with no partly-allowed wording tying them together — most
        # likely a batch judgment disposing of multiple appeals
        # differently. Genuinely ambiguous for a single-label row.
        label = "unclear"
        conflict = True
        match = dismissed_m if dismissed_m.start() > allowed_m.start() else allowed_m
    elif dismissed_m is not None:
        label = "dismissed"
        match = dismissed_m
    elif allowed_m is not None:
        label = "allowed"
        match = allowed_m
    else:
        return {"label": "unclear", "confidence": _CONFIDENCE_NONE, "snippet": "", "match_start": None}

    distance_from_end = len(text) - match.end()
    if conflict:
        confidence = _CONFIDENCE_CONFLICT
    elif distance_from_end <= _TIER_1_CHARS:
        confidence = _CONFIDENCE_TIER_1
    elif distance_from_end <= _TIER_2_CHARS:
        confidence = _CONFIDENCE_TIER_2
    else:
        confidence = _CONFIDENCE_TIER_3

    if not conflict and _has_multiple_appeal_numbers(text):
        # Multiple distinct appeal numbers near the disposal — likely a
        # batch judgment where different appeals got different outcomes.
        # The matched label may only describe one of them.
        confidence = min(confidence, _CONFIDENCE_MULTI_APPEAL_CAP)

    start = max(0, match.start() - SNIPPET_CONTEXT_CHARS)
    end = min(len(text), match.end() + SNIPPET_CONTEXT_CHARS)
    snippet = text[start:end].strip()

    return {
        "label": label,
        "confidence": round(confidence, 2),
        "snippet": snippet,
        "match_start": match.start(),
    }
