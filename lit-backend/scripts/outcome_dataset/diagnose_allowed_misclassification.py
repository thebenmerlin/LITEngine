"""
Diagnostic: for every true-"allowed" case in the 187-row usable set,
get out-of-fold predictions (each row predicted by a fold that did NOT
train on it) and report what it got misclassified as, then pull the
label_snippet_full text for the most confidently-wrong cases alongside
their 5 feature values.

Reuses train_model.py's exact data loading / feature-building / model
config / fold setup (same random_state=42, same 5-fold split) so this
is diagnosing the same model already reported in training_report.md,
not a new one. No retraining beyond the 5 per-fold fits already implied
by cross-validation, no new data.

    ./venv/bin/python3 -m scripts.outcome_dataset.diagnose_allowed_misclassification
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> lit-backend/

from scripts.outcome_dataset.labeling import extract_outcome_label
from scripts.outcome_dataset.scrape import load_cached_judgment
from scripts.outcome_dataset.train_model import (
    FEATURE_COLUMNS,
    RANDOM_STATE,
    build_feature_frame,
    load_usable_rows,
    make_pipeline,
)

TOP_N = 10


def main() -> None:
    rows = load_usable_rows()
    X, y = build_feature_frame(rows)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    n = len(rows)
    oof_pred = np.empty(n, dtype=object)
    oof_proba = np.zeros((n, 3))
    classes_ref = None

    for train_idx, test_idx in skf.split(X, y):
        pipeline = make_pipeline()
        pipeline.fit(X[train_idx], y[train_idx])
        classes_ref = list(pipeline.named_steps["clf"].classes_)
        proba = pipeline.predict_proba(X[test_idx])
        pred = pipeline.predict(X[test_idx])
        oof_pred[test_idx] = pred
        oof_proba[test_idx] = proba

    class_idx = {c: i for i, c in enumerate(classes_ref)}
    allowed_idx = class_idx["allowed"]

    # -- Collect every true-"allowed" row's out-of-fold outcome ---------------
    diagnostics = []
    for i, r in enumerate(rows):
        if r["extracted_label"] != "allowed":
            continue
        predicted = oof_pred[i]
        p_allowed = oof_proba[i, allowed_idx]
        p_predicted = oof_proba[i, class_idx[predicted]]
        diagnostics.append({
            "case_id": r["case_id"],
            "title": r["title"],
            "misclassified": predicted != "allowed",
            "predicted_as": predicted,
            "p_allowed": p_allowed,
            "p_predicted": p_predicted,
            "margin": p_predicted - p_allowed,  # how confidently wrong
            "features": {c: float(r[c]) for c in FEATURE_COLUMNS},
            "appellant_type": r["appellant_type"],
        })

    n_allowed = len(diagnostics)
    n_misclassified = sum(1 for d in diagnostics if d["misclassified"])
    print(f"True-allowed cases: {n_allowed}")
    print(f"Misclassified (out-of-fold): {n_misclassified} ({100*n_misclassified/n_allowed:.1f}%)")
    from collections import Counter
    print(f"Misclassified as: {Counter(d['predicted_as'] for d in diagnostics if d['misclassified'])}")
    print()

    # -- Full per-row table -----------------------------------------------------
    print("=== All true-allowed cases, out-of-fold prediction ===")
    print(f"{'case_id':12s} {'predicted_as':16s} {'p(allowed)':10s} {'p(predicted)':12s} {'margin':8s}")
    for d in sorted(diagnostics, key=lambda x: -x["margin"]):
        print(
            f"{d['case_id']:12s} {d['predicted_as']:16s} "
            f"{d['p_allowed']:.3f}      {d['p_predicted']:.3f}        {d['margin']:+.3f}"
        )

    # -- Top N most confidently wrong --------------------------------------------
    wrong = [d for d in diagnostics if d["misclassified"]]
    wrong.sort(key=lambda x: -x["margin"])
    top = wrong[:TOP_N]

    # dataset_v2.csv only stores a 400-char truncated snippet; the full
    # snippet isn't persisted anywhere, so regenerate it the same
    # deterministic way it was computed originally — from the already
    # on-disk cached judgment text, no new scraping/data involved.
    print()
    print(f"=== Top {len(top)} most confidently misclassified true-\"allowed\" cases ===")
    for rank, d in enumerate(top, 1):
        detail = load_cached_judgment(d["case_id"])
        snippet_full = extract_outcome_label(detail.text)["snippet"] if detail else "(raw judgment not cached)"

        print()
        print(f"--- #{rank}: case_id={d['case_id']} ---")
        print(f"Title: {d['title']}")
        print(f"True label: allowed | Predicted: {d['predicted_as']} "
              f"(p_allowed={d['p_allowed']:.3f}, p_{d['predicted_as']}={d['p_predicted']:.3f}, margin={d['margin']:+.3f})")
        print(f"appellant_type: {d['appellant_type']}")
        print("Features: " + ", ".join(f"{k.replace('feature_', '')}={v:.3f}" for k, v in d["features"].items()))
        print(f"label_snippet_full: {snippet_full}")


if __name__ == "__main__":
    main()
