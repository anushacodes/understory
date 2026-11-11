# Understory — acceptance criteria and evaluation plan

Updated: November 11, 2026. Status: executable acceptance gates, with results and limitations in [VERIFICATION.md](VERIFICATION.md).

These criteria cover repository understanding only. IDs connect product behavior to implementation tasks. “Pass” requires recorded evidence, not a checkbox based on visual inspection alone.

## Controlled evaluation corpus

The fixture design below is implemented in `fixtures/` and the inert adversarial tests. Produce two immutable source snapshots without requiring a Git commit in this workspace; archive contents and recorded SHA identities can be synthetic and must be labeled as such. Any actual Git commit or push requires a specific user request.

| Fixture feature | Snapshot A | Snapshot B / failure variant |
| --- | --- | --- |
| Request flow | `app/api.py` → `app/validation.py` → `app/service.py` → `app/storage.py` | Validation behavior and range change |
| Symbols | Same short function name in two modules; class/method; nested, decorated, async, non-ASCII definitions | One symbol changes; unrelated symbols remain |
| Docs/config | README, Markdown sections, RST sections, `pyproject.toml`, supported JSON/INI/YAML examples | One doc changes; one file remains byte-identical |
| Tests | Static validation and service test files | A test changes; no test execution is claimed by the product |
| Manifest | Supported files plus excluded binary, vendor, secret-like and unsupported-language paths | One file removed, one renamed, one added |
| Invalid inputs | Traversal/link archives, oversized entry, too many files, invalid Python | Unsafe imports rejected; per-file parse failure recorded |
| Connector | Recorded public repo metadata, ref resolution and pinned archive responses | Rate limit, timeout, invalid ref, lost connection, malicious redirect |
| Model adapter | Deterministic fake embeddings and scripted answer outputs | Timeout, malformed output, invalid citation, budget exhaustion |

Unsafe fixtures are inert test data. The application never executes imported content. Real provider behavior is evaluated separately from fake adapters.

Create 24 labeled questions before retrieval tuning: 16 development questions and 8 held out. Include identifier, conceptual, multi-file, documentation/configuration, and unsupported questions. Reserve at least two unanswerable questions in each split. Each answerable question names acceptable evidence units as `(snapshot, path, symbol/section or line interval)`; label alternatives where more than one passage is valid. Relevance labels must not be produced solely by the system being evaluated.

## Import and execution gates

| ID | Scenario | Required result | Verification |
| --- | --- | --- | --- |
| IMP-01 | Import an allowed public repository at a ref | Job records requested ref and resolves one SHA before source download; retries reuse that SHA | Connector fixture and persisted rows |
| IMP-02 | Repeat the same idempotency key and body; then change the body | Same job is returned for the replay; changed input returns `409` | API/database integration |
| IMP-03 | First import or refresh fails midway | Staging content is unsearchable; previous active snapshot remains; failure stage is visible | Integration with injected failures |
| IMP-04 | Replay a completed batch/import | No duplicate source versions, passages, embeddings, or memberships under their declared identities | Unique constraints and row-count assertions |
| JOB-01 | Stop worker after a committed checkpoint and restart | Job resumes after lease expiry/reclaim; transient files can be rebuilt at the pinned SHA | Real PostgreSQL recovery scenario |
| JOB-02 | Old worker resumes after another worker reclaims | Old token cannot checkpoint, emit progress, complete, or activate | Two controlled worker attempts |
| JOB-03 | Older import finishes after a newer import request | Only the latest requested activation generation may change the active pointer; old result remains retained and ready | Controlled completion ordering |
| JOB-04 | Cancel queued or running work | Queued work stops; running work observes cancellation at the next bounded checkpoint; no partial activation/output | API/worker integration |
| JOB-05 | Retry transient failures and exhaust attempts | Bounded delay/attempts; persisted retry time and error; permanent validation errors do not retry | Clock-controlled integration |
| EVT-01 | Disconnect progress client and reconnect with event ID | Ordered committed events replay without gaps; client deduplicates IDs | SSE integration and browser flow |
| EVT-02 | Worker offline or event history expired | Job reports queued/availability state; expired replay returns reset instructions while job state remains readable | API/browser checks |

## Parsing, sources, and versions

| ID | Scenario | Required result | Verification |
| --- | --- | --- | --- |
| SRC-01 | Parse nested/decorated/async/non-ASCII Python | Qualified names, parent identities, and inclusive original line ranges resolve correctly | Parser unit fixtures |
| SRC-02 | Parse docs and supported configs | Excerpts preserve original text and line ranges; config handling does not execute constructors or interpolation | Parser fixtures |
| SRC-03 | Inspect coverage and excluded files | Counts reconcile with manifest; unsupported, secret-like, binary, large, generated, and parse-error reasons are distinct | Manifest/inventory assertions |
| SRC-04 | Import no supported content or a parse-error file | Empty corpus is explicitly marked and generation is unavailable; individual parse errors produce visible partial coverage | Import/API checks |
| VER-01 | Import B after A | B reflects additions/changes/deletions/renames; A stays readable; unchanged compatible embedding inputs reuse vectors | Two-snapshot integration |
| VER-02 | Change embedding/chunking configuration | Incompatible vectors are never reused; effective model identity/dimensions/configuration are recorded | Cache/configuration assertions |
| VER-03 | Activate B while a request uses A | Search result, answer evidence, viewer, and links all continue to use A | Barrier-controlled concurrent requests |
| VER-04 | Reopen/export an older answer | Same retained text, source version, SHA, ranges, model configuration, and evidence selections | Export consistency check |

## Retrieval and answering

| ID | Scenario | Required result | Verification |
| --- | --- | --- | --- |
| RET-01 | Exact/prefix lookup with duplicate short names | Correct qualified symbols returned separately; bounded results and stable tie ordering | Labeled symbol cases |
| RET-02 | Search all modes with source/path filters | Each mode applies repository/snapshot/source filters before selecting results; staging/other repositories never appear | Retrieval integration |
| RET-03 | Query with no relevant evidence | Empty search response; no assertion that a behavior is absent everywhere | API and wording review |
| RET-04 | Embedding service unavailable | Exact/lexical work; semantic/hybrid return unavailable unless caller explicitly permits lexical fallback, which is labeled | Provider failure checks |
| RET-05 | Evaluate exact, lexical, semantic and hybrid | Same pinned corpus/split; Recall@5 and MRR@10, declared relevance mapping, configuration and timing reported | Reproducible evaluation artifact |
| ANS-01 | Answerable single-file and multi-file questions | Substantive factual claims have supporting citations; uncertainty about runtime behavior is explicit | Scripted validation plus human review |
| ANS-02 | Question outside indexed evidence | `insufficient_evidence` or supported partial answer with specific gaps; no invented path or repository-wide absence claim | Unanswerable cases and review |
| ANS-03 | Output contains invalid/cross-scope citation | Output is not published as valid; bounded repair may occur, otherwise fail with structured error | Adversarial adapter fixture |
| ANS-04 | Provider timeout, invalid output, or exhausted budget | Persisted failed run/job with reason; no successful fabricated result; usage recorded | Failure injection |
| ANS-05 | Generate overview | Inventory remains available independently; generated module/entry-point statements cite inspected sources | Overview review |
| ANS-06 | Open source containing instruction injection | Source stays untrusted evidence; cannot authorize tools, reveal secrets, or alter scope | Injection fixtures and boundary checks |

## UI and access boundaries

| ID | Scenario | Required result | Verification |
| --- | --- | --- | --- |
| UI-01 | Complete import → overview → search → source → question | Selected repo/SHA and coverage stay visible; all citation clicks open the correct range | Browser critical path |
| UI-02 | Refresh browser during an accepted job | Job and run can be reopened without depending on in-memory progress | Browser reconnect/reload |
| UI-03 | Ready, indexing, retry, partial, empty, unavailable, failed states | Each state has accurate copy and an appropriate next action | Browser fixtures/manual review |
| UI-04 | Navigate with keyboard and render malicious source | Controls are labeled/focusable; code is text; untrusted HTML/scripts do not execute | Accessibility and rendering checks |
| UI-05 | Compare selected landing, dashboard and theme boards with implementation | Wordmark/fonts, palette, hierarchy, three-pane desktop composition and citation/highlight treatment follow [Understory.html](../Understory.html) and [UI_REFERENCE.md](UI_REFERENCE.md); narrow widths retain pane/citation access and reduced motion is honored | Reference-size desktop and narrow-screen captures; theme and keyboard review |
| UI-06 | Reconcile reference mock content with actual capabilities | No issue/PR UI, fabricated activity, executed-test claim, unsupported caller graph or implied conversation memory; displayed controls work and data/mode/baseline are real | UI content/control review and fixture-driven browser checks |
| SEC-01 | Missing/wrong owner credential or mismatched resource scope | Every repo/source/job/run/export action enforces access; guessed identifiers disclose no source content | Negative API tests |
| SEC-02 | Unsafe host, redirect, archive path/link, archive bomb | Rejected within limits; no writes outside extraction area and no unintended network targets | Inert adversarial fixtures |
| SEC-03 | Oversized request or concurrent work exceeds limit | Bounded rejection with structured reason; no unbounded memory/provider usage | Boundary integration |
| SEC-04 | Inspect frontend and application logs | No server/provider credentials; source bodies and owner token are redacted by default | Build/log review |
| OPS-01 | Export then owner-purge a repository | Export is self-describing; authorized purge removes dependent data and unused vectors; other repositories survive | Two-repository integration |
| OPS-02 | Restart from documented local setup | Migrations, API, worker, frontend, fake-provider mode and optional real-provider configuration are reproducible | Clean environment walkthrough |

## Evaluation rules and release evidence

Retrieval metrics apply to answerable questions. For each result, map chunks to the labeled evidence units and count each unit once. Recall@5 is the fraction of relevant units covered by the first five results; MRR@10 uses the first relevant result within ten. Report unanswerable cases separately. Publish per-query results so averages do not hide a broken category.

For generation, split each answer into substantive repository claims and label each supported, unsupported, contradicted, or explicitly uncertain. Report citation-reference validity separately from claim support. Record appropriate abstention on unsupported questions. Fake-adapter passes demonstrate contract behavior, not real retrieval or generation quality.

Mandatory mechanical gates have zero tolerance for invalid citations, cross-snapshot leakage, unauthorized reads, duplicate identity rows, and stale-worker publication. For the controlled release demonstration, no contradicted or unsupported substantive claims may remain in the reviewed outputs, and all labeled unanswerable cases must express the evidence gap.

Numeric retrieval-quality, latency and model-cost thresholds were frozen in [evals/README.md](../evals/README.md) before the held-out report. After the first development baseline, record proposed thresholds and rationale before running the held-out set. Freeze them before release evaluation. If hybrid does not improve over the baseline, report that result; do not invent an improvement or repeatedly tune against held-out questions.

Evidence bundle: fixture/archive hashes and real-repo SHA when available; question split/labels; parser/chunker/model identities; environment; per-query metrics; citation/claim review; warm/cold timings with sample counts; provider consumption; recovery and boundary results; unresolved limitations. Report p50/p95 only with sample sizes and describe small-sample uncertainty.

## Additional hosted-showcase gate

Hosting is not required for the local MVP. Before calling a hosted showcase ready, verify persistence/migrations, credential storage, owner authentication over TLS, worker-offline behavior, backups/restore procedure, provider/data-transmission policy, and actual host/model costs and spending controls. If anonymous visitors are added, design and verify separate read/query authorization, rate limits, and private answer visibility first.

No deployment or paid-service activation is authorized by this planning document. Implementation tasks and gate dependencies are in [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md).
