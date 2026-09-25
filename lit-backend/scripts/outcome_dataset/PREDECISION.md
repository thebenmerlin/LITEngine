# Pre-decision outcome experiment

The confirmed 187-case judgment-derived result remains the incumbent. This workflow requires **new, separate pre-decision text** for at least 300 cases. Cached judgments in `raw_cache/` are not accepted as feature input.

## Input files

Create a UTF-8 CSV manifest and keep its text files beneath the manifest directory. Required columns:

```csv
case_id,matter_id,text_path,filing_date,decision_date,court,appellant_type,outcome,input_verified,outcome_verified
case-001,matter-001,filings/case-001.txt,2020-01-15,2022-06-01,High Court,accused_appeal,succeeds,true,true
```

`matter_id` groups related appeals so they cannot cross the train/holdout split. Dates use `YYYY-MM-DD`. `outcome` is `dismissed` or `succeeds` (full or partial relief). `appellant_type` is `accused_appeal`, `state_appeal`, or `unclear`. The intake process sets `input_verified` only after checking source provenance and that the text predates the decision; it sets `outcome_verified` only after cross-checking the final order. These checks can be automated from authoritative records, with a manual audit of ambiguous cases and a sampled training/holdout batch. The importer flags obvious disposal phrases for a further audit in `feature_metadata.json`; that check cannot prove absence of leakage.

Build a separate precedent manifest with `doc_id,matter_id,title,text_path,decision_date,court,url`. Each text file contains a published judgment. The index builder stores dates and matter IDs, enabling strict `decision_date < filing_date` filtering and related-matter exclusion.

## Commands

From `lit-backend/`:

```bash
./venv/bin/python -m scripts.outcome_dataset.build_precedent_index --manifest /path/to/precedents.csv --output /path/to/dated_precedents.json
./venv/bin/python -m scripts.outcome_dataset.build_predecision --manifest /path/to/filings.csv --precedent-index /path/to/dated_precedents.json --output-dir data/outcome_dataset/predecision/v1
./venv/bin/python -m scripts.outcome_dataset.train_predecision --data-dir data/outcome_dataset/predecision/v1
./venv/bin/python -m scripts.outcome_dataset.evaluate_predecision --data-dir data/outcome_dataset/predecision/v1
./venv/bin/python -m scripts.outcome_dataset.verify_promotion --data-dir data/outcome_dataset/predecision/v1 --deployed-precedent-index /path/to/dated_precedents.json
```

The build command uses the same extraction service as the app; pass `--rules-only` only when evaluating a rules-only browser configuration. The builder refuses mixed extraction methods and writes `review_queue.csv` with 25 training cases, 25 holdout cases, and every obvious outcome-cue flag. Review each queued filing and outcome, then set `reviewed=yes` and `issue_found=no`. Resolve any issue in a new dataset version. Training refuses an unsigned audit. Keep the exact dated precedent index used for evaluation in serving. The evaluation command refuses to score a holdout twice; a failed promotion requires new cases and a new dataset version.

The final command prints environment variables for a gated artifact only when the holdout gate passes and the serving index hash matches. It does not deploy or change the active model. When `PRECEDENT_INDEX_PATH` is set, the live index is frozen: the indexing endpoint is disabled and shutdown does not rewrite it. The existing `OUTCOME_MODEL_PRIMARY` setting and heuristic fallback remain available. With no staged filings, no candidate artifact or holdout score can be produced.
