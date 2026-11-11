# Local MVP verification

Recorded November 11, 2026. This is a local owner-operated release, with a private source remote. Hosting, anonymous access, private-repository ingestion and MCP were not implemented or deployed. Tests use the actual local PostgreSQL/pgvector service; deterministic provider tests never call external generation.

## Results and reproduction

- Backend: **75 tests passed**, covering actual migrations in isolated PostgreSQL schemas, parser/archive boundaries, imports, fencing, retry accounting, subprocess crash recovery, answer validation, owner enforcement, retention and purge.
- Frontend: production TypeScript/Vite build passed. **15 of 15 browser cases passed in the final full run**: seven desktop and seven mobile workspace cases, plus one desktop stopped-worker/reload case. Earlier runs exercised actual Groq generation. The final full run replayed a successful question through its original idempotency key to preserve quota; all source/history/export/navigation checks still used the live application. The mobile question case passed after correcting a reauthentication test wait. No skipped cases are being counted as passes.
- Real Groq: single-file, multi-file, overview and two unsupported-question demonstrations completed. Desktop/mobile browser questions also completed. Raw source/usage exports are in [live.json](../evals/reports/live.json). No credentials are included.
- Real source: ItsDangerous **2.2.0**, SHA `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd`; 60 inventoried files, 41 included, 19 excluded, zero parse failures, 297 passages, 145 symbols; about 23 seconds for this one cold import. Exclusions remain visible. Source was read, never executed.
- Restore: [restore.json](../evals/reports/restore.json) records an actual custom-format dump restored into a disposable database, matching retained row counts and zero invalid evidence memberships/ranges.
- Themes and responsive source navigation: final screenshots in [screenshots](screenshots/). These are representative captures, not a claim of pixel-identical rendering at every size.

Commands and prerequisites are in [README](../README.md) and [operations](OPERATIONS.md). The release browser run enables `UNDERSTORY_LIVE_TESTS=1` and supplies only this project's worker PID; default browser runs skip explicit live/recovery cases to avoid hidden quota consumption or pausing an unrelated process.

One dependency warning remains: the installed Starlette test client deprecates its current httpx transport. It does not fail the suite; dependency migration is a follow-up rather than an unverified lockfile change. The CLI's color-environment warning is cosmetic.

## Retrieval measurements

Labels: 24 questions, 16 development / 8 held out, two unanswerable in each split. Relevance is path plus overlapping source interval, deduplicated per unit. It gives credit to enclosing excerpts and is not a measure of full answer support. Unanswerable questions are excluded from retrieval averages.

Targets were frozen in [evals/README.md](../evals/README.md) before the first held-out report. No ranking tuning was done against that report.

| Mode | Development Recall@5 / MRR@10 (14 answerable) | Held-out Recall@5 / MRR@10 (6 answerable) |
| --- | --- | --- |
| Exact | 0.357 / 0.357 | 0.167 / 0.167 |
| Lexical | 0.726 / 0.786 | 0.833 / 0.750 |
| Semantic | 0.940 / 0.899 | 1.000 / 0.875 |
| Hybrid | 0.929 / 0.893 | 1.000 / 0.867 |

[Development report](../evals/reports/development.json), [held-out report](../evals/reports/held_out.json). Hybrid passed the frozen 0.75/0.75 targets; semantic MRR was slightly higher. There is no claimed universal hybrid improvement.

[Separate warm measurement](../evals/reports/warm.json): 80 sequential hybrid queries on synthetic A, macOS ARM64, warm p50 **11.08 ms**, p95 **27.35 ms**; cold initialization **1,135 ms**. Both passed the local targets (warm p95 <250 ms, cold <5 s). This is single-machine, sequential, small-corpus timing, not concurrent throughput or an SLA.

## Source-support review of actual Groq output

Reviewer: Codex, through direct comparison of the retained output and supplied evidence. This is an assistant-performed qualitative review, not an independent human annotation study. A reader can repeat it from [live.json](../evals/reports/live.json) and the fixture source. Mechanical citation validity and semantic support are separate checks.

| Case | Claims reviewed | Source support and limits |
| --- | --- | --- |
| Single file | Nonempty string account ID; positive integer amount in cents | `app/validation.py` and README validation section. No runtime/executed-test claim. |
| Multiple files | API validates then delegates; service retains store and calls append; store copies payload and returns receipt | `app/api.py`, `app/service.py`, `app/storage.py`, with per-step evidence IDs. |
| Overview | Synthetic Ledger purpose; documented request/service/store flow; static API and formatting definitions | README and static excerpts. The formatting role/core-flow wording is a summary inference from the documented flow, not a resolved runtime graph. Missing detailed module excerpts are explicitly disclosed. |
| Held-out 07 | Production encryption key cannot be supplied from selected evidence | `insufficient_evidence`; no invented credential. |
| Held-out 08 | Latest PR reviewer cannot be established | `insufficient_evidence`; no invented reviewer or live GitHub discussion claim. |

No contradicted substantive source claims were identified in this small review. Runtime usage and repository-wide negative claims are not established by it. Overview wording includes a qualified architectural inference, which should not be repeated in an interview as runtime proof. An independent human support study has not been conducted; no general factual-accuracy percentage is claimed.

The five saved demonstration jobs took roughly 1.6–5.4 seconds each. One 429 triggered a retry. Its first call has unknown usage and retains a 9,200-token reservation; known calls record actual consumption. These are application token records, not a dollar-cost measurement or guarantee of free-tier availability. The 90-second active deadline excludes queue/backoff time and can be observed only at bounded checkpoints.

## Acceptance evidence map

“Covered” means the listed controlled scenario was exercised; it does not claim arbitrary repositories/providers are proven correct.

| Gates | Evidence | Result / qualification |
| --- | --- | --- |
| IMP-01 | `test_connectors.py`, `test_process_recovery.py`, real import in `live.json` | Canonical provider identity and full SHA pinned; retry reuses SHA; real pinned archive imported. |
| IMP-02 | `test_jobs.py::test_idempotency_replay_and_conflict`, answer omitted-snapshot replay test | Replay preserves original job/baseline; changed body conflicts. |
| IMP-03 | `test_imports.py::test_mid_import_storage_failure_keeps_staging_hidden` | Mid-import failure keeps prior active snapshot; staging cannot be read as ready. |
| IMP-04 | Same-SHA import and subprocess recovery tests | Source/passages/memberships deduplicate under declared identities. |
| JOB-01 | `test_process_recovery.py` | Real subprocess exits after committed batches, then lease reclaim completes. |
| JOB-02 | Reclaimed-lease test in `test_jobs.py` | Old token cannot checkpoint or perform guarded publication writes. |
| JOB-03 | Activation-order test in `test_jobs.py` | Newest requested generation controls active pointer; older result remains historical. |
| JOB-04 | Queued API cancellation and running-import cancellation tests | Cooperative cancellation prevents partial activation. |
| JOB-05 | Retry/deadline tests, `test_providers.py`, real 429 | Bounded attempts/backoff; active budgets persist across retries; malformed output fails closed. |
| EVT-01 | API durable replay test; fetch/SSE browser question flows | Ordered committed sequences replay; client ignores duplicate IDs. |
| EVT-02 | `test_maintenance.py`, `recovery.spec.ts` | Expired history returns 410; stopped worker distinct from queued state; job remains readable. |
| SRC-01 | `test_indexing.py` | Nested, decorated, async and non-ASCII ranges/parents verified. |
| SRC-02 | Parser docs/config tests | Original line ranges retained; YAML/config is text, never executed. |
| SRC-03 | Archive/source-policy/import tests; real coverage report | Inventory and exclusion reasons reconcile; binary/secret/unsupported/large/parse-failed paths distinguished. |
| SRC-04 | Empty parse-failed corpus test | Explicit empty coverage, no results, generation refused. |
| VER-01 | A/B import and embedding refresh tests | Deletion/rename/change handling; A retained; compatible inputs reuse vectors. |
| VER-02 | `test_embeddings.py` | Input/assets/dimensions/preprocessing identity; old incompatible semantic queries fail or explicitly fall back. |
| VER-03 | Mid-generation B activation test | Answer remains pinned to A with exact original source evidence. |
| VER-04 | Browser history/export/reload; immutable evidence tests | Saved output, baseline, excerpts, configuration and usage retained. |
| RET-01 | Parser duplicate symbols, exact search/browser and evaluation labels | Qualified identities and separate short-name matches preserved. |
| RET-02 | API kind/path filters, snapshot/source constraints, four-mode reports | Filters precede candidate selection; scopes and ready membership enforced. |
| RET-03 | Empty corpus and lexical/exact search cases; unanswerable report rows | Empty results do not establish repository-wide absence; vector matches alone do not prove answerability. |
| RET-04 | API unavailable/fallback and changed-assets tests | Exact/lexical available independently; explicit labeled degradation only. |
| RET-05 | Development, held-out and warm reports | Same pinned corpus and fixed labels; per-query results included. |
| ANS-01 | `test_answers.py`, actual single/multi-file report and qualitative review above | Valid selected citations and source-backed controlled claims; no independent human accuracy study. |
| ANS-02 | Real held-07/08 plus strict output schema | Both unsupported questions express evidence gaps without invented facts. |
| ANS-03 | Unknown evidence ID, cross-scope DB and malformed-output tests | Invalid output is not published; no automatic repair call. |
| ANS-04 | Provider error/JSON tests, budget-prevention test, real 404/429 history | Failures remain durable and structured; unknown usage remains reserved. |
| ANS-05 | Real overview, inventory and history browser tests | Inventory independent of Groq; overview cites inspected/documented sources and exposes gaps. |
| ANS-06 | Untrusted-data system prompt, no provider tools, inert config/archive fixtures | Source has no tool authority; no autonomous tool loop exists. This does not prove immunity to every semantic prompt injection. |
| UI-01 | Desktop/mobile browse/search/ask/citation/export flows; actual import API check | Selected baseline and exact citation ranges maintained across core workflow. |
| UI-02 | Desktop stopped-worker reload test; question reauthentication/history test | Accepted job and saved answer survive refresh with owner reauthentication. |
| UI-03 | Actual ready/partial/queued/offline/cancelled/failed states; API empty/fallback/provider failure fixtures | State copy and next actions implemented; not every provider failure is visually snapshotted. |
| UI-04 | Keyboard/reduced-motion tests and malicious source rendering test | Visible focus, labeled controls and source markup rendered as text. Not a full WCAG certification. |
| UI-05 | Supplied fonts/assets, theme screenshots and narrow-screen checks | Meadow/three-pane design preserved; narrow panes remain navigable. |
| UI-06 | Actual API data and content/control review | No issue/PR features, invented activity, executed-imported-test claim or chat-memory promise. |
| SEC-01 | All-data-route owner test, foreign-owner/foreign-snapshot tests | Unauthenticated reads/writes rejected; guessed foreign resources disclose no source. |
| SEC-02 | Archive and canonical-connector tests | No arbitrary hosts/redirects, traversal, links, duplicate paths or unbounded decompression. |
| SEC-03 | Chunked request, archive/source/storage, queue capacity, generation budget tests | Bounded rejection with persisted errors; source-byte limit differs from physical disk use. |
| SEC-04 | Memory-only owner token, ignored `.env`, build/log inspection | No server/provider keys in tracked files, build or normal logs; API query access logs disabled. |
| OPS-01 | Two-repository purge and usage-bearing export tests/browser | Other repository survives; referenced data retained until explicit purge; unused vectors collected. |
| OPS-02 | Actual migration/start/demo workflow, production build and restore drill | Local setup documented and exercised; optional model downloads need initial network access. |

## Delivery limitations

This is a bounded local MVP for small public Python repositories. The exact vector scan, single worker, source-byte ceiling and manual maintenance are deliberate local choices. Provider quotas and account model availability can change. The application does not execute imported tests, resolve a complete runtime graph, provide chat memory or establish that every repository file was inspected. Semantic claim support needs review even when citation IDs and ranges are valid.
