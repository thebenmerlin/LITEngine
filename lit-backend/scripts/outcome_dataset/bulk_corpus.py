"""
Local access to Dattam Labs' public AWS Open Data buckets
(`indian-supreme-court-judgments`, `indian-high-court-judgments`;
CC-BY-4.0, no AWS credentials required) — replaces live, rate-limited
Kanoon search as the mechanism for resolving an SC judgment's cited HC
case into actual judgment text.

The HC bucket's `title` field is structured as "{TYPE}/{NUMBER}/{YEAR} of
{PARTY1} Vs {PARTY2}" (confirmed across Delhi/Karnataka/Bombay/Madras
partitions) — case-number+year gives an EXACT local lookup, no fuzzy
search or verification-by-guessing needed. `hc_court_registry.json` (built
once from a real partition listing, see its own generation note) maps
this project's HC_FAMILIES labels to the bucket's (court_code, bench)
partition keys.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_CACHE_DIR = REPO_ROOT / "data" / "bulk_corpus"
SC_BUCKET = "indian-supreme-court-judgments"
HC_BUCKET = "indian-high-court-judgments"
REGISTRY_PATH = Path(__file__).resolve().parent / "hc_court_registry.json"

HC_TITLE_RE = re.compile(r"^\s*[A-Za-z.\-]+/(\d+)/(\d{4})\s+of\s+", re.IGNORECASE)

# A case can take several years from filing to decision; this is how far
# past the filing year the decision-year partition search will look when
# the citation's own "dated" recital didn't give an exact decision year.
DECISION_YEAR_SEARCH_SPAN = 8


def _run_aws(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["aws", "s3", *args, "--no-sign-request"], capture_output=True, text=True)


def _s3_cp(remote_key: str, local_path: Path) -> bool:
    if local_path.exists():
        return True
    local_path.parent.mkdir(parents=True, exist_ok=True)
    result = _run_aws(["cp", f"s3://{remote_key}", str(local_path)])
    return result.returncode == 0 and local_path.exists()


def _s3_ls_names(remote_prefix: str) -> List[str]:
    """List object keys' basenames under a prefix (works for both a
    'directory' prefix ending in / and a partial-filename prefix)."""
    result = _run_aws(["ls", f"s3://{remote_prefix}"])
    if result.returncode != 0:
        return []
    names = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and "PRE" not in parts:
            names.append(parts[-1])
    return names


_registry: Optional[Dict[str, List[Dict[str, str]]]] = None


def load_registry() -> Dict[str, List[Dict[str, str]]]:
    global _registry
    if _registry is None:
        _registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return _registry


# ---------------------------------------------------------------------
# Supreme Court side
# ---------------------------------------------------------------------

def sc_metadata_local_path(year: int) -> Path:
    return LOCAL_CACHE_DIR / "sc_metadata" / f"year={year}" / "metadata.parquet"


def sync_sc_metadata(year: int) -> Optional[Path]:
    path = sc_metadata_local_path(year)
    if path.exists():
        return path
    remote = f"{SC_BUCKET}/metadata/parquet/year={year}/metadata.parquet"
    return path if _s3_cp(remote, path) else None


def sc_pdf_dir(year: int) -> Path:
    return LOCAL_CACHE_DIR / "sc_pdf" / f"year={year}"


def sync_sc_pdfs(year: int) -> Optional[Path]:
    """Bulk-download + extract one year's English-language SC PDF tar.
    ~300-500MB/year; cheap and rate-limit-free compared to per-doc Kanoon
    fetches. Cached on disk — a no-op on repeat calls."""
    out_dir = sc_pdf_dir(year)
    marker = out_dir / ".extracted"
    if marker.exists():
        return out_dir
    tar_path = LOCAL_CACHE_DIR / "sc_pdf_tar" / f"{year}_english.tar"
    remote = f"{SC_BUCKET}/data/tar/year={year}/english/english.tar"
    if not _s3_cp(remote, tar_path):
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["tar", "-xf", str(tar_path), "-C", str(out_dir)], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    marker.write_text("done", encoding="utf-8")
    tar_path.unlink(missing_ok=True)  # extracted; no need to keep the tar
    return out_dir


def sc_pdf_text(year: int, path_field: str) -> Optional[str]:
    pdf_dir = sync_sc_pdfs(year)
    if pdf_dir is None:
        return None
    pdf_path = pdf_dir / f"{path_field}_EN.pdf"
    if not pdf_path.exists():
        return None
    result = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


# ---------------------------------------------------------------------
# High Court side
# ---------------------------------------------------------------------

def _hc_metadata_local_path(year: int, court_code: str, bench: str) -> Path:
    return LOCAL_CACHE_DIR / "hc_metadata" / f"year={year}" / f"court={court_code}" / f"bench={bench}" / "metadata.parquet"


def sync_hc_metadata(year: int, court_code: str, bench: str) -> Optional[Path]:
    path = _hc_metadata_local_path(year, court_code, bench)
    if path.exists():
        return path
    remote = f"{HC_BUCKET}/metadata/parquet/year={year}/court={court_code}/bench={bench}/metadata.parquet"
    return path if _s3_cp(remote, path) else None


_hc_index_cache: Dict[Path, Dict[Tuple[str, str], dict]] = {}


def _hc_index(path: Path) -> Dict[Tuple[str, str], dict]:
    if path in _hc_index_cache:
        return _hc_index_cache[path]
    index: Dict[Tuple[str, str], dict] = {}
    try:
        table = pq.read_table(path, columns=["title", "cnr", "decision_date"])
        titles = table.column("title").to_pylist()
        cnrs = table.column("cnr").to_pylist()
        dates = table.column("decision_date").to_pylist()
        for title, cnr, date in zip(titles, cnrs, dates):
            if not title:
                continue
            m = HC_TITLE_RE.match(title)
            if not m:
                continue
            key = (m.group(1), m.group(2))
            index.setdefault(key, {"cnr": cnr, "decision_date": date, "title": title})
    except Exception:
        pass
    _hc_index_cache[path] = index
    return index


def find_hc_candidates(family: str, number: str, case_year: str, decision_year_hint: Optional[int] = None) -> List[dict]:
    """Exact local lookup for HC cases an SC judgment might have cited.
    Case-type abbreviations collide across unrelated proceedings within
    the SAME bench (e.g. "CRA/88/2015" is both a Criminal Appeal and,
    elsewhere, a Civil Revision Application — confirmed against real data)
    and the number+year alone can't disambiguate that, so this returns
    EVERY structural number+year match in search-priority order — the
    caller must still verify each against the citing judgment's own text
    (verify_citation_in_text) before accepting one; a structural match
    here is a candidate, not a result. Tries `decision_year_hint` (from
    the citation's own "dated" recital — precise) across every bench for
    the family first, then widens to a filing-year-forward window."""
    entries = load_registry().get(family, [])
    if not entries:
        return []

    digit_match = re.match(r"\d+", number)
    primary_digits = digit_match.group(0) if digit_match else number
    filing_year = int(case_year)

    candidate_years: List[int] = []
    if decision_year_hint:
        candidate_years.append(decision_year_hint)
    for y in range(filing_year, filing_year + DECISION_YEAR_SEARCH_SPAN):
        if y not in candidate_years:
            candidate_years.append(y)

    candidates: List[dict] = []
    for decision_year in candidate_years:
        for entry in entries:
            path = sync_hc_metadata(decision_year, entry["court_code"], entry["bench"])
            if path is None:
                continue
            row = _hc_index(path).get((primary_digits, case_year))
            if row is None:
                continue
            candidates.append({
                **row,
                "court_code": entry["court_code"],
                "bench": entry["bench"],
                "decision_year_partition": decision_year,
            })
    return candidates


def fetch_hc_pdf_text(court_code: str, bench: str, decision_year_partition: int, cnr: str) -> Optional[str]:
    remote_dir = f"{HC_BUCKET}/data/pdf/year={decision_year_partition}/court={court_code}/bench={bench}"
    names = [n for n in _s3_ls_names(f"{remote_dir}/{cnr}") if n.startswith(cnr)]
    if not names:
        return None
    # A CNR can have more than one listed order (interim + final); the
    # largest PDF is the most likely to be the substantive final judgment
    # rather than a short procedural order.
    sizes = {}
    for line in _run_aws(["ls", f"s3://{remote_dir}/{cnr}"]).stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            try:
                sizes[parts[-1]] = int(parts[2])
            except ValueError:
                pass
    chosen = max(names, key=lambda n: sizes.get(n, 0)) if sizes else names[0]

    local_path = LOCAL_CACHE_DIR / "hc_pdf" / f"year={decision_year_partition}" / f"court={court_code}" / f"bench={bench}" / chosen
    if not _s3_cp(f"{remote_dir}/{chosen}", local_path):
        return None
    result = subprocess.run(["pdftotext", "-layout", str(local_path), "-"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None
