"""Check a passing holdout gate and serving-index parity before deployment."""

import argparse
import hashlib
import json
from pathlib import Path


def verify(data_dir: Path, deployed_precedent_index: Path):
    evaluation = json.loads((data_dir / "evaluation_report.json").read_text(encoding="utf-8"))
    metadata = json.loads((data_dir / "feature_metadata.json").read_text(encoding="utf-8"))
    if not evaluation["promotion_gate_passed"]:
        raise ValueError("Holdout promotion gate did not pass")
    actual_hash = hashlib.sha256(deployed_precedent_index.read_bytes()).hexdigest()
    if actual_hash != metadata["precedent_index_sha256"]:
        raise ValueError("Serving precedent index differs from the evaluated index")
    artifact = (data_dir / f"{evaluation['candidate_version']}.joblib").resolve()
    if not artifact.is_file():
        raise ValueError("Candidate artifact is missing")
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != evaluation["candidate_sha256"]:
        raise ValueError("Candidate artifact changed after holdout evaluation")
    if hashlib.sha256((data_dir / "features.csv").read_bytes()).hexdigest() != evaluation["features_sha256"]:
        raise ValueError("Feature data changed after holdout evaluation")
    if hashlib.sha256((data_dir / "review_queue.csv").read_bytes()).hexdigest() != evaluation["review_queue_sha256"]:
        raise ValueError("Audit signoff changed after holdout evaluation")
    return {
        "OUTCOME_MODEL_PATH": str(artifact),
        "PRECEDENT_INDEX_PATH": str(deployed_precedent_index.resolve()),
        "OUTCOME_MODEL_PRIMARY": "new_model",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--deployed-precedent-index", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.data_dir, args.deployed_precedent_index), indent=2))


if __name__ == "__main__":
    main()
