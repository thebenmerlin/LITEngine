"""
Appellant-type classification — is this a STATE-side appeal (state or a
private complainant appealing an acquittal — bad for the originally
acquitted person if allowed) or an ACCUSED-side appeal (the convicted
person appealing their own conviction — good for them if allowed)?

Needed because "allowed" means opposite things depending on who filed:
State's appeal against an acquittal being allowed is bad for the accused;
the accused's own appeal against a conviction being allowed is good for
them. Without this, "allowed"/"dismissed" alone can't be interpreted
consistently across rows.

Two signal sources, combined with a tiered confidence score (same design
as labeling.py) rather than ever forcing a guess:
  1. Case caption — which party is named first (appellant/petitioner
     side): "State Of X vs Y" vs "Y vs State Of X"/"Y vs Z".
  2. Textual corroboration — Section 378 CrPC (or the BNSS equivalent,
     Section 419) governs appeals against acquittal, almost always filed
     by the State or a complainant with leave; Section 374 CrPC (or BNSS
     equivalent, Section 415) governs appeals against conviction, filed
     by the convicted person.

Private-complainant appeals against an acquittal are bucketed as
"state_appeal" too — not because a complainant literally is the state,
but because the polarity is the same one this column exists to capture:
does "allowed" favor the prosecution side or the originally-convicted/
accused side.
"""

import re
from typing import NamedTuple, Optional

CAPTION_SCAN_CHARS = 150  # title is short; only need the "X vs Y" span

STATE_PARTY_RE = re.compile(
    r"^(?:the\s+)?(?:"
    r"state\s+of\b|union\s+of\s+india\b|union\s+territory\b|u\.?t\.?\s+of\b|state\b|"
    r"govt\.?\s+of\b|government\s+of\b|.{0,30}?\badministration\b|"
    # Union Territories are routinely named as a caption party without a
    # "State of"/"UT of" prefix at all.
    r"nct\s+of\s+delhi\b|dadra\s+and\s+nagar\s+haveli\b|daman\s+and\s+diu\b|"
    r"puducherry\b|pondicherry\b|andaman\s+and\s+nicobar\b|lakshadweep\b|"
    r"jammu\s+and\s+kashmir\b|union\s+territory\s+of\b"
    r")",
    re.IGNORECASE,
)

VS_SPLIT_RE = re.compile(r"\s+(?:vs\.?|versus)\s+", re.IGNORECASE)
TITLE_DATE_SUFFIX_RE = re.compile(r"\s+on\s+\d{1,2}\s+\w+,?\s+\d{4}\s*$", re.IGNORECASE)

SECTION_378_RE = re.compile(
    r"\bsection\s+378\b|\bs\.?\s*378\s+cr\.?p\.?c|\bsection\s+419\s+bnss\b",
    re.IGNORECASE,
)
SECTION_374_RE = re.compile(
    r"\bsection\s+374\b|\bs\.?\s*374\s+cr\.?p\.?c|\bsection\s+415\s+bnss\b",
    re.IGNORECASE,
)
LEAVE_TO_APPEAL_RE = re.compile(r"\bleave\s+to\s+appeal\b", re.IGNORECASE)
ACQUITTAL_APPEAL_RE = re.compile(r"\bappeal\s+against\s+(?:the\s+)?acquittal\b|\bappeal\s+against\s+acquittal\b", re.IGNORECASE)
CONVICTION_APPEAL_RE = re.compile(r"\bappeal\s+against\s+(?:the\s+)?conviction\b", re.IGNORECASE)
COMPLAINANT_ACQUITTAL_RE = re.compile(r"\bcomplainant\b.{0,80}?\bacquittal\b|\bacquittal\b.{0,80}?\bcomplainant\b", re.IGNORECASE)


class AppellantTypeResult(NamedTuple):
    appellant_type: str  # "state_appeal" | "accused_appeal" | "unclear"
    confidence: float


def _caption_signal(title: str) -> Optional[str]:
    """Return 'state_first' | 'individual_first' | None from the case
    caption's "X vs Y" party order."""
    clean_title = TITLE_DATE_SUFFIX_RE.sub("", title or "").strip()
    parts = VS_SPLIT_RE.split(clean_title, maxsplit=1)
    if len(parts) != 2:
        return None
    first_party = parts[0].strip()
    second_party = parts[1].strip()

    first_is_state = bool(STATE_PARTY_RE.search(first_party))
    second_is_state = bool(STATE_PARTY_RE.search(second_party))

    if first_is_state and not second_is_state:
        return "state_first"
    if second_is_state and not first_is_state:
        return "individual_first"
    return None  # both or neither look like State — ambiguous


def classify_appellant_type(title: str, text: str) -> AppellantTypeResult:
    caption = _caption_signal(title)

    has_378 = bool(SECTION_378_RE.search(text))
    has_374 = bool(SECTION_374_RE.search(text))
    has_leave = bool(LEAVE_TO_APPEAL_RE.search(text))
    has_acquittal_appeal = bool(ACQUITTAL_APPEAL_RE.search(text))
    has_conviction_appeal = bool(CONVICTION_APPEAL_RE.search(text))
    has_complainant_acquittal = bool(COMPLAINANT_ACQUITTAL_RE.search(text))

    state_signal = has_378 or has_acquittal_appeal or has_complainant_acquittal
    accused_signal = has_374 or has_conviction_appeal

    # Both textual signals present — genuinely ambiguous (could be a
    # batch judgment with both a State appeal against one accused's
    # acquittal AND another accused's own appeal against conviction).
    if state_signal and accused_signal:
        return AppellantTypeResult("unclear", 0.3)

    if caption == "state_first":
        if state_signal:
            return AppellantTypeResult("state_appeal", 0.9)
        if accused_signal:
            # Caption says State-first but the only statutory signal is
            # conviction-appeal — contradictory, don't guess.
            return AppellantTypeResult("unclear", 0.3)
        return AppellantTypeResult("state_appeal", 0.6)

    if caption == "individual_first":
        if accused_signal:
            return AppellantTypeResult("accused_appeal", 0.9)
        if state_signal:
            return AppellantTypeResult("unclear", 0.3)
        return AppellantTypeResult("accused_appeal", 0.6)

    # No usable caption signal (both parties individuals/organizations,
    # or title didn't parse) — fall back to the statutory signal alone,
    # at reduced confidence since it's not corroborated by the caption.
    if state_signal and not accused_signal:
        conf = 0.6 if has_leave or has_complainant_acquittal else 0.5
        return AppellantTypeResult("state_appeal", conf)
    if accused_signal and not state_signal:
        return AppellantTypeResult("accused_appeal", 0.5)

    return AppellantTypeResult("unclear", 0.0)
