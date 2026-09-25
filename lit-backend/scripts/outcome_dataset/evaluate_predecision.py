"""One-time, paired holdout comparison against the deployed binary model."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score, brier_score_loss, confusion_matrix, f1_score,
    precision_recall_fscore_support,
)

from scripts.outcome_dataset.train_predecision import frame, load_features, review_queue_hash
from services.outcome_model import DEFAULT_MODEL_PATH

CLASSES = ["dismissed", "succeeds"]


def metrics(y, p):
    pred = np.where(p >= 0.5, "succeeds", "dismissed")
    precision, recall, f1, support = precision_recall_fscore_support(
        y, pred, labels=CLASSES, zero_division=0,
    )
    calibration_error = 0.0
    for low in np.linspace(0, 1, 11)[:-1]:
        high = low + 0.1
        bucket = (p >= low) & (p < high if high < 1 else p <= high)
        if bucket.any():
            calibration_error += bucket.mean() * abs((y[bucket] == "succeeds").mean() - p[bucket].mean())
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "brier": float(brier_score_loss(y == "succeeds", p)),
        "ece_10_bins": float(calibration_error),
        "confusion_matrix": confusion_matrix(y, pred, labels=CLASSES).tolist(),
        "per_class": {
            cls: {
                "precision": float(precision[i]), "recall": float(recall[i]),
                "f1": float(f1[i]), "support": int(support[i]),
            } for i, cls in enumerate(CLASSES)
        },
    }


def paired_bootstrap_lower(y, candidate_p, incumbent_p, groups, n_samples=5000):
    by_group = defaultdict(list)
    for i, group in enumerate(groups):
        by_group[group].append(i)
    group_ids = list(by_group)
    rng = np.random.default_rng(42)
    differences = []
    for _ in range(n_samples):
        sampled = rng.choice(group_ids, len(group_ids), replace=True)
        indices = np.array([i for group in sampled for i in by_group[group]])
        candidate_pred = np.where(candidate_p[indices] >= 0.5, "succeeds", "dismissed")
        incumbent_pred = np.where(incumbent_p[indices] >= 0.5, "succeeds", "dismissed")
        differences.append(
            f1_score(y[indices], candidate_pred, labels=CLASSES, average="macro", zero_division=0) -
            f1_score(y[indices], incumbent_pred, labels=CLASSES, average="macro", zero_division=0)
        )
    return float(np.percentile(differences, 2.5))


def evaluate(data_dir: Path, incumbent_path: Path = DEFAULT_MODEL_PATH):
    report_path = data_dir / "evaluation_report.json"
    if report_path.exists():
        raise ValueError("Frozen holdout already evaluated; use a new dataset version")
    rows, split, _ = load_features(data_dir)
    training = json.loads((data_dir / "training_report.json").read_text(encoding="utf-8"))
    if review_queue_hash(data_dir, rows) != training["review_queue_sha256"]:
        raise ValueError("Audit signoff changed after training")
    candidate_path = data_dir / f"{training['version']}.joblib"
    candidate = joblib.load(candidate_path)
    incumbent = joblib.load(incumbent_path)
    if getattr(candidate, "version", None) != training["version"]:
        raise ValueError("Candidate artifact version differs from training report")
    holdout_ids = set(split["holdout_ids"])
    holdout = [row for row in rows if row["case_id"] in holdout_ids]
    y_counts = Counter(row["outcome"] for row in holdout)
    if len(holdout) < 100 or any(y_counts[cls] < 30 for cls in CLASSES):
        raise ValueError("Holdout does not meet size and class gates")
    X, y, groups = frame(holdout)
    candidate_p = candidate.predict_proba(X)[:, 1]
    incumbent_p = incumbent.predict_proba(X)[:, 1]
    candidate_metrics = metrics(y, candidate_p)
    incumbent_metrics = metrics(y, incumbent_p)
    lift = candidate_metrics["macro_f1"] - incumbent_metrics["macro_f1"]
    lower = paired_bootstrap_lower(y, candidate_p, incumbent_p, groups)
    recall_drop = {
        cls: incumbent_metrics["per_class"][cls]["recall"] - candidate_metrics["per_class"][cls]["recall"]
        for cls in CLASSES
    }
    slices = {}
    for key in ("appellant_type", "court"):
        slices[key] = {}
        for value in sorted(set(row[key] for row in holdout)):
            indices = np.array([i for i, row in enumerate(holdout) if row[key] == value])
            slices[key][value] = {
                "candidate": metrics(y[indices], candidate_p[indices]),
                "incumbent": metrics(y[indices], incumbent_p[indices]),
            }
    result = {
        "candidate_version": training["version"],
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "features_sha256": hashlib.sha256((data_dir / "features.csv").read_bytes()).hexdigest(),
        "review_queue_sha256": training["review_queue_sha256"],
        "incumbent_artifact": str(incumbent_path),
        "holdout_n": len(holdout),
        "class_counts": dict(y_counts),
        "candidate": candidate_metrics,
        "incumbent": incumbent_metrics,
        "macro_f1_lift": float(lift),
        "paired_bootstrap_95_lower": lower,
        "recall_drop": recall_drop,
        "slices": slices,
        "promotion_gate_passed": bool(lift >= 0.03 and lower > 0 and all(drop <= 0.02 for drop in recall_drop.values())),
    }
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--incumbent", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    report = evaluate(args.data_dir, args.incumbent)
    print(json.dumps({key: report[key] for key in ("holdout_n", "macro_f1_lift", "paired_bootstrap_95_lower", "recall_drop", "promotion_gate_passed")}, indent=2))


if __name__ == "__main__":
    main()
