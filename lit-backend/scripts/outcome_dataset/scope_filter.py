"""
Scope filter — confirms each collected case is actually a criminal
appeal (or a closely-adjacent proceeding: criminal revision, reference
trial), rather than a Writ Petition/Writ Appeal on unrelated subject
matter that the "criminal appeal"-flavored search queries swept in
incidentally.

Signals are read from the case CAPTION region (the first ~2000 chars of
the judgment text — where Indian court judgments state the proceeding
type and number, e.g. "CRIMINAL APPEAL NO(S). ... OF 2026" or
"WRIT PETITION NO.14327 OF 2021") rather than keyword-anywhere-in-text
matching, since e.g. "writ petition" or "criminal appeal" can legitimately
be *mentioned* deep in a judgment's discussion without being what this
document itself is.

Three outcomes per case:
  - in scope (no flag)
  - hard-excluded: clearly a Writ Petition/Writ Appeal on unrelated
    subject matter (service disputes, PILs, policy writs) with no
    criminal-appeal signal in the caption at all
  - borderline_scope: mixed signals, or a writ captioned proceeding with
    a criminal-adjacent corroborating signal (premature release/
    remission writ appeals, tax-prosecution matters invoking CrPC
    appeal provisions) — left for manual review rather than auto-decided
"""

import re
from typing import NamedTuple, Optional

CAPTION_REGION_CHARS = 2000

CRIMINAL_SIGNAL_RE = re.compile(
    r"\b(?:"
    # "Crl.A. No.123", "Crl.A.Nos.158, 159", "Crl.A.(SJ) No...",
    # "CRIMINAL APPEAL NO(S). OF 2026"
    r"crl?\.?\s*a(?:ppeal)?\.?(?:\s*\([a-z]{1,4}\))?\.?\s*nos?\b|"
    r"criminal\s+appeal\.?(?:\s*\([a-z]{1,4}\))?\s*nos?\b|"
    r"crl?\.?\s*a\.?\s+\d+|"  # "Crl. A. 05 OF 2019" — abbreviation directly followed by the number, no "No." token at all
    r"cra[\-\s]|"  # CRA-AS-59-2022 style (Punjab & Haryana HC)
    r"crm[\-\s]?a[\-\s]|"  # CRM-A-... = Criminal Misc. Appeal
    r"crl?\.?\s*rev(?:ision)?\.?\s*(?:petition\s+)?nos?\b|criminal\s+revision\s+(?:petition\s+)?nos?\b|"
    r"crl?\.?\s*ref(?:erence)?\.?\s*nos?\b|criminal\s+reference\s+nos?\b|"
    r"r\.?t\.?\s*no\.?\s*\d|reference\s+trial\s+no|"
    r"crl?\.?\s*m\.?p\.?\s*nos?\b|criminal\s+misc(?:ellaneous)?\s+petition\s+nos?\b|"
    r"slp\s*\(crl?\.?\)|special\s+leave\s+petition\s*\(crl"
    r")\b",
    re.IGNORECASE,
)

WRIT_SIGNAL_RE = re.compile(
    r"\b(?:w\.?p\.?\s*(?:\(crl?\.?\))?\s*no|writ\s+petition\s+no|w\.?a\.?\s*no|writ\s+appeal\s+no)\b",
    re.IGNORECASE,
)

# Corroborating signals that a writ-captioned proceeding is still
# criminal-adjacent enough to warrant a human decision rather than a
# hard exclude. Deliberately narrow — generic mentions like "criminal
# prosecution" or "prosecution under" show up constantly as background
# narrative in otherwise-unrelated writs (e.g. a service-dispute writ
# petitioner who happens to also face an unrelated criminal case), so
# only specific procedural phrases that indicate THIS proceeding is
# about a criminal-adjacent remedy are used.
BORDERLINE_CORROBORATION_RE = re.compile(
    r"\b(?:premature\s+release|remission\s+of\s+sentence|grant\s+of\s+pardon|"
    r"exercise\s+of\s+clemency|"
    r"section\s+432\s+(?:of\s+)?(?:the\s+)?(?:cr\.?p\.?c|code\s+of\s+criminal\s+procedure)|"
    r"section\s+433\s+(?:of\s+)?(?:the\s+)?(?:cr\.?p\.?c|code\s+of\s+criminal\s+procedure)|"
    r"writ\s+of\s+habeas\s+corpus|"
    r"quash(?:ing)?\s+(?:of\s+)?(?:the\s+)?(?:fir|complaint|charge\s*sheet)"
    r")\b",
    re.IGNORECASE,
)


class ScopeResult(NamedTuple):
    hard_exclude: bool
    borderline_scope: bool
    reason: str


def classify_scope(text: str) -> ScopeResult:
    caption = text[:CAPTION_REGION_CHARS]

    has_criminal = bool(CRIMINAL_SIGNAL_RE.search(caption))
    has_writ = bool(WRIT_SIGNAL_RE.search(caption))

    if has_criminal and not has_writ:
        return ScopeResult(False, False, "criminal appeal/revision/reference signal in caption")

    if has_writ and not has_criminal:
        # Writ-captioned with no criminal signal at all — check for
        # criminal-adjacent corroboration anywhere in the full text
        # before deciding hard-exclude vs borderline.
        if BORDERLINE_CORROBORATION_RE.search(text):
            return ScopeResult(False, True, "writ caption, but criminal-adjacent corroboration found (e.g. remission/quashing/habeas corpus)")
        return ScopeResult(True, False, "writ caption with no criminal-appeal signal — likely unrelated subject matter")

    if has_criminal and has_writ:
        # Mixed signals — e.g. a Writ Appeal referencing an underlying
        # criminal proceeding, or the case caption lists both a writ and
        # a connected criminal number. Genuinely ambiguous.
        return ScopeResult(False, True, "both criminal and writ signals present in caption")

    # Neither signal found — could be an older/differently-formatted
    # judgment (e.g. some pre-2000 SC judgments don't state a case-type
    # header at all), not necessarily out of scope. Don't guess either
    # way with a hard exclude; leave unflagged but note nothing was
    # found, rather than silently assuming "in scope" is 100% certain.
    return ScopeResult(False, False, "no explicit case-type signal found in caption — leaving unflagged")
