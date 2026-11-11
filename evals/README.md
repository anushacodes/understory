# Retrieval and answer evaluation

`questions.json` contains 24 reviewed source-location judgments for **synthetic fixture A**: 16 development questions and 8 held-out questions. Each split has two intentionally unanswerable questions. Labels were fixed before comparing retrieval quality; do not tune against held-out results.

The relevance unit is a path plus an inclusive original source interval. A result covers a unit when its path matches and its range overlaps. Count a unit once even if multiple chunks cover it. This simple rubric can give credit to enclosing chunks and does not measure whether the retrieved excerpt alone fully answers a question; claim-support review is separate.

Run from the project root with the local database and the verified local model available:

```sh
uv run --extra embeddings understory-demo
uv run --extra embeddings python -m app.evaluate --split development --output evals/reports/development.json
uv run --extra embeddings python -m app.evaluate --split held_out --output evals/reports/held_out.json
```

All four modes use the same pinned snapshot and questions. Exact search is primarily an identifier baseline, so its aggregate score across natural-language questions is expected to be limited. PostgreSQL lexical search is not BM25. Hybrid scores use RRF, not confidence probabilities.

Reports record corpus identity, effective model/parser/chunker configuration, question-file hash, environment, per-query locations/metrics and timings. Unanswerable questions are excluded from Recall@5/MRR@10; their result lists are retained so a nonempty vector search is not confused with an answerability decision.

Timings are small-sample local measurements, in a fixed mode order, with cold model initialization in the first semantic query. They do not establish production throughput or general model quality. The development baseline currently shows semantic and hybrid are both useful, with semantic slightly ahead on these labels; there is no claim that fusion always improves retrieval.

## Frozen local release targets

These targets are recorded after the initial development report and **before** the first held-out report. They apply to this controlled local MVP, not arbitrary repositories or a hosted SLA:

- Hybrid Recall@5 at least 0.75 and MRR@10 at least 0.75 on the six held-out answerable questions.
- All tested citation IDs, scopes and ranges mechanically valid; zero unauthorized/staging/cross-snapshot evidence in required boundary tests.
- No unsupported or contradicted substantive claims in the reviewed controlled answer demonstrations; both held-out unanswerable cases must express the missing evidence.
- Warm local retrieval p95 below 250 ms in a separately labeled repeat sample; cold semantic startup below 5 seconds on the recorded machine. Report sample counts and initialization separately.
- Generated answers finish or expose a bounded failure under the configured 90-second active execution budget. Provider rate limits are explicit failures/retries, not successful invented results.
- Real calls stay within configured application token reservations. Local embeddings use no external embedding API. Provider billing and paid-plan behavior are not inferred from token totals.

Do not change targets after seeing held-out results. If a target fails, record it and fix the implementation against development/new evaluation data; do not repeatedly optimize to this held-out set.

## Answer review

Review generation separately. For each controlled output, list substantive claims, supporting evidence, unsupported/contradicted claims and evidence gaps. Valid citation references are necessary but insufficient. Include single-file, multi-file, overview and unsupported questions. Deterministic fake-provider tests verify contracts and recovery, while actual Groq demonstrations verify the configured integration; neither replaces the other's evidence.

The final evidence report should include a small real-repository SHA/license, its import coverage, refresh/recovery checks, known limitations and a reproducible demo command sequence. Benchmark JSON files are measurements, not resume improvement claims.
