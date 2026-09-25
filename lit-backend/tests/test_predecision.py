import tempfile
import unittest
import csv
import json
from datetime import date
from pathlib import Path

from scripts.outcome_dataset.predecision_data import FilingCase, freeze_split, load_manifest
from scripts.outcome_dataset.prepare_precedent_corpus import stage
from services.precedent_filter import decision_before


class PredecisionIntakeTests(unittest.TestCase):
    def test_manifest_requires_verified_predecision_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "case.txt").write_text("The appellant challenges the trial finding. " * 20, encoding="utf-8")
            manifest = root / "filings.csv"
            header = "case_id,matter_id,text_path,filing_date,decision_date,court,appellant_type,outcome,input_verified,outcome_verified\n"
            row = "one,matter-one,case.txt,2020-01-01,2021-01-01,High Court,accused_appeal,succeeds,false,true\n"
            manifest.write_text(header + row, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "verified input provenance"):
                load_manifest(manifest)
            manifest.write_text(header + row.replace("false,true", "true,true"), encoding="utf-8")
            self.assertEqual(load_manifest(manifest)[0].outcome, "succeeds")

    def test_frozen_split_keeps_matters_together_and_meets_gate(self):
        cases = []
        for i in range(320):
            cases.append(FilingCase(
                case_id=f"case-{i}", matter_id=f"matter-{i // 2}",
                text_path=Path("unused"), filing_date=date(2020, 1, 1),
                decision_date=date(2021, 1, 1), court="High Court",
                appellant_type="accused_appeal",
                outcome="succeeds" if i % 4 == 0 else "dismissed",
                text_hash=str(i), outcome_cue_found=False,
            ))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "split.json"
            split = freeze_split(cases, path)
            train_matters = {cases[int(cid.split("-")[1])].matter_id for cid in split["train_ids"]}
            held_matters = {cases[int(cid.split("-")[1])].matter_id for cid in split["holdout_ids"]}
            self.assertFalse(train_matters & held_matters)
            self.assertGreaterEqual(len(split["holdout_ids"]), 100)
            self.assertGreaterEqual(len(split["train_ids"]), 200)
            self.assertEqual(split, freeze_split(cases, path))

    def test_temporal_filter_rejects_unknown_and_same_day(self):
        cutoff = date(2020, 6, 1)
        self.assertTrue(decision_before("2020-05-31", cutoff))
        self.assertFalse(decision_before("2020-06-01", cutoff))
        self.assertFalse(decision_before("2020-06-02", cutoff))
        self.assertFalse(decision_before(None, cutoff))
        self.assertFalse(decision_before("not-a-date", cutoff))

    def test_cached_judgments_stage_only_dated_unique_precedents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            cache.mkdir()
            text = "The appellate court considered the record and arguments. " * 20
            for doc_id, date_value in (("1", "2020-01-01"), ("2", "2020-01-01"), ("3", None)):
                (cache / f"{doc_id}.json").write_text(json.dumps({
                    "doc_id": doc_id, "date": date_value, "title": f"Case {doc_id}",
                    "court": "Supreme Court of India", "text": text,
                    "url": f"https://indiankanoon.org/doc/{doc_id}/",
                }), encoding="utf-8")
            output = root / "precedents"
            summary = stage(cache, output)
            self.assertEqual(summary["valid_dated"], 2)
            self.assertEqual(summary["indexed_judgments"], 1)
            self.assertEqual(summary["near_duplicate_rows_removed"], 1)
            with (output / "precedents.csv").open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["doc_id"], "1")
            self.assertEqual(row["decision_date"], "2020-01-01")
            with self.assertRaisesRegex(ValueError, "not empty"):
                stage(cache, output)


if __name__ == "__main__":
    unittest.main()
