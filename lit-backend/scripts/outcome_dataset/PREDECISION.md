# Pre-decision outcome experiment

The confirmed 187-case judgment-derived result remains the incumbent. This workflow requires **new, separate pre-decision text** for at least 300 cases. Cached judgments in `raw_cache/` are not accepted as feature input.

## Public collection status (25 September 2026)

The public-source pilot found one original criminal special-leave petition posted by the [Internet Freedom Foundation](https://internetfreedom.in/the-supreme-court-refuses-special-leave-petition-challenging-the-unconstitutional-retention-of-mobile-data-of-journalists/). Its PDF states `FILED ON: 22.12.2022` and contains 1,553 OCR words across nine pages. The downloaded PDF SHA-256 is `72d4601764dfb6e603f2b6704e8c8b1df515bb493b50a68aab71afbf3ea5bc87`. The collection command below downloads it to ignored local storage and records the PDF/text SHA-256 hashes, source URL, page count, extraction method, and leakage cue flag. It intentionally marks the case `candidate_only`: the linked article reports a dismissal but gives a decision date that has not been confirmed against an official order. The case has no verified outcome and is excluded from training. The seed is a source pointer, not a verified training row.

```bash
./venv/bin/python -m scripts.outcome_dataset.collect_public_filings \
  --seeds scripts/outcome_dataset/public_filing_seeds.csv \
  --output-dir data/outcome_dataset/predecision/candidates/public_v1
```

The Supreme Court's [Office Reports](https://www.sci.gov.in/office-report-case-no/) are public, but a sampled [fresh-case report](https://api.sci.gov.in/officereport/2024/42100/42100_2024_2024-11-29_2684.html) listed filing dates and procedural entries without the petition's facts or arguments. It cannot be substituted for an original petition. The Court's [e-filing FAQ](https://efiling3.sci.gov.in/resources/FAQ) describes document access through registration or a copying application, so the public office-report site is not a bulk petition corpus. Existing public judgment datasets, including [ILDC](https://exploration-lab.github.io/IL-TUR/docs/tasks/court-judgment-prediction-with-explanation-cjpe/) and [TathyaNyaya](https://github.com/ShubhamKumarNigam/TathyaNyaya-and-FactLegalLlama), derive inputs from final judgments and do not meet this experiment's predecision provenance requirement. These findings explain why the pilot has not produced a training manifest or new accuracy score.

To expand the corpus, add links to original predecision petitions or independently published predecision case summaries to the seed CSV. For each case, verify the document's filing date and matter identity, obtain its final court order, verify dismissal versus full/partial relief and appellant direction, then create a `filings.csv` training manifest. Keep ambiguous and still-pending matters as candidates. The 300-case and review gates below remain mandatory.

## Input files

Create a UTF-8 CSV manifest and keep its text files beneath the manifest directory. Required columns:

```csv
case_id,matter_id,text_path,filing_date,decision_date,court,appellant_type,outcome,input_verified,outcome_verified
case-001,matter-001,filings/case-001.txt,2020-01-15,2022-06-01,High Court,accused_appeal,succeeds,true,true
```

`matter_id` groups related appeals so they cannot cross the train/holdout split. Dates use `YYYY-MM-DD`. `outcome` is `dismissed` or `succeeds` (full or partial relief). `appellant_type` is `accused_appeal`, `state_appeal`, or `unclear`. The intake process sets `input_verified` only after checking source provenance and that the text predates the decision; it sets `outcome_verified` only after cross-checking the final order. These checks can be automated from authoritative records, with a manual audit of ambiguous cases and a sampled training/holdout batch. The importer flags obvious disposal phrases for a further audit in `feature_metadata.json`; that check cannot prove absence of leakage.

Build a separate precedent manifest with `doc_id,matter_id,title,text_path,decision_date,court,url`. Each text file contains a published judgment. The index builder stores dates and matter IDs, enabling strict `decision_date < filing_date` filtering and related-matter exclusion. The cached Indian Kanoon judgments may be used for this **precedent corpus only**. They are never acceptable as the pre-decision case inputs. A filing that corresponds to a cached judgment must use a matching `matter_id` (or have the relationship reviewed and mapped) so that its own judgment and companion matters are excluded.

The cached corpus can be staged locally with:

```bash
./venv/bin/python -m scripts.outcome_dataset.prepare_precedent_corpus --output-dir data/outcome_dataset/predecision/precedents/v1
./venv/bin/python -m scripts.outcome_dataset.build_precedent_index --manifest data/outcome_dataset/predecision/precedents/v1/precedents.csv --output data/outcome_dataset/predecision/precedents/v1/dated_index.json
```

The staging command rejects undated or incomplete documents, collapses near-duplicate judgments, and records source hashes. `matter_id` defaults to the surviving Indian Kanoon document ID; related appeals under different IDs still need a case-level linkage audit. The dated index remains local until a candidate passes the frozen holdout gate and the identical index is configured in serving.

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

The final command prints environment variables for a gated artifact only when the holdout gate passes and the serving index hash matches. It does not deploy or change the active model. When `PRECEDENT_INDEX_PATH` is set, the live index is frozen: the indexing endpoint is disabled and shutdown does not rewrite it. The existing `OUTCOME_MODEL_PRIMARY` setting and heuristic fallback remain available. A precedent index alone does not supply training examples: without at least 300 verified, independent pre-decision filings and outcomes, no candidate artifact or holdout score can be produced.
