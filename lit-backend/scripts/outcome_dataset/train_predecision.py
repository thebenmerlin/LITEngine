"""Select a linear filing-based model without inspecting the frozen holdout.

Example: python -m scripts.outcome_dataset.train_predecision --data-dir data/outcome_dataset/predecision/v1
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, f1_score
from sklearn.model_selection import StratifiedGroupKFold

from scripts.outcome_dataset.build_predecision import FEATURE_KEYS
from services.calibrated_outcome import CalibratedOutcomeModel
from scripts.outcome_dataset.train_model import make_pipeline

FEATURE_ORDER = list(FEATURE_KEYS) + ["appellant_type"]


def load_features(data_dir: Path):
    split = json.loads((data_dir / "frozen_split.json").read_text(encoding="utf-8"))
    metadata = json.loads((data_dir / "feature_metadata.json").read_text(encoding="utf-8"))
    if metadata["feature_order"] != FEATURE_ORDER:
        raise ValueError("Feature metadata does not match model contract")
    with (data_dir / "features.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["case_id"]: row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != set(split["train_ids"] + split["holdout_ids"]):
        raise ValueError("Feature rows differ from frozen split")
    train_matters = {by_id[c]["matter_id"] for c in split["train_ids"]}
    holdout_matters = {by_id[c]["matter_id"] for c in split["holdout_ids"]}
    if train_matters & holdout_matters:
        raise ValueError("Related matters cross the frozen split")
    return rows, split, metadata


def frame(rows):
    X = np.empty((len(rows), len(FEATURE_ORDER)), dtype=object)
    for i, row in enumerate(rows):
        for j, key in enumerate(FEATURE_KEYS):
            value = float(row[key])
            if not 0 <= value <= 1:
                raise ValueError(f"{row['case_id']}: {key} outside [0, 1]")
            X[i, j] = value
        X[i, -1] = row["appellant_type"]
    y = np.array([row["outcome"] for row in rows])
    groups = np.array([row["matter_id"] for row in rows])
    return X, y, groups


def review_queue_hash(data_dir: Path, feature_rows):
    path = data_dir / "review_queue.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["case_id"]: row for row in feature_rows}
    if not rows or any(row["case_id"] not in by_id for row in rows):
        raise ValueError("Review queue is empty or contains unknown cases")
    reviewed_ids = {row["case_id"] for row in rows}
    if len(reviewed_ids) != len(rows):
        raise ValueError("Review queue contains duplicate cases")
    if any(sum(by_id[case_id]["split"] == split_name for case_id in reviewed_ids) < 25 for split_name in ("train", "holdout")):
        raise ValueError("Review queue needs at least 25 cases from each split")
    if any(row["outcome_cue_found"] == "True" and row["case_id"] not in reviewed_ids for row in feature_rows):
        raise ValueError("All outcome-cue flags must be reviewed")
    if any(row["reviewed"].strip().lower() not in ("yes", "true", "1") for row in rows):
        raise ValueError("Every queued case must be reviewed before training")
    if any(row["issue_found"].strip().lower() not in ("no", "false", "0") for row in rows):
        raise ValueError("Resolve review issues in a new dataset version before training")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train(data_dir: Path) -> Path:
    if (data_dir / "evaluation_report.json").exists():
        raise ValueError("Frozen holdout has been evaluated; use a new dataset version")
    rows, split, metadata = load_features(data_dir)
    audit_hash = review_queue_hash(data_dir, rows)
    train_ids = set(split["train_ids"])
    train_rows = [row for row in rows if row["case_id"] in train_ids]
    if len(train_rows) < 200 or len(split["holdout_ids"]) < 100:
        raise ValueError("Dataset does not meet frozen size gate")
    X, y, groups = frame(train_rows)
    if min(Counter(y).values()) < 5:
        raise ValueError("Training needs at least five examples per class")
    folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42).split(X, y, groups))
    candidates = []
    for C in (0.01, 0.1, 1.0, 10.0):
        for weight in (None, "balanced"):
            oof = np.empty(len(y), dtype=float)
            for train_idx, val_idx in folds:
                model = make_pipeline(C=C)
                model.set_params(clf__class_weight=weight)
                model.fit(X[train_idx], y[train_idx])
                oof[val_idx] = model.predict_proba(X[val_idx])[:, 1]
            pred = np.where(oof >= 0.5, "succeeds", "dismissed")
            candidates.append({
                "C": C, "class_weight": weight,
                "macro_f1": float(f1_score(y, pred, average="macro")),
                "brier": float(brier_score_loss(y == "succeeds", oof)),
                "oof": oof,
            })
    chosen = sorted(candidates, key=lambda item: (-item["macro_f1"], item["brier"], item["C"]))[0]
    calibrator = LogisticRegression(max_iter=2000)
    calibrator.fit(chosen["oof"].reshape(-1, 1), y == "succeeds")
    if calibrator.coef_[0, 0] <= 0:
        raise ValueError("Calibration would reverse the ranking; stop for review")
    model = make_pipeline(C=chosen["C"])
    model.set_params(clf__class_weight=chosen["class_weight"])
    model.fit(X, y)
    version = "filings-" + hashlib.sha256(
        (data_dir / "features.csv").read_bytes() +
        (data_dir / "frozen_split.json").read_bytes()
    ).hexdigest()[:12]
    artifact = CalibratedOutcomeModel(model, calibrator, FEATURE_ORDER, version, metadata["extraction_method"])
    artifact_path = data_dir / f"{version}.joblib"
    joblib.dump(artifact, artifact_path)
    report = {
        "version": version,
        "train_n": len(train_rows),
        "train_class_counts": dict(Counter(y)),
        "feature_metadata": metadata,
        "review_queue_sha256": audit_hash,
        "selected": {key: chosen[key] for key in ("C", "class_weight", "macro_f1", "brier")},
        "candidates": [{key: item[key] for key in ("C", "class_weight", "macro_f1", "brier")} for item in candidates],
        "holdout_evaluated": False,
    }
    (data_dir / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return artifact_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    print(train(args.data_dir))


if __name__ == "__main__":
    main()
