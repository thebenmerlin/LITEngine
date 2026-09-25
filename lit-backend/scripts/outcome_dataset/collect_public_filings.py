"""Download publicly posted petition PDFs into a provenance-first candidate corpus.

The output is deliberately not a training manifest. Filing dates, case links,
outcomes, and OCR must be checked against the source documents before a case
can be marked verified for the predecision experiment.
"""

import argparse
import csv
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from scripts.outcome_dataset.predecision_data import OUTCOME_CUES

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PAGES = 100
REQUIRED = {"case_id", "petition_url", "source_page_url", "claimed_filing_date"}


def download_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Petition URL must use HTTPS")
    if parsed.hostname in {"drive.google.com", "www.drive.google.com"}:
        match = re.fullmatch(r"/file/d/([A-Za-z0-9_-]+)(?:/.*)?", parsed.path)
        file_id = match.group(1) if match else parse_qs(parsed.query).get("id", [None])[0]
        if not file_id:
            raise ValueError("Google Drive URL must contain a file ID")
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def extract_pdf_text(pdf_path: Path) -> tuple[str, str, int]:
    info = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True)
    page_match = re.search(r"^Pages:\s+(\d+)$", info.stdout, re.MULTILINE)
    if not page_match:
        raise ValueError("PDF page count is unavailable")
    pages = int(page_match.group(1))
    if pages > MAX_PAGES:
        raise ValueError(f"PDF has {pages} pages; manual intake required")
    plain = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True, check=True).stdout
    if len(plain.split()) >= 50:
        return plain, "pdftotext", pages
    with tempfile.TemporaryDirectory() as temporary:
        prefix = Path(temporary) / "page"
        subprocess.run(["pdftoppm", "-r", "130", "-png", str(pdf_path), str(prefix)], check=True, capture_output=True)
        chunks = []
        for image in sorted(Path(temporary).glob("page-*.png")):
            result = subprocess.run(["tesseract", str(image), "stdout"], capture_output=True, text=True, check=True)
            chunks.append(result.stdout)
    return "\n\n".join(chunks), "tesseract", pages


def collect(seed_csv: Path, output_dir: Path) -> dict:
    with seed_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Seed CSV missing columns: {sorted(missing)}")
        seeds = list(reader)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "LITEngine research corpus/1.0"}) as client:
        for seed in seeds:
            case_id = seed["case_id"].strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
                raise ValueError(f"Unsafe case ID: {case_id!r}")
            case_dir = output_dir / case_id
            case_dir.mkdir(exist_ok=True)
            url = download_url(seed["petition_url"].strip())
            with client.stream("GET", url) as response:
                response.raise_for_status()
                pdf = bytearray()
                for chunk in response.iter_bytes():
                    pdf.extend(chunk)
                    if len(pdf) > MAX_PDF_BYTES:
                        raise ValueError(f"{case_id}: PDF exceeds {MAX_PDF_BYTES} bytes")
            if not pdf.startswith(b"%PDF-"):
                raise ValueError(f"{case_id}: response is not a PDF")
            pdf_path = case_dir / "petition.pdf"
            pdf_path.write_bytes(pdf)
            text, method, pages = extract_pdf_text(pdf_path)
            text_path = case_dir / "petition.txt"
            text_path.write_text(text, encoding="utf-8")
            record = {
                "case_id": case_id,
                "petition_url": seed["petition_url"].strip(),
                "source_page_url": seed["source_page_url"].strip(),
                "claimed_filing_date": seed["claimed_filing_date"].strip(),
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "pdf_path": str(pdf_path),
                "text_path": str(text_path),
                "pages": pages,
                "words": len(text.split()),
                "extraction_method": method,
                "outcome_cue_found": bool(OUTCOME_CUES.search(text)),
                "input_verified": False,
                "outcome_verified": False,
                "review_status": "candidate_only",
            }
            (case_dir / "provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            manifest.append(record)
    summary = {"candidates": len(manifest), "records": manifest}
    (output_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.seeds, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
