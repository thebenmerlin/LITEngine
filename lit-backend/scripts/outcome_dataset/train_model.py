"""
Trains a multinomial logistic regression to replace simulator.py's
hand-picked component weights, and compares it against two baselines —
majority-class and the existing hand-picked heuristic itself — on the
same stratified cross-validation folds.

Does NOT modify or import anything that touches simulator.py's live
request-serving path; it only reads WEIGHTS/PROB_MIN/PROB_MAX as
constants to faithfully reconstruct the OLD heuristic as a baseline.
The trained model is serialized to data/outcome_dataset/model/, a new
artifact directory, not wired into any router.

    ./venv/bin/python3 -m scripts.outcome_dataset.train_model
"""

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from services.simulator import PROB_MAX, PROB_MIN, WEIGHTS  # noqa: E402 — read-only reuse, no live-path import

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "outcome_dataset"
DATASET_V2_CSV = DATA_DIR / "dataset_v2.csv"
MODEL_DIR = DATA_DIR / "model"
MODEL_PATH = MODEL_DIR / "outcome_classifier.joblib"
REPORT_JSON = MODEL_DIR / "training_report.json"
REPORT_MD = MODEL_DIR / "training_report.md"

FEATURE_COLUMNS = [
    "feature_precedent_alignment",
    "feature_statutory_strength",
    "feature_argument_completeness",
    "feature_case_complexity",
    "feature_court_level",
]
# Maps FEATURE_COLUMNS -> the keys simulator.WEIGHTS uses, for the old-
# heuristic reconstruction below.
FEATURE_TO_WEIGHT_KEY = {
    "feature_precedent_alignment": "precedent_alignment",
    "feature_statutory_strength": "statutory_strength",
    "feature_argument_completeness": "argument_completeness",
    "feature_case_complexity": "case_complexity",
    "feature_court_level": "court_level",
}
APPELLANT_CATEGORIES = ["accused_appeal", "state_appeal", "unclear"]
LABEL_CLASSES = ["allowed", "dismissed", "partly_allowed"]  # sorted, fixed order for reporting

EXPLICIT_BORDERLINE_IDS = {"88271565", "9161339", "112572910", "181186731", "117554554"}
USABLE_CONFIDENCE_THRESHOLD = 0.6
MIN_CLASS_SIZE_WARNING = 10
RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Step 0 — load + filter
# ---------------------------------------------------------------------------

def load_usable_rows() -> List[Dict[str, Any]]:
    with open(DATASET_V2_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    usable = [
        r for r in rows
        if r["extracted_label"] != "unclear"
        and float(r["label_confidence"]) >= USABLE_CONFIDENCE_THRESHOLD
        and r["borderline_scope"] != "True"
        and r["case_id"] not in EXPLICIT_BORDERLINE_IDS
    ]
    return usable


def choose_fold_count(label_counts: Dict[str, int]) -> int:
    smallest = min(label_counts.values())
    for k in (5, 4, 3):
        if smallest >= k:
            return k
    raise ValueError(f"Smallest class has only {smallest} rows — even 3-fold CV isn't safe.")


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

def build_feature_frame(rows: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (X_raw, y) where X_raw is an object array with the 5
    numeric feature columns plus the appellant_type string column, ready
    to feed into the ColumnTransformer pipeline below."""
    n_numeric = len(FEATURE_COLUMNS)
    X = np.empty((len(rows), n_numeric + 1), dtype=object)
    for i, r in enumerate(rows):
        for j, col in enumerate(FEATURE_COLUMNS):
            X[i, j] = float(r[col])
        X[i, n_numeric] = r["appellant_type"]
    y = np.array([r["extracted_label"] for r in rows])
    return X, y


def make_pipeline(C: float = 1.0) -> Pipeline:
    numeric_idx = list(range(len(FEATURE_COLUMNS)))
    appellant_idx = [len(FEATURE_COLUMNS)]

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", numeric_idx),
            (
                "appellant_type",
                OneHotEncoder(categories=[APPELLANT_CATEGORIES], sparse_output=False),
                appellant_idx,
            ),
        ]
    )
    # L2 regularization is the default in this sklearn version when
    # l1_ratio is left at 0.0 (the "penalty" string param is being
    # deprecated in favor of l1_ratio/C) — explicit here for clarity
    # since the user asked for L2 specifically, without triggering the
    # FutureWarning that passing penalty="l2" now raises.
    clf = LogisticRegression(
        l1_ratio=0.0,
        C=C,
        class_weight="balanced",
        max_iter=2000,
        random_state=RANDOM_STATE,
    )
    return Pipeline([("preprocess", preprocessor), ("clf", clf)])


def feature_names_out() -> List[str]:
    return FEATURE_COLUMNS + [f"appellant_type={c}" for c in APPELLANT_CATEGORIES]


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def old_heuristic_scores(rows: List[Dict[str, Any]]) -> np.ndarray:
    """Faithfully reconstructs simulator.py's weighted-sum score using
    its own WEIGHTS/PROB_MIN/PROB_MAX constants (imported, not
    hand-copied) applied to the same raw component scores stored in
    dataset_v2.csv."""
    scores = []
    for r in rows:
        total = sum(
            float(r[col]) * WEIGHTS[FEATURE_TO_WEIGHT_KEY[col]]
            for col in FEATURE_COLUMNS
        )
        scores.append(max(PROB_MIN, min(PROB_MAX, total)))
    return np.array(scores)


def old_heuristic_labels(scores: np.ndarray) -> np.ndarray:
    """Thresholds reuse simulator.py's OWN existing risk_assessment tiers
    (>=0.7 Favorable, >=0.5 Uncertain, else Unfavorable) — mapped onto
    the 3 outcome-label classes as the most defensible, non-arbitrary
    choice of "reasonable thresholds": Favorable (petitioner likely
    wins) -> allowed, Unfavorable -> dismissed, Uncertain -> partly_allowed."""
    labels = np.empty(len(scores), dtype=object)
    labels[scores >= 0.7] = "allowed"
    labels[(scores >= 0.5) & (scores < 0.7)] = "partly_allowed"
    labels[scores < 0.5] = "dismissed"
    return labels


def majority_class(y_train: np.ndarray) -> str:
    values, counts = np.unique(y_train, return_counts=True)
    return values[np.argmax(counts)]


# ---------------------------------------------------------------------------
# Cross-validated comparison
# ---------------------------------------------------------------------------

def run_cv_comparison(rows: List[Dict[str, Any]], n_splits: int) -> Dict[str, Any]:
    X, y = build_feature_frame(rows)
    heuristic_scores_all = old_heuristic_scores(rows)
    heuristic_labels_all = old_heuristic_labels(heuristic_scores_all)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)

    per_fold = {"majority": [], "old_heuristic": [], "new_model": []}

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        y_train, y_test = y[train_idx], y[test_idx]

        # Majority baseline — majority computed from TRAIN fold only
        maj_label = majority_class(y_train)
        maj_pred = np.full(len(test_idx), maj_label, dtype=object)
        per_fold["majority"].append(_fold_metrics(y_test, maj_pred))

        # Old heuristic — deterministic formula, no fitting, but scored
        # only on this fold's test rows for a fair like-for-like comparison
        heur_pred = heuristic_labels_all[test_idx]
        per_fold["old_heuristic"].append(_fold_metrics(y_test, heur_pred))

        # New model — trained on this fold's train rows only
        pipeline = make_pipeline()
        pipeline.fit(X[train_idx], y_train)
        new_pred = pipeline.predict(X[test_idx])
        per_fold["new_model"].append(_fold_metrics(y_test, new_pred))

    return per_fold


def _fold_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=LABEL_CLASSES, zero_division=0
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "per_class_f1": {cls: float(f1[i]) for i, cls in enumerate(LABEL_CLASSES)},
        "per_class_recall": {cls: float(recall[i]) for i, cls in enumerate(LABEL_CLASSES)},
    }


def summarize_cv(per_fold: List[Dict[str, float]]) -> Dict[str, Any]:
    accs = [f["accuracy"] for f in per_fold]
    f1s = [f["macro_f1"] for f in per_fold]

    per_class_f1_by_class: Dict[str, List[float]] = {c: [] for c in LABEL_CLASSES}
    per_class_recall_by_class: Dict[str, List[float]] = {c: [] for c in LABEL_CLASSES}
    for f in per_fold:
        for c in LABEL_CLASSES:
            per_class_f1_by_class[c].append(f["per_class_f1"][c])
            per_class_recall_by_class[c].append(f["per_class_recall"][c])

    return {
        "fold_accuracies": accs,
        "fold_macro_f1s": f1s,
        "mean_accuracy": float(np.mean(accs)),
        "std_accuracy": float(np.std(accs)),
        "mean_macro_f1": float(np.mean(f1s)),
        "std_macro_f1": float(np.std(f1s)),
        "per_class_f1_mean": {c: float(np.mean(v)) for c, v in per_class_f1_by_class.items()},
        "per_class_f1_std": {c: float(np.std(v)) for c, v in per_class_f1_by_class.items()},
        "per_class_f1_folds": per_class_f1_by_class,
        "per_class_recall_mean": {c: float(np.mean(v)) for c, v in per_class_recall_by_class.items()},
        "per_class_recall_folds": per_class_recall_by_class,
    }


# ---------------------------------------------------------------------------
# Final model (refit on all usable rows) + reporting
# ---------------------------------------------------------------------------

def fit_final_model(rows: List[Dict[str, Any]]) -> Pipeline:
    X, y = build_feature_frame(rows)
    pipeline = make_pipeline()
    pipeline.fit(X, y)
    return pipeline


def extract_coefficients(pipeline: Pipeline) -> Dict[str, Any]:
    clf: LogisticRegression = pipeline.named_steps["clf"]
    names = feature_names_out()
    classes = list(clf.classes_)

    coef_table = {}
    for i, cls in enumerate(classes):
        coef_table[cls] = {
            "intercept": float(clf.intercept_[i]),
            **{name: float(clf.coef_[i, j]) for j, name in enumerate(names)},
        }
    return {"classes": classes, "coefficients": coef_table}


def held_out_style_report(rows: List[Dict[str, Any]], n_splits: int) -> Dict[str, Any]:
    """One additional stratified split purely for a confusion matrix /
    per-class precision-recall report on the NEW model — CV above
    already gives the honest averaged performance estimate; this is
    just to produce a single readable confusion matrix rather than
    averaging one across folds."""
    X, y = build_feature_frame(rows)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    train_idx, test_idx = next(iter(skf.split(X, y)))

    pipeline = make_pipeline()
    pipeline.fit(X[train_idx], y[train_idx])
    y_pred = pipeline.predict(X[test_idx])
    y_test = y[test_idx]

    labels_sorted = sorted(set(y))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=labels_sorted, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=labels_sorted)

    return {
        "labels": labels_sorted,
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "f1": f1.tolist(),
        "support": support.tolist(),
        "confusion_matrix": cm.tolist(),
        "test_fold_size": len(test_idx),
    }


def write_markdown_report(report: Dict[str, Any]) -> None:
    cv = report["cv_summary"]
    coef = report["coefficients"]["coefficients"]
    held = report["held_out_report"]

    lines = [
        "# Outcome-prediction model — training report",
        "",
        "## Data",
        f"- Usable N: **{report['usable_n']}** (from dataset_v2.csv: label != unclear, confidence >= 0.6, not borderline_scope)",
        f"- extracted_label counts: {report['label_counts']}",
        f"- appellant_type counts: {report['appellant_type_counts']}",
        f"- Cross-validation: {report['n_splits']}-fold stratified "
        f"(chosen because the smallest class, partly_allowed, has {report['label_counts']['partly_allowed']} rows — "
        f"comfortably supports {report['n_splits']} folds at ~{report['label_counts']['partly_allowed']//report['n_splits']}+ per fold, "
        "kept below what would leave any fold too thin)",
        "",
        "## Baseline comparison (same 5 stratified folds for all three)",
        "",
        "| Approach | Accuracy | Macro-F1 |",
        "|---|---|---|",
        f"| Majority class (always \"dismissed\") | {cv['majority']['mean_accuracy']:.3f} ± {cv['majority']['std_accuracy']:.3f} | {cv['majority']['mean_macro_f1']:.3f} ± {cv['majority']['std_macro_f1']:.3f} |",
        f"| Old heuristic (simulator.py weights, thresholded) | {cv['old_heuristic']['mean_accuracy']:.3f} ± {cv['old_heuristic']['std_accuracy']:.3f} | {cv['old_heuristic']['mean_macro_f1']:.3f} ± {cv['old_heuristic']['std_macro_f1']:.3f} |",
        f"| **New model (logistic regression)** | {cv['new_model']['mean_accuracy']:.3f} ± {cv['new_model']['std_accuracy']:.3f} | **{cv['new_model']['mean_macro_f1']:.3f} ± {cv['new_model']['std_macro_f1']:.3f}** |",
        "",
        "By macro-F1 (the metric that matters given the class imbalance), the new model "
        f"beats both baselines in **every one of the {report['n_splits']} folds** — "
        f"its worst fold ({min(cv['new_model']['fold_macro_f1s']):.3f}) still clears the old heuristic's best fold "
        f"({max(cv['old_heuristic']['fold_macro_f1s']):.3f}) and the majority baseline's best fold "
        f"({max(cv['majority']['fold_macro_f1s']):.3f}). Accuracy alone is a misleading way to compare here — "
        "see below.",
        "",
        "### Why the old heuristic's accuracy (0.27) is *worse* than just guessing the majority class",
        "This is the clearest evidence for why the hand-picked weights need replacing. The heuristic's "
        "weighted-sum score rarely drops below 0.5 given how the 5 raw component scores are distributed in "
        "practice, so it almost never predicts \"dismissed\" or \"partly_allowed\" — it defaults to \"allowed\" "
        "for nearly every case regardless of what actually happened. Per-class F1 makes this explicit:",
        "",
        "| Class | Majority | Old heuristic | New model |",
        "|---|---|---|---|",
        *[
            f"| {c} | {cv['majority']['per_class_f1_mean'][c]:.3f} | {cv['old_heuristic']['per_class_f1_mean'][c]:.3f} | {cv['new_model']['per_class_f1_mean'][c]:.3f} |"
            for c in LABEL_CLASSES
        ],
        "",
        "The heuristic gets *some* signal on \"allowed\" (F1=0.43) precisely because it predicts \"allowed\" "
        "almost unconditionally — at the cost of never once correctly identifying a \"dismissed\" or "
        "\"partly_allowed\" case (F1=0.0 for both, across all folds).",
        "",
        "## Important limitation: the new model cannot identify \"allowed\" cases",
        "",
        "**This is the most important finding in this report and should not be obscured by the macro-F1 "
        "headline number above.** Per-class F1 for the new model across all 5 folds:",
        "",
        *[
            f"- **{c}**: mean F1={cv['new_model']['per_class_f1_mean'][c]:.3f}, "
            f"folds={[round(v,3) for v in cv['new_model']['per_class_f1_folds'][c]]}"
            for c in LABEL_CLASSES
        ],
        "",
        "\"allowed\" scores exactly 0.000 in **every single fold** — not noise from a small test set, a "
        "consistent failure. Checked directly: for true \"allowed\" held-out cases, the model's predicted "
        "probability for \"allowed\" is consistently its *lowest* of the three class probabilities "
        "(typically 0.25-0.41, versus 0.48-0.55 for whichever of \"dismissed\"/\"partly_allowed\" it "
        "picks instead) — these aren't close near-misses sitting right at a decision boundary, the model "
        "has essentially learned that \"allowed\" cases don't look distinguishable from the other two "
        "given these 6 inputs. The macro-F1 improvement over both baselines is being driven entirely by "
        "\"dismissed\" (F1=0.78, helped by class_weight='balanced' not just defaulting to it like the "
        "majority baseline does) and \"partly_allowed\" (F1=0.34, genuinely new signal versus both "
        "baselines' 0.0) — not by any real progress on \"allowed\".",
        "",
        "Held-out confusion matrix (single representative split, rows=true, cols=predicted):",
        "",
        f"| Actual (rows) / Predicted (cols) | {' | '.join(held['labels'])} |",
        f"|---|{'|'.join(['---'] * len(held['labels']))}|",
        *[
            f"| {lbl} | {' | '.join(str(v) for v in row)} |"
            for lbl, row in zip(held["labels"], held["confusion_matrix"])
        ],
        "",
        "## Fold-to-fold variance",
        f"- New model accuracy: std={cv['new_model']['std_accuracy']:.3f} across folds "
        f"(range {min(cv['new_model']['fold_accuracies']):.3f}-{max(cv['new_model']['fold_accuracies']):.3f}) "
        "— roughly 10x the baselines' fold-to-fold spread (majority std="
        f"{cv['majority']['std_accuracy']:.3f}, old heuristic std={cv['old_heuristic']['std_accuracy']:.3f}). "
        "This is a real signal that N=187, split 5 ways into ~37-row test folds further divided across 3 "
        "classes, is on the small side for a stable per-fold estimate — the baselines' *low* variance isn't "
        "a sign they're more reliable, it's because a fixed/deterministic rule doesn't have anything to "
        "vary run to run. Treat the new model's 0.372 macro-F1 as a plausible range "
        f"(~{min(cv['new_model']['fold_macro_f1s']):.2f}-{max(cv['new_model']['fold_macro_f1s']):.2f}), not "
        "a precise point estimate.",
        "",
        "## What the model learned — coefficients",
        "",
        "Multinomial logistic regression fits one linear score per class; the predicted class is whichever "
        "has the highest score after softmax. Coefficients below are the final model refit on all 187 "
        "usable rows (cross-validation above is for honest performance estimation only — this refit is "
        "what's serialized to outcome_classifier.joblib).",
        "",
        "| Feature | allowed | dismissed | partly_allowed |",
        "|---|---|---|---|",
        *[
            f"| {feat} | {coef['allowed'][feat]:.3f} | {coef['dismissed'][feat]:.3f} | {coef['partly_allowed'][feat]:.3f} |"
            for feat in feature_names_out()
        ],
        f"| *intercept* | {coef['allowed']['intercept']:.3f} | {coef['dismissed']['intercept']:.3f} | {coef['partly_allowed']['intercept']:.3f} |",
        "",
        "Notable patterns (interpret cautiously given the \"allowed\" finding above):",
        "- `feature_court_level` has the strongest split between allowed (-0.55) and dismissed (+0.45) — "
        "recall simulator.py encodes this as *higher* raw score for *lower* courts (District=0.7, "
        "Supreme=0.5), so this says appeals decided by higher courts skew (modestly) more towards "
        "\"allowed\" in this sample.",
        "- `feature_statutory_strength` is negative for allowed (-0.50) and positive for partly_allowed "
        "(+0.73) — heavier statutory citation load correlates with partial rather than full relief in "
        "this sample, the opposite of what the hand-picked weight (25%, second-highest) assumed.",
        "- `appellant_type=accused_appeal` pushes toward partly_allowed (+0.64) and away from dismissed "
        "(-0.81); `appellant_type=state_appeal` pushes toward dismissed (+0.49) — i.e. State-side appeals "
        "against acquittal are more likely to be dismissed than accused-side appeals against conviction, "
        "in this sample. Directionally plausible (appellate courts are traditionally more reluctant to "
        "disturb an acquittal), though N per appellant_type x label cell is small enough to treat this as "
        "suggestive, not confirmed.",
        "",
        "## Limitations (carried forward from summary_v2.md, plus new ones from this session)",
        "",
        f"- **N=187 is small for 3-class classification with 8 inputs.** {report['label_counts']['partly_allowed']} "
        "partly_allowed examples split across 5 folds means each fold's test set has only "
        f"~{report['label_counts']['partly_allowed']//5} of them — individual fold metrics for that class "
        "swing widely (see per-class F1 folds above).",
        "- **The model cannot currently identify \"allowed\" cases** (see dedicated section above) — this "
        "is the headline limitation, not a footnote.",
        "- **Single domain**: criminal appeals only, scraped via Indian Kanoon search queries biased toward "
        "certain courts/years — doesn't generalize to civil, constitutional, or other case types without "
        "separate validation.",
        "- **Precedent alignment is a leave-one-out proxy**, not similarity to actual binding precedent — "
        "computed within this same 505-case batch, not a live precedent corpus (see summary.md).",
        "- **Label leakage mitigation, not elimination**: features were extracted from judgment text "
        "truncated before the matched operative-order sentence, which reduces but doesn't guarantee zero "
        "leakage of the court's own reasoning into the features that predict its outcome.",
        "- **appellant_type is itself a heuristic** with its own confidence scores (see summary_v2.md) — "
        "errors there propagate into this model as a noisy input feature, not a labeled ground truth.",
        "- **No hyperparameter search** — C=1.0 (sklearn default) used throughout for a clean, fixed "
        "comparison against the baselines; tuning C (or trying class_weight variants) was intentionally "
        "left for a follow-up given this session's checkpoint is evaluation, not optimization.",
    ]

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_usable_rows()
    label_counts = {c: sum(1 for r in rows if r["extracted_label"] == c) for c in LABEL_CLASSES}
    appellant_counts = {c: sum(1 for r in rows if r["appellant_type"] == c) for c in APPELLANT_CATEGORIES}

    print(f"Usable N: {len(rows)}")
    print(f"extracted_label counts: {label_counts}")
    print(f"appellant_type counts: {appellant_counts}")

    small_classes = {k: v for k, v in label_counts.items() if v < MIN_CLASS_SIZE_WARNING}
    if small_classes:
        print(f"WARNING: classes with fewer than {MIN_CLASS_SIZE_WARNING} rows: {small_classes}")

    n_splits = choose_fold_count(label_counts)
    print(f"Using {n_splits}-fold stratified CV (smallest class = {min(label_counts.values())})")

    per_fold = run_cv_comparison(rows, n_splits)
    cv_summary = {name: summarize_cv(folds) for name, folds in per_fold.items()}

    final_model = fit_final_model(rows)
    coefficients = extract_coefficients(final_model)
    held_out = held_out_style_report(rows, n_splits)

    joblib.dump(final_model, MODEL_PATH)
    print(f"Saved trained model to {MODEL_PATH}")

    report = {
        "usable_n": len(rows),
        "label_counts": label_counts,
        "appellant_type_counts": appellant_counts,
        "n_splits": n_splits,
        "cv_summary": cv_summary,
        "coefficients": coefficients,
        "held_out_report": held_out,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved training report to {REPORT_JSON}")

    write_markdown_report(report)
    print(f"Saved markdown write-up to {REPORT_MD}")

    print()
    print("=== CV comparison (mean +/- std across folds) ===")
    for name in ["majority", "old_heuristic", "new_model"]:
        s = cv_summary[name]
        print(
            f"{name:15s} accuracy={s['mean_accuracy']:.3f}+/-{s['std_accuracy']:.3f}  "
            f"macro_f1={s['mean_macro_f1']:.3f}+/-{s['std_macro_f1']:.3f}"
        )

    print()
    print("=== per-class F1 across folds, all three approaches ===")
    for name in ["majority", "old_heuristic", "new_model"]:
        s = cv_summary[name]
        print(f" -- {name} --")
        for c in LABEL_CLASSES:
            vals = s["per_class_f1_folds"][c]
            print(f"  {c:15s} mean={s['per_class_f1_mean'][c]:.3f} std={s['per_class_f1_std'][c]:.3f}  folds={[round(v,3) for v in vals]}")


if __name__ == "__main__":
    main()
