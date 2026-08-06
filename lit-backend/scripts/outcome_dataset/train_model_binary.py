"""
Retrains the outcome classifier on a BINARY target: dismissed vs
succeeds (succeeds = allowed OR partly_allowed merged).

Why: scripts/outcome_dataset/diagnose_allowed_misclassification.py
found the 3-way model's "allowed" class un-learnable from the 5
simulator features + appellant_type — 100% of true-allowed cases (all
53) were misclassified out-of-fold, split near-evenly between dismissed
(27) and partly_allowed (26), and the confidently-wrong cases had
saturated, homogeneous feature values (argument_completeness=1.0,
case_complexity=0.5, statutory_strength~0.85-0.9 across the board) with
no separating signal left for a linear model. Merging allowed +
partly_allowed collapses exactly the boundary that had no signal, while
keeping the boundary the model clearly *could* find (dismissed vs not).

dataset_v2.csv's 3-way extracted_label column is untouched —
outcome_binary is derived in-memory here only, never written back.

    ./venv/bin/python3 -m scripts.outcome_dataset.train_model_binary
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset.labeling import extract_outcome_label
from scripts.outcome_dataset.scrape import load_cached_judgment
from scripts.outcome_dataset.train_model import (
    FEATURE_COLUMNS,
    MIN_CLASS_SIZE_WARNING,
    RANDOM_STATE,
    choose_fold_count,
    feature_names_out,
    load_usable_rows,
    make_pipeline,
    old_heuristic_scores,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "outcome_dataset"
MODEL_DIR = DATA_DIR / "model"
MODEL_PATH = MODEL_DIR / "outcome_classifier_binary.joblib"
REPORT_JSON = MODEL_DIR / "training_report_binary.json"
REPORT_MD = MODEL_DIR / "training_report.md"  # appended, not overwritten

BINARY_CLASSES = ["dismissed", "succeeds"]
TOP_N_DIAGNOSTIC = 10


# ---------------------------------------------------------------------------
# Target derivation + features
# ---------------------------------------------------------------------------

def derive_binary_label(extracted_label: str) -> str:
    return "dismissed" if extracted_label == "dismissed" else "succeeds"


def build_feature_frame_binary(rows: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    n_numeric = len(FEATURE_COLUMNS)
    X = np.empty((len(rows), n_numeric + 1), dtype=object)
    for i, r in enumerate(rows):
        for j, col in enumerate(FEATURE_COLUMNS):
            X[i, j] = float(r[col])
        X[i, n_numeric] = r["appellant_type"]
    y = np.array([derive_binary_label(r["extracted_label"]) for r in rows])
    return X, y


def old_heuristic_labels_binary(scores: np.ndarray) -> np.ndarray:
    """Same threshold used for the 3-way heuristic (simulator.py's own
    0.5 "Uncertain"/"Unfavorable" boundary) — binary collapse means
    >=0.5 (previously allowed OR partly_allowed) -> succeeds."""
    labels = np.empty(len(scores), dtype=object)
    labels[scores < 0.5] = "dismissed"
    labels[scores >= 0.5] = "succeeds"
    return labels


def majority_class(y_train: np.ndarray) -> str:
    values, counts = np.unique(y_train, return_counts=True)
    return values[np.argmax(counts)]


# ---------------------------------------------------------------------------
# CV comparison (also collects out-of-fold predictions for the diagnostic)
# ---------------------------------------------------------------------------

def _fold_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=BINARY_CLASSES, zero_division=0
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "per_class_precision": {c: float(precision[i]) for i, c in enumerate(BINARY_CLASSES)},
        "per_class_recall": {c: float(recall[i]) for i, c in enumerate(BINARY_CLASSES)},
        "per_class_f1": {c: float(f1[i]) for i, c in enumerate(BINARY_CLASSES)},
    }


def summarize_cv(per_fold: List[Dict[str, Any]]) -> Dict[str, Any]:
    accs = [f["accuracy"] for f in per_fold]
    f1s = [f["macro_f1"] for f in per_fold]
    per_class_f1 = {c: [] for c in BINARY_CLASSES}
    for f in per_fold:
        for c in BINARY_CLASSES:
            per_class_f1[c].append(f["per_class_f1"][c])
    return {
        "fold_accuracies": accs,
        "fold_macro_f1s": f1s,
        "mean_accuracy": float(np.mean(accs)),
        "std_accuracy": float(np.std(accs)),
        "mean_macro_f1": float(np.mean(f1s)),
        "std_macro_f1": float(np.std(f1s)),
        "per_class_f1_mean": {c: float(np.mean(v)) for c, v in per_class_f1.items()},
        "per_class_f1_std": {c: float(np.std(v)) for c, v in per_class_f1.items()},
        "per_class_f1_folds": per_class_f1,
    }


def run_cv_comparison(
    rows: List[Dict[str, Any]], n_splits: int
) -> Tuple[Dict[str, List[Dict[str, Any]]], np.ndarray, np.ndarray, List[str], np.ndarray]:
    X, y = build_feature_frame_binary(rows)
    heuristic_scores_all = old_heuristic_scores(rows)
    heuristic_labels_all = old_heuristic_labels_binary(heuristic_scores_all)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    per_fold: Dict[str, List[Dict[str, Any]]] = {"majority": [], "old_heuristic": [], "new_model": []}

    n = len(rows)
    oof_pred = np.empty(n, dtype=object)
    oof_proba = np.zeros((n, 2))
    classes_ref: List[str] = []

    for train_idx, test_idx in skf.split(X, y):
        y_train, y_test = y[train_idx], y[test_idx]

        maj_label = majority_class(y_train)
        maj_pred = np.full(len(test_idx), maj_label, dtype=object)
        per_fold["majority"].append(_fold_metrics(y_test, maj_pred))

        heur_pred = heuristic_labels_all[test_idx]
        per_fold["old_heuristic"].append(_fold_metrics(y_test, heur_pred))

        pipeline = make_pipeline()
        pipeline.fit(X[train_idx], y_train)
        classes_ref = list(pipeline.named_steps["clf"].classes_)
        new_pred = pipeline.predict(X[test_idx])
        new_proba = pipeline.predict_proba(X[test_idx])
        per_fold["new_model"].append(_fold_metrics(y_test, new_pred))

        oof_pred[test_idx] = new_pred
        oof_proba[test_idx] = new_proba

    return per_fold, oof_pred, oof_proba, classes_ref, y


# ---------------------------------------------------------------------------
# Final model + coefficients
# ---------------------------------------------------------------------------

def fit_final_model(rows: List[Dict[str, Any]]):
    X, y = build_feature_frame_binary(rows)
    pipeline = make_pipeline()
    pipeline.fit(X, y)
    return pipeline


def extract_coefficients(pipeline) -> Dict[str, Any]:
    clf = pipeline.named_steps["clf"]
    names = feature_names_out()
    classes = list(clf.classes_)

    # Binary LogisticRegression stores a single coef_/intercept_ row for
    # the positive class (classes_[1]) under the hood; expose both
    # classes' effective linear scores for symmetry with the 3-way report.
    if clf.coef_.shape[0] == 1:
        pos_class = classes[1]
        neg_class = classes[0]
        coef_table = {
            pos_class: {"intercept": float(clf.intercept_[0]), **{n: float(clf.coef_[0, j]) for j, n in enumerate(names)}},
            neg_class: {"intercept": float(-clf.intercept_[0]), **{n: float(-clf.coef_[0, j]) for j, n in enumerate(names)}},
        }
    else:
        coef_table = {
            cls: {"intercept": float(clf.intercept_[i]), **{n: float(clf.coef_[i, j]) for j, n in enumerate(names)}}
            for i, cls in enumerate(classes)
        }
    return {"classes": classes, "coefficients": coef_table}


# ---------------------------------------------------------------------------
# Diagnostic carryover — confident misclassifications of "succeeds"
# ---------------------------------------------------------------------------

def diagnose_succeeds_misclassification(
    rows: List[Dict[str, Any]],
    y: np.ndarray,
    oof_pred: np.ndarray,
    oof_proba: np.ndarray,
    classes_ref: List[str],
) -> Dict[str, Any]:
    class_idx = {c: i for i, c in enumerate(classes_ref)}
    succeeds_idx = class_idx["succeeds"]

    diagnostics = []
    for i, r in enumerate(rows):
        if y[i] != "succeeds":
            continue
        predicted = oof_pred[i]
        p_succeeds = oof_proba[i, succeeds_idx]
        p_predicted = oof_proba[i, class_idx[predicted]]
        diagnostics.append({
            "case_id": r["case_id"],
            "title": r["title"],
            "true_3way_label": r["extracted_label"],
            "misclassified": predicted != "succeeds",
            "predicted_as": predicted,
            "p_succeeds": float(p_succeeds),
            "p_predicted": float(p_predicted),
            "margin": float(p_predicted - p_succeeds),
            "features": {c: float(r[c]) for c in FEATURE_COLUMNS},
            "appellant_type": r["appellant_type"],
        })

    n_succeeds = len(diagnostics)
    n_misclassified = sum(1 for d in diagnostics if d["misclassified"])
    wrong = sorted((d for d in diagnostics if d["misclassified"]), key=lambda x: -x["margin"])
    top = wrong[:TOP_N_DIAGNOSTIC]

    for d in top:
        detail = load_cached_judgment(d["case_id"])
        d["label_snippet_full"] = extract_outcome_label(detail.text)["snippet"] if detail else "(raw judgment not cached)"

    return {
        "n_succeeds": n_succeeds,
        "n_misclassified": n_misclassified,
        "misclassification_rate": n_misclassified / n_succeeds if n_succeeds else None,
        "all_rows": diagnostics,
        "top_confident_wrong": top,
    }


# ---------------------------------------------------------------------------
# Markdown report (appended)
# ---------------------------------------------------------------------------

def render_markdown_section(report: Dict[str, Any]) -> str:
    cv = report["cv_summary"]
    coef = report["coefficients"]["coefficients"]
    diag = report["diagnostic"]
    cm = report["confusion_matrix"]

    lines = [
        "",
        "---",
        "",
        "# Binary model (dismissed vs succeeds) — training report",
        "",
        "## Why the target was merged",
        "",
        "The 3-way model (see report above) could not learn the \"allowed\" class at all: "
        f"**100% of the {report['label_counts_3way']['allowed']} true-allowed cases were "
        "misclassified out-of-fold** (27 → dismissed, 26 → partly_allowed — a near-even split, "
        "not a lean toward either alternative), and the most confidently-wrong cases shared "
        "saturated, homogeneous feature values (argument_completeness=1.0, case_complexity=0.5, "
        "statutory_strength~0.85-0.9 across nearly all of them) with no remaining variance for a "
        "linear model to separate them from \"dismissed\". Since \"partly_allowed\" already sits "
        "conceptually closer to \"allowed\" than to \"dismissed\" (the appellant gets *some* relief "
        "either way), merging the two collapses exactly the boundary that had no learnable signal, "
        "while keeping the boundary the 3-way model clearly could find (dismissed vs. not).",
        "",
        "## Data",
        f"- Usable N: **{report['usable_n']}** (same filter as the 3-way model: dataset_v2.csv, "
        "label != unclear, confidence >= 0.6, not borderline_scope)",
        f"- outcome_binary counts: {report['label_counts_binary']} "
        f"(derived in-memory from extracted_label — dataset_v2.csv's 3-way column is untouched)",
        f"- {report['n_splits']}-fold stratified CV, same random_state as the 3-way run",
        "",
        "## Baseline comparison (same 5 stratified folds for all three)",
        "",
        "| Approach | Accuracy | Macro-F1 | F1(dismissed) | F1(succeeds) |",
        "|---|---|---|---|---|",
        f"| Majority class (always \"dismissed\") | {cv['majority']['mean_accuracy']:.3f} ± {cv['majority']['std_accuracy']:.3f} | {cv['majority']['mean_macro_f1']:.3f} ± {cv['majority']['std_macro_f1']:.3f} | {cv['majority']['per_class_f1_mean']['dismissed']:.3f} | {cv['majority']['per_class_f1_mean']['succeeds']:.3f} |",
        f"| Old heuristic (thresholded at 0.5) | {cv['old_heuristic']['mean_accuracy']:.3f} ± {cv['old_heuristic']['std_accuracy']:.3f} | {cv['old_heuristic']['mean_macro_f1']:.3f} ± {cv['old_heuristic']['std_macro_f1']:.3f} | {cv['old_heuristic']['per_class_f1_mean']['dismissed']:.3f} | {cv['old_heuristic']['per_class_f1_mean']['succeeds']:.3f} |",
        f"| **New binary model** | {cv['new_model']['mean_accuracy']:.3f} ± {cv['new_model']['std_accuracy']:.3f} | **{cv['new_model']['mean_macro_f1']:.3f} ± {cv['new_model']['std_macro_f1']:.3f}** | {cv['new_model']['per_class_f1_mean']['dismissed']:.3f} | **{cv['new_model']['per_class_f1_mean']['succeeds']:.3f}** |",
        "",
        f"succeeds F1 per fold: {[round(v,3) for v in cv['new_model']['per_class_f1_folds']['succeeds']]}",
        f"dismissed F1 per fold: {[round(v,3) for v in cv['new_model']['per_class_f1_folds']['dismissed']]}",
        "",
        "## Confusion matrix (full out-of-fold predictions, all 187 rows — every row predicted "
        "exactly once by a fold that didn't train on it, more robust than a single held-out split)",
        "",
        "| Actual (rows) / Predicted (cols) | dismissed | succeeds |",
        "|---|---|---|",
        f"| dismissed | {cm['dismissed'][0]} | {cm['dismissed'][1]} |",
        f"| succeeds | {cm['succeeds'][0]} | {cm['succeeds'][1]} |",
        "",
        "## Diagnostic carryover — confident misclassifications of \"succeeds\"",
        "",
        f"- succeeds cases: {diag['n_succeeds']}",
        f"- misclassified out-of-fold: {diag['n_misclassified']} ({100*diag['misclassification_rate']:.1f}%)",
        "",
    ]

    if diag["n_misclassified"] == 0:
        lines.append("No misclassifications — nothing further to show.")
    else:
        from collections import Counter
        appellant_counts = Counter(d["appellant_type"] for d in diag["top_confident_wrong"])
        dominant, dominant_n = appellant_counts.most_common(1)[0]
        if dominant_n >= len(diag["top_confident_wrong"]) * 0.6:
            lines.append(
                f"**Pattern**: {dominant_n} of the top {len(diag['top_confident_wrong'])} most confidently "
                f"misclassified cases have `appellant_type={dominant}`. Matches the coefficient table below — "
                f"`appellant_type={dominant}` has a strong learned pull toward the majority prediction for that "
                "category, which is directionally correct on average but overrides the weaker feature signal "
                "for the minority of such cases that actually succeed."
            )
            lines.append("")
        lines.append(f"Top {len(diag['top_confident_wrong'])} most confidently misclassified \"succeeds\" cases:")
        lines.append("")
        for rank, d in enumerate(diag["top_confident_wrong"], 1):
            feat_str = ", ".join(f"{k.replace('feature_', '')}={v:.3f}" for k, v in d["features"].items())
            lines.extend([
                f"**#{rank}: case_id={d['case_id']}** (originally 3-way label: {d['true_3way_label']})",
                f"- {d['title']}",
                f"- Predicted: dismissed (p_succeeds={d['p_succeeds']:.3f}, p_dismissed={d['p_predicted']:.3f}, margin={d['margin']:+.3f}) | appellant_type: {d['appellant_type']}",
                f"- Features: {feat_str}",
                f"- Snippet: {d['label_snippet_full']}",
                "",
            ])

    lines.extend([
        "## What the model learned — coefficients (binary)",
        "",
        "Positive coefficient = pushes toward \"succeeds\"; negative = pushes toward \"dismissed\".",
        "",
        "| Feature | succeeds | dismissed |",
        "|---|---|---|",
        *[
            f"| {feat} | {coef['succeeds'][feat]:.3f} | {coef['dismissed'][feat]:.3f} |"
            for feat in feature_names_out()
        ],
        f"| *intercept* | {coef['succeeds']['intercept']:.3f} | {coef['dismissed']['intercept']:.3f} |",
        "",
        "## Limitations — carried over, still apply",
        "",
        "- **appellant_type is still a heuristic**, not ground truth — its own confidence scores "
        "and error modes (see summary_v2.md) propagate into this model as a noisy input feature, "
        "unchanged from the 3-way run.",
        "- **N=187 is still small**, now split 113/74 instead of 3 ways — better per-class support "
        "than before but still modest for 5-fold CV.",
        "- **Single domain, leave-one-out precedent proxy, truncated-text label-leakage mitigation** — "
        "all limitations from summary.md / summary_v2.md apply unchanged; merging the target doesn't "
        "touch the feature-computation pipeline.",
        "- **The 3-way granularity (allowed vs partly_allowed) is now unavailable from this model** — "
        "if the live app needs to distinguish full relief from partial relief, this binary model can't "
        "provide that; it was traded away specifically because that distinction had no learnable signal "
        "here, not because it doesn't matter.",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_usable_rows()
    label_counts_3way = {}
    for r in rows:
        label_counts_3way[r["extracted_label"]] = label_counts_3way.get(r["extracted_label"], 0) + 1

    label_counts_binary: Dict[str, int] = {}
    for r in rows:
        b = derive_binary_label(r["extracted_label"])
        label_counts_binary[b] = label_counts_binary.get(b, 0) + 1

    print(f"Usable N: {len(rows)}")
    print(f"outcome_binary counts: {label_counts_binary}")

    small_classes = {k: v for k, v in label_counts_binary.items() if v < MIN_CLASS_SIZE_WARNING}
    if small_classes:
        print(f"WARNING: classes with fewer than {MIN_CLASS_SIZE_WARNING} rows: {small_classes}")

    n_splits = choose_fold_count(label_counts_binary)
    print(f"Using {n_splits}-fold stratified CV (smallest class = {min(label_counts_binary.values())})")

    per_fold, oof_pred, oof_proba, classes_ref, y = run_cv_comparison(rows, n_splits)
    cv_summary = {name: summarize_cv(folds) for name, folds in per_fold.items()}

    final_model = fit_final_model(rows)
    coefficients = extract_coefficients(final_model)

    cm = confusion_matrix(y, oof_pred, labels=BINARY_CLASSES)
    cm_dict = {lbl: cm[i].tolist() for i, lbl in enumerate(BINARY_CLASSES)}

    diagnostic = diagnose_succeeds_misclassification(rows, y, oof_pred, oof_proba, classes_ref)

    joblib.dump(final_model, MODEL_PATH)
    print(f"Saved trained binary model to {MODEL_PATH}")

    report = {
        "usable_n": len(rows),
        "label_counts_3way": label_counts_3way,
        "label_counts_binary": label_counts_binary,
        "n_splits": n_splits,
        "cv_summary": cv_summary,
        "coefficients": coefficients,
        "confusion_matrix": cm_dict,
        "diagnostic": diagnostic,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved binary training report to {REPORT_JSON}")

    with open(REPORT_MD, "a", encoding="utf-8") as f:
        f.write(render_markdown_section(report))
    print(f"Appended binary section to {REPORT_MD}")

    print()
    print("=== Binary CV comparison (mean +/- std across folds) ===")
    for name in ["majority", "old_heuristic", "new_model"]:
        s = cv_summary[name]
        print(
            f"{name:15s} accuracy={s['mean_accuracy']:.3f}+/-{s['std_accuracy']:.3f}  "
            f"macro_f1={s['mean_macro_f1']:.3f}+/-{s['std_macro_f1']:.3f}  "
            f"F1(dismissed)={s['per_class_f1_mean']['dismissed']:.3f}  "
            f"F1(succeeds)={s['per_class_f1_mean']['succeeds']:.3f}"
        )

    print()
    print(f"=== Diagnostic: succeeds misclassification ===")
    print(f"succeeds cases: {diagnostic['n_succeeds']}, misclassified: {diagnostic['n_misclassified']} "
          f"({100*diagnostic['misclassification_rate']:.1f}%)")
    if diagnostic["n_misclassified"] / diagnostic["n_succeeds"] > 0.9:
        print("WARNING: succeeds F1 is still near-zero — this is a harder ceiling than the 3-way split explained.")


if __name__ == "__main__":
    main()
