"""Validated intake and frozen split for pre-decision outcome experiments.

The manifest points only to material created before the appeal was decided.
Judgments are used by a reviewer to verify the outcome, never as feature text.
"""

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List


CLASSES = ("dismissed", "succeeds")
APPELLANT_TYPES = ("accused_appeal", "state_appeal", "unclear")
REQUIRED_COLUMNS = {
    "case_id", "matter_id", "text_path", "filing_date", "decision_date",
    "court", "appellant_type", "outcome", "input_verified", "outcome_verified",
}
OUTCOME_CUES = re.compile(
    r"\b(?:this|the|instant|present)\s+appeal\s+(?:is|stands|was)\s+"
    r"(?:allowed|dismissed|partly\s+allowed)\b|\bappeal\s+is\s+accordingly\s+allowed\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FilingCase:
    case_id: str
    matter_id: str
    text_path: Path
    filing_date: date
    decision_date: date
    court: str
    appellant_type: str
    outcome: str
    text_hash: str
    outcome_cue_found: bool


def _true(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def load_manifest(path: Path) -> List[FilingCase]:
    path = path.resolve()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Manifest missing columns: {sorted(missing)}")
        raw_rows = list(reader)

    cases = []
    seen_ids = set()
    seen_text = {}
    for line, row in enumerate(raw_rows, start=2):
        case_id = row["case_id"].strip()
        matter_id = row["matter_id"].strip()
        if not case_id or not matter_id or case_id in seen_ids:
            raise ValueError(f"Line {line}: missing or duplicate case_id/matter_id")
        seen_ids.add(case_id)
        if not _true(row["input_verified"]) or not _true(row["outcome_verified"]):
            raise ValueError(f"Line {line}: verified input provenance and outcome are required")
        filing_date = date.fromisoformat(row["filing_date"].strip())
        decision_date = date.fromisoformat(row["decision_date"].strip())
        if decision_date <= filing_date:
            raise ValueError(f"Line {line}: decision_date must follow filing_date")
        outcome = row["outcome"].strip()
        appellant_type = row["appellant_type"].strip()
        if outcome not in CLASSES or appellant_type not in APPELLANT_TYPES:
            raise ValueError(f"Line {line}: invalid outcome or appellant_type")
        text_path = (path.parent / row["text_path"].strip()).resolve()
        if not text_path.is_relative_to(path.parent) or not text_path.is_file():
            raise ValueError(f"Line {line}: text_path must name a file under {path.parent}")
        text = text_path.read_text(encoding="utf-8").strip()
        if len(text.split()) < 50:
            raise ValueError(f"Line {line}: pre-decision text has fewer than 50 words")
        normalized = " ".join(text.lower().split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if digest in seen_text:
            raise ValueError(f"Line {line}: exact text duplicate of {seen_text[digest]}")
        seen_text[digest] = case_id
        cases.append(FilingCase(
            case_id, matter_id, text_path, filing_date, decision_date,
            row["court"].strip(), appellant_type, outcome, digest,
            bool(OUTCOME_CUES.search(text)),
        ))
    return cases


def freeze_split(cases: List[FilingCase], path: Path, seed: int = 42) -> dict:
    """Freeze matter-grouped holdout IDs once; never redraw an existing split."""
    if path.exists():
        split = json.loads(path.read_text(encoding="utf-8"))
        known = {case.case_id for case in cases}
        if set(split["train_ids"] + split["holdout_ids"]) != known:
            raise ValueError("Frozen split differs from manifest; create a new dataset version")
        return split

    by_matter = defaultdict(list)
    for case in cases:
        by_matter[case.matter_id].append(case)
    groups = list(by_matter.values())
    groups.sort(key=lambda group: hashlib.sha256(f"{seed}:{group[0].matter_id}".encode()).hexdigest())
    holdout = []
    train = []
    holdout_counts = Counter()
    for group in groups:
        group_counts = Counter(case.outcome for case in group)
        if len(holdout) < 100 or any(holdout_counts[c] < 30 and group_counts[c] for c in CLASSES):
            holdout.extend(group)
            holdout_counts.update(group_counts)
        else:
            train.extend(group)
    if len(cases) < 300 or len(train) < 200 or len(holdout) < 100 or any(holdout_counts[c] < 30 for c in CLASSES):
        raise ValueError(
            f"Insufficient data: total={len(cases)}, train={len(train)}, "
            f"holdout={len(holdout)}, holdout_classes={dict(holdout_counts)}; "
            "need >=300 total, >=200 train, >=100 holdout and >=30 per class"
        )
    split = {
        "version": 1,
        "seed": seed,
        "train_ids": sorted(case.case_id for case in train),
        "holdout_ids": sorted(case.case_id for case in holdout),
        "holdout_class_counts": dict(holdout_counts),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, indent=2), encoding="utf-8")
    return split
