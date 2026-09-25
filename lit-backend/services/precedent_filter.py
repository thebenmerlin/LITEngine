"""Date checks shared by live and offline precedent retrieval."""

from datetime import date
from typing import Optional


def decision_before(value: Optional[str], cutoff: date) -> bool:
    """Unknown or malformed decision dates cannot establish temporal eligibility."""
    if not value:
        return False
    try:
        return date.fromisoformat(value[:10]) < cutoff
    except ValueError:
        return False
