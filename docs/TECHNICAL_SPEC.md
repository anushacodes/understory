# Understory — initial technical specification

Updated: November 10, 2026. Status: proposed implementation contract, not running software.

Product authority: [MVP_SCOPE.md](MVP_SCOPE.md). Verification authority: [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md). Changes to a contract should update its acceptance criteria and dependent backlog items together.

## Architecture and responsibilities

Use a modular application with a Python API, a separate Python worker, a static web frontend, and one PostgreSQL database with vector support. The API and worker share application services. PostgreSQL holds durable jobs/events and indexed content; no separate queue service is required.

| Component | Responsibility |
| --- | --- |
| Web workspace | Owner session, repository/snapshot selection, import progress, inventory, search, source viewing, questions and exports |
| API | Authentication, validation, resource scope, bounded reads, enqueue operations, event replay and output serialization |
| Worker | Safe imports, parsing/chunking/embedding, overview/answer jobs, leases/checkpoints and atomic publication |
| Retrieval service | Shared scoped symbol/lexical/vector retrieval and bounded evidence assembly |
| Answer service | Structured provider input/output, citation validation, limitations, run persistence |
| GitHub connector | Public repository validation, ref resolution, pinned archive retrieval; no issue or PR APIs |
| Model adapters | Embedding and generation interfaces, effective model identity, timeouts, usage and errors |
| PostgreSQL | Immutable source versions, snapshots/manifests, indexes, jobs/events, answer evidence and usage |

Retain the existing proposed stack: Python 3.12+; FastAPI/Pydantic; SQLAlchemy/psycopg/Alembic; Python AST; httpx; React/TypeScript/Vite; pytest/PostgreSQL integration checks/Playwright; uv/npm and local container tooling. These are technology choices, not verified version compatibility. Select supported versions and consult current documentation when producing dependency/configuration code. No hosted database, inference provider, or auth service has been selected.

No autonomous tool loop is needed. Questions use bounded retrieval → evidence assembly → generation → validation. There is no repository code execution, issue research, or second scheduler.

## Frontend design contract

The user-supplied [Understory.html](../Understory.html) is the visual reference. [UI_REFERENCE.md](UI_REFERENCE.md) captures its landing, logo, three-pane dashboard, fonts and light/dark palettes. Preserve the desktop repository/question/evidence composition and extend it for overview, search, import progress and missing states. Treat its custom bundled template/runtime as reference packaging; the application uses the chosen frontend stack.

The reference does not authorize issue features, a call graph, executed tests or chat memory. Omit issue UI/copy; label test-source inspection and independent questions accurately. Numbered citations in the question pane map to matching source gutter markers/ranges in the evidence pane. Activity comes from actual job/retrieval/read metadata, never mock counts or hidden model reasoning. Preserve reduced-motion behavior and supply visible focus states. Responsive pane navigation and final theme behavior require definition before frontend work. UI-05/06 verify fidelity and scope reconciliation.

## Access and operating assumptions

Proposed local default: one owner token configured server-side; API binds to loopback; browser submits the token at runtime and retains it only in memory. All repository, source, job, answer and export routes require that identity. Credentials never appear in frontend build variables, URLs, logs, source exports, or local storage. Limit CORS to the configured frontend origin. `/health` is unauthenticated and contains no details; `/ready` returns minimal status without credentials or source data.

This is a local-development access model. A hosted release must choose and verify remote owner authentication and TLS before deployment; a reusable owner secret embedded in a web bundle is prohibited. A later anonymous showcase needs a separate access/abuse design. Repositories and every dependent resource carry an owner/access scope even while there is only one owner.

## Identity and data model

IDs are opaque strings. Commit SHAs are fully resolved source identities. Hashes are application-computed content/configuration hashes. Line ranges use original stored UTF-8 text, 1-based inclusive lines. Non-UTF-8 files are inventoried as unsupported in the baseline. Ranges must include decorators where applicable and remain correct for non-ASCII content and original newline conventions.

| Entity | Required fields and identity | Invariants |
| --- | --- | --- |
| `repositories` | ID, owner scope, canonical GitHub owner/name/provider repo ID, requested default ref, active snapshot ID, latest requested activation generation | Unique provider identity within scope; active snapshot belongs to this repository and is ready |
| `snapshots` | ID, repository ID, full SHA, indexing config hash, staging/ready/failed state, manifest summary, indexed time, empty/partial coverage | Unique `(repository, SHA, indexing_config_hash)`; config includes parser/chunker and embedding identity; ready contents are immutable |
| `source_versions` | ID, repository ID, normalized path, content hash, immutable original bytes/text, source kind, encoding, line count | Unique `(repository, path, content_hash)`; same text at another path is another placement/version |
| `snapshot_files` | Snapshot, path, optional source version, bytes/hash when available, inclusion state and reason | Unique `(snapshot, path)`; includes excluded-path inventory without retaining excluded bodies; deleted paths absent in the next manifest |
| `symbols` | Source version, parser config, qualified name, kind, parent, start/end lines, local ordinal | Qualified names alone need not be unique; overloads/redefinitions retain distinct placements |
| `passages` | Source version, parser/chunker config, symbol/section, ordinal/range, source excerpt, embedding input hash | Unique structural placement/config identity; original text separate from embedding input |
| `embedding_cache` | Embedding input hash, provider/model/revision, dimensions, preprocessing config, vector | Unique compatible input/config identity; no reuse across incompatible identities |
| `passage_embeddings` | Passage, embedding configuration, cache entry | Scoped associations; staged snapshots cannot leak through shared cache rows |
| `jobs` | ID, scope/repository, kind, status/stage, request, generation if import, resolved SHA if import, attempts, lease token/expiry, checkpoint, retry time, cancellation, error | Fenced writes; idempotency and request hash retained; a repeated call can incur repeated external requests but not duplicate application identities |
| `job_events` | Job ID, monotonic event sequence, timestamp, event kind, bounded payload | Unique `(job, sequence)`; event commit precedes delivery |
| `answer_runs` | ID, owner/repository/snapshot, kind question/overview, optional question, status/job, retrieval/provider config, output, gaps/limitations, timestamps | Snapshot pinned at enqueue; successful output immutable |
| `run_evidence` | Run ID, local evidence ID, source version, path/symbol, original range/excerpt, retrieval metadata | Unique `(run, evidence ID)`; selections pinned before generation and same repository/snapshot as run |
| `usage_events` | Request/job/run/call IDs, provider/config, reservation, known usage, attempted/settled/unknown outcome, timing | Usage accounting does not assume exactly-once provider invocation |

Use foreign keys and scoped uniqueness/composite checks to prevent mismatched repository/snapshot/source associations. A run evidence row must reference a source version in that run's snapshot manifest. Source versions can be shared by retained snapshots. Generated overviews are answer runs, not source evidence. Model prose never becomes an indexed repository fact.

Snapshot configuration declares capabilities: `inventory`, `lexical`, or `hybrid`. An inventory-only milestone snapshot exposes inventory but cannot serve search or generation. A lexical configuration requires valid parsed sources/passages but no embeddings; it supports exact/lexical search. A hybrid configuration additionally requires compatible vectors for every eligible passage before activation. The completed MVP uses hybrid snapshots. A feature requiring unavailable snapshot capabilities returns `409 snapshot_capability_unavailable`; it never treats incomplete indexing as ready for that feature. Configuration changes produce separate snapshot identities rather than mutating ready contents.

Store the full effective indexing configuration, not only its hash. Changing parser/chunker or embedding configuration creates a new compatible snapshot identity. An already ready matching snapshot can be reused by a new import job, but activation still checks that job's requested generation. Failed staging work may be rebuilt idempotently after its old job is terminal; concurrent matching builds must serialize on the same snapshot identity.

Initial lexical search is PostgreSQL full-text search plus symbol/identifier normalization; do not label it BM25. Start with exact vector scans for the bounded corpus. An approximate index requires evidence of need.

## Source policy and proposed budgets

These are configurable starting limits for the local fixture/small-repository baseline, not measured capacity or provider pricing. Limits apply server-side. Record the effective values in import/run metadata. Review them against the first fixture before accepting a real repository.

| Limit | Proposed default | Behavior at limit |
| --- | --- | --- |
| Repository access | Explicit repository allowlist; GitHub public repositories only | Reject unsupported registration/import |
| Compressed archive | 20 MiB streamed | Fail import, preserve active snapshot |
| Total extracted content | 100 MiB | Fail import before exceeding budget |
| Archive entries / path depth | 5,000 entries / 20 path segments | Fail import; count excluded entries too |
| Supported file size | 512 KiB | Inventory file as excluded; continue with partial coverage |
| Retained supported content per snapshot | 20 MiB | Fail import with size-budget error |
| Job execution | 15 minutes active import time / 90 seconds active answer time | Check between bounded operations; cancel/fail without publication; queued time excluded |
| Provider/GitHub network call | 30-second timeout; job deadline takes precedence | Classify retryable failures; enforce remaining deadline |
| GitHub calls per import | 20 attempted requests including retries/redirects | Fail with request-budget reason |
| Search | Query ≤2,000 characters; result limit 1–20, default 10 | Reject oversized input |
| Viewer | ≤300 lines and ≤256 KiB per response | Return bounded range/continuation metadata |
| Question | ≤4,000 characters | Reject oversized input |
| Embedding input | ≤800 tokens per passage including headers; target 600, overlap ≤80 | Use selected model tokenizer; split at structure then lines; oversize single line uses explicitly labeled partial retrieval text |
| Answer context/output | ≤8,000 input tokens total / ≤1,200 output tokens, further limited by provider capacity | Include prompts/evidence/metadata in input budget; return gaps when evidence cannot fit |
| Answer evidence | Up to 12 bounded passages within token budget | Deduplicate placements; retain contributing files separately |
| Job capacity | One active worker job; ≤2 pending imports per repo; ≤10 queued/running/retry-wait jobs per owner | Reject excess enqueue with `429` and retry guidance |
| Leases/retries | 60-second lease; heartbeat every 15 seconds; ≤3 total attempts | Backoff with jitter/rate-limit guidance; job deadline and budgets still apply |
| Daily model usage | Owner-configured ceiling required before real provider calls; unset means disabled | Atomically reserve estimated maximum tokens/calls; reject when unavailable |

Separate embedding and generation token ceilings; combine them only through explicit owner configuration. A token cap is not a verified dollar cap. Track attempted calls with unknown usage conservatively until reconciled. An external request can complete after local timeout/cancellation, so application controls alone cannot guarantee a strict provider billing ceiling. Provider-side spending controls must be checked before a paid integration.

Supported content: `.py`, `.md`, `.rst`, `pyproject.toml`, `setup.cfg`, `tox.ini`, and non-secret `.toml`, `.ini`, `.json`, `.yaml`, `.yml` files outside excluded directories. Parse config without custom constructors, execution, interpolation, or fetching references. Docs/configs use bounded line-preserving sections; RST need not support all directives semantically. Keep syntax errors as inventory failures; valid text can still be shown if retained, with parse status visible. Unparseable files are excluded from structural retrieval in the baseline.

Exclude binary/non-UTF-8 files, VCS internals, build outputs, virtual environments, dependency/vendor directories, generated/minified files, and common secret paths such as `.env*`, private keys and credential files. Maintain a versioned exclusion policy. Heuristics are not a guarantee that supported files contain no secrets; owner import UI must disclose that selected supported text is transmitted to the configured model providers.

Reject absolute paths, traversal, duplicate normalized paths, links, device/special entries, and extraction outside a fresh temporary root. Validate public-repository metadata and resolved SHA before fetching an archive. Connector-only HTTPS hosts/redirects are explicitly allowlisted and private/local destinations blocked; never accept an arbitrary archive URL from a client. Stream budgets before full buffering. No module imports, dependency installation or code execution from downloaded content.

## Import lifecycle and durable jobs

An import job has stages `resolve → download → inventory → parse → embed → validate → activate`. Save bounded checkpoints and counters after committed batches. On the first successful resolution persist `resolved_sha`; every retry uses it even if the branch moves. Requested ref remains explanatory metadata.

Job transitions:

| From | To | Condition |
| --- | --- | --- |
| queued | running | Worker atomically claims eligible work and increments fencing token |
| running | retry_wait | Transient failure, attempts/time/budget remain |
| retry_wait | running | Retry time reached; new claim/token |
| running with expired lease | running | Reclaim creates a new attempt/token within attempt limit |
| running | succeeded | Validated publication and final job state commit together |
| queued/retry_wait | cancelled | Owner cancellation before claim |
| running | cancelled | Current worker observes cancel request before final publication |
| queued/running/retry_wait | failed | Permanent error, exhausted budget/deadline/attempts, or invalid configuration |

Use short claiming transactions and row locks that allow skipping locked work. Lease checks use database time. Every checkpoint, event, completion and activation write checks the current token and unexpired lease in its transaction. A heartbeat has a separate path during long network operations; bounded provider calls do not silently disable renewal. The terminal state of a lost worker is settled on reclaim, not by a browser.

Checkpoint commits and event inserts share a transaction. Completion rechecks cancellation under the job lock. If completion wins the race, later cancel returns the terminal result; if cancellation wins, publication is rejected. Never keep database locks open across network calls.

Import enqueue reserves an increasing repository activation generation. At publication, lock/check repository and current job: only a job whose generation equals the latest requested generation may change `active_snapshot_id`. A superseded job may still complete a retained ready snapshot and reports `activated: false, reason: superseded`. If the newer job fails, the prior active snapshot remains; an older late completion is not silently promoted. A new explicit import of the desired retained SHA can activate it.

Validate manifest reconciliation, supported/excluded counts, source ranges, passage coverage, and configured vector counts/dimensions before marking ready for the declared capability. Embedding failure prevents nonempty hybrid snapshots from becoming ready. A searchable snapshot with zero supported passages is marked `empty`; inventory is readable, search is empty, and generation is unavailable. Individual file parse/exclusion failures yield explicit partial coverage. Failed/cancelled jobs never activate staging content.

Answer and overview jobs use the same scheduler/fencing rules, with stages `retrieve → assemble → generate → validate → publish`. Provider calls may repeat after recovery. Only a current worker can commit one final output. Persist evidence before the external generation call; abandoned attempts can remain diagnostic records but cannot publish conflicting results.

Events contain metadata/progress, not streamed model tokens. Token-by-token answer streaming is deferred; completed answers appear after validation. SSE is for durable job progress and run links.

## Retrieval, overview and answer contract

At request acceptance resolve an omitted snapshot to the active ready snapshot and keep that ID through the operation. Reject explicitly selected staging/failed snapshots. For question/overview jobs, pin it at enqueue time, not worker start. No active snapshot returns `409 snapshot_not_ready`.

Search modes: `exact`, `lexical`, `semantic`, `hybrid`. Exact matches preserve original identifiers and qualified names; lexical additionally normalizes identifier variants. Hybrid combines independent lexical and vector top-50 candidate lists with reciprocal rank fusion, proposed constant 60, after scope/kind/path filters. Exact-symbol matches may be prepended as a separately labeled signal. Deduplicate by source placement; preserve distinct functions in the same file. Stable tie order uses path, start line, then passage ID. Record fusion configuration for evaluation.

`path_prefix` is a normalized literal repository-relative prefix, not a regex/glob. Source kinds are `code`, `test`, `doc`, `config`, with the classifier version recorded. Tests are static source evidence; presence is not executed coverage.

If semantic/hybrid query embeddings fail, default to `503 provider_unavailable`. Only `allow_lexical_fallback=true` permits a lexical response; report requested/effective mode and warning. Exact/lexical never need generation or query embeddings. Search scores indicate rank signals, not confidence.

Answer assembly selects up to 12 evidence passages, optionally adding bounded enclosing/neighbor lines within the same snapshot. A synthetic combined excerpt cannot claim one continuous original range across omitted lines; store separate ranges/evidence items. The generator receives question/task, baseline, selected original excerpts and IDs, inventory coverage and explicit source-as-data instructions. It cannot browse, execute code or retrieve another snapshot.

An overview combines deterministic inventory with bounded README, packaging/entry-point config, major-module and symbol evidence. Candidate entry points are supported by static declarations or source and labeled as candidates where runtime behavior is unknown. Overview coverage describes inspected files; it never implies exhaustive architectural analysis.

Successful run output:

```json
{
  "run_id": "run_example",
  "kind": "question",
  "snapshot_id": "snapshot_A",
  "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "outcome": "answered",
  "segments": [
    {
      "text": "The request handler delegates input checking to validate_payload.",
      "evidence_ids": ["e1", "e2"]
    }
  ],
  "citations": [
    {"evidence_id": "e1", "source_version_id": "sv_api", "path": "app/api.py", "start_line": 10, "end_line": 18},
    {"evidence_id": "e2", "source_version_id": "sv_validation", "path": "app/validation.py", "start_line": 5, "end_line": 24}
  ],
  "gaps": [],
  "limitations": ["Static source inspection; repository code was not executed."],
  "coverage": {"included_files": 12, "excluded_files": 3, "parse_failed_files": 0, "inspected_files": 2}
}
```

Identifiers, SHA and source lines above are synthetic examples. Production citations also include the stored excerpt and a server-constructed GitHub URL pinned to the full SHA. `outcome` is `answered`, `partial`, or `insufficient_evidence`; this is distinct from job success. Insufficient evidence can be a successful run with no substantive claims and an empty citation list.

Validate provider schema, evidence IDs, source membership, ranges, allowed links, and segment references before publishing. Never trust a model-supplied URL. A maximum of one bounded repair call is allowed if budget/deadline remain; otherwise fail `invalid_model_output`. Reference validity is a mechanical gate; semantic support needs the separate evaluation rubric. Save model/configuration and known usage alongside output. Reopening a run never regenerates it implicitly.

## HTTP contracts

All routes are under `/v1`. JSON requests/responses use opaque IDs, UTC timestamps with timezone, structured errors, and request IDs. Query parameters are validated and pagination is bounded. List defaults are 20, maximum 100, using opaque continuation cursors tied to filters/sort; event replay and source line continuation have their own contracts.

| Method | Route | Contract |
| --- | --- | --- |
| GET | `/health`, `/ready` | Process liveness / database-schema readiness; worker availability is separate |
| POST | `/repositories` | `{github_repository: "owner/name", default_ref?: "main"}`; `201` on new registration, `200` on existing canonical registration |
| GET | `/repositories` | Scoped paginated repository summaries |
| GET | `/repositories/{id}` | Identity, active snapshot, inventory/coverage summary, current jobs, last worker heartbeat |
| POST | `/repositories/{id}/imports` | `{ref: "main"}` plus required idempotency key; `202` durable import job |
| GET | `/repositories/{id}/snapshots` | Paginated retained ready baselines with config/coverage; job exposes staging status |
| GET | `/repositories/{id}/tree` | Snapshot, optional directory, bounded paginated inventory including exclusions |
| GET | `/repositories/{id}/files` | Snapshot, path, start/end lines; immutable stored original source, range/continuation metadata |
| GET | `/repositories/{id}/symbols` | Snapshot, exact/prefix query, optional path; bounded paginated symbols |
| GET | `/repositories/{id}/search` | Snapshot, query, mode (default `lexical`), kinds, path prefix, limit, fallback flag; excerpts/evidence, coverage and effective mode |
| POST | `/repositories/{id}/questions` | `{question, snapshot_id?, retrieval_mode?: "hybrid"}` plus idempotency key; `202` with job/run IDs |
| POST | `/repositories/{id}/overviews` | `{snapshot_id?}` plus idempotency key; `202` cited overview job/run IDs |
| GET | `/runs/{id}` | Run status, chosen baseline, evidence, configuration, coverage, result or error |
| GET | `/runs/{id}/export` | Owner-authorized JSON: schema version, output, exact evidence, baseline/configuration and known usage; no credentials |
| GET | `/jobs/{id}` | Kind, status, stage, counters, attempts, retry time, last heartbeat, cancellation, error/result links |
| GET | `/jobs/{id}/events` | Authenticated SSE; ordered persisted event sequence, supports `Last-Event-ID` |
| POST | `/jobs/{id}/cancel` | `202` while cancellation is pending, `200` terminal state; no rollback of completed publication |
| DELETE | `/repositories/{id}` | Owner-only explicit purge; `409` if nonterminal jobs exist; delete dependencies transactionally, then GC unreferenced cache entries |

Source read errors distinguish missing paths from excluded/unavailable bodies. Inventory remains available for excluded paths. Search evidence IDs are response-local; they become run-local immutable IDs only after answer assembly persists selections.

Asynchronous response example:

```json
{
  "job_id": "job_example",
  "run_id": "run_example",
  "status": "queued",
  "snapshot_id": "snapshot_A",
  "status_url": "/v1/jobs/job_example",
  "events_url": "/v1/jobs/job_example/events",
  "result_url": "/v1/runs/run_example"
}
```

Import responses omit `run_id` and answer-specific fields; resolved SHA is initially unknown and exposed on the job after pinning.

Require `Idempotency-Key` on all job-creating POSTs. Scope by actor + repository + operation + key; hash normalized client inputs, including whether snapshot was omitted. Replay must return the originally pinned job/run even if the active snapshot changed since enqueue. Same key/different request gives `409 idempotency_conflict`. Retain records for at least seven days after terminal completion and throughout nonterminal work. Reusing a key after retention can create new work; document that behavior.

Error shape:

```json
{"error": {"code": "snapshot_not_ready", "message": "No ready snapshot is available.", "retryable": false}, "request_id": "request_example"}
```

Use `401` for missing/invalid credentials; `403` for a known disallowed operation; scoped missing/inaccessible resource IDs return `404`. Use `422` for invalid inputs/unsupported source policy, `409` for state/idempotency conflicts, `429` for application quotas/capacity, and `503` for unavailable required services. Async execution failures live on the job/run, not a retrospective HTTP status change. Never include tokens or provider error bodies verbatim.

Persist progress events with sequence IDs scoped to the job, UTC time, stage/status and counters. Heartbeat pings without IDs are not durable history. Reconnect replays events after `Last-Event-ID`, then tails; clients deduplicate by ID. For a cursor older than retained history return `410 event_history_expired` before opening SSE and direct the client to reload job state. Terminal job state and completed output remain readable after event expiry.

## Retention and operations

Proposed local policy: retain ready snapshots and successful runs until explicit owner purge; never silently remove evidence referenced by a retained run. This is manual bounded storage, not a claim of infinite capacity. Enforce a configurable storage ceiling that rejects new imports before deleting retained data. Keep job events and terminal idempotency records for at least seven days; retain job summaries until repository purge. Remove failed/staging unreferenced data after seven days and temporary archives at job end or on startup cleanup.

Purge first requires all jobs terminal, then deletes runs/evidence, jobs/events, snapshot manifests, source placements and repository-scoped data in foreign-key order. Shared vectors are collected only when no remaining passage references them. Export is available before purge. No background retention task may delete evidence needed by retained runs.

Log request/job/run/repository/snapshot IDs, lease generation, stage times, counts, retries, provider identity, usage and structured error codes. Redact secrets; avoid full source and question text in routine logs. Report worker freshness separately from API/database readiness. Provide runbooks for restart/reclaim/cancel, rebuild, configuration/model change, export/purge and database restore.

## Decision register

The documents establish a planning baseline. Rows below distinguish user preferences from technical work that can be verified during implementation. No paid resource, deployment, Git commit or push is authorized by them.

| ID | Decision | Proposed direction / required evidence | Resolve before |
| --- | --- | --- | --- |
| D-01 | Confirm local versus hosted first delivery | Local demo first; hosted showcase optional. User preference may change this without expanding product scope | Hosting work; local foundation can proceed when implementation is requested |
| D-02 | Maximum real-provider spend and source transmission | Real adapters disabled until owner sets a budget and accepts selected-source transmission; $0 aspiration retained | Any real model call |
| D-03 | Embedding/generation models and providers | Verify tokenizer, effective input/output limits, identity/revision, dimensions, usage reporting and data policy; fake adapters first | Model adapter integration and vector schema finalization |
| D-04 | Dependency/toolchain versions | Pin compatible supported versions and consult current primary documentation; no versions asserted beyond the existing Python baseline | Scaffold/lockfiles |
| D-05 | Limits and retention | Tables above are proposed defaults; validate fixture size, storage ceiling, timing and manual-retention expectations | First real import and release |
| D-06 | Remote owner auth/hosting/database | Keep local auth for local use; verify TLS, persistence, backups, costs and credentials for chosen remote services | Any hosted deployment |
| D-07 | Real showcase repository and license | Choose a small compatible public Python repository; inspect license and preserve notices. Choose this project's license before distribution | Real-corpus distribution/showcase |
| D-08 | Quality/latency/cost thresholds | Measure development baseline; freeze numeric targets before held-out release evaluation | Release evaluation |
| D-09 | Landing variant and initial theme behavior | Supplied HTML is confirmed visual direction; choose meadow versus optional canyon and initial light/dark behavior without redesigning the reference | Frontend implementation |

Product scope and the supplied HTML's role as UI reference are user-confirmed. The proposed operating defaults above should be reviewed as planning choices; uncertain provider capabilities, prices and hosting quotas are intentionally not presented as facts.
