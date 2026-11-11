# Understory — milestone backlog

Updated: November 11, 2026. Status: local M0–M5 delivery implemented; evidence and qualifications appear below and in [VERIFICATION.md](VERIFICATION.md). Original task dependencies are retained for study.

Scope: repository understanding. [MVP_SCOPE.md](MVP_SCOPE.md) defines the experience; [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) defines contracts; [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) defines gate IDs.

## Milestone evidence

| Milestone | Delivered evidence |
| --- | --- |
| M0 | Pydantic/OpenAPI contracts, synthetic A/B, 24 labeled questions, dependency locks and UI mapping |
| M1 | Real PostgreSQL migrations, job/lease/API tests, subprocess crash/reclaim test, pinned GitHub import |
| M2 | Parser/source/range/filter tests and desktop/mobile browse/search checks |
| M3 | Local 384-dimensional model, compatible cache/version tests and four-mode development/held-out reports |
| M4 | Real Groq outputs, negative output/budget tests, overview/history/export/citation browser flows |
| M5 | Retention/purge and storage tests, database restore drill, real ItsDangerous import, warm measurements, documented local setup |

The detailed gate evidence and limitations are in [VERIFICATION.md](VERIFICATION.md). Hosted deployment, anonymous access and MCP remain optional and unimplemented. There is no automatic malformed-answer repair; validation fails closed instead. Physical database capacity includes more than the source-byte import ceiling.

## Working rules

- Start implementation only after the user requests it. Creating these artifacts does not authorize provider calls, deployment, commits or pushes.
- Implement only the tables/routes needed by the current milestone while preserving declared identities.
- Keep the API and worker separate; use one durable PostgreSQL scheduler. No agent framework is needed.
- Use fake connectors/providers before spending money or sending real repository text to a provider.
- Each task records its applicable gate results and remaining limitations. Do not claim a gate passed from documentation alone.
- Estimate calendar effort after the foundation and importer demonstrate actual throughput; this backlog contains dependencies rather than invented deadlines.

## M0 — Review contracts and define fixtures

| Task | Deliverable | Depends on | Done when |
| --- | --- | --- | --- |
| P0-01 | Decision record for D-01/D-02 and proposed access/limits/retention | Planning artifacts | Local delivery default, budget restrictions, and any user preference changes are explicit; unresolved remote choices do not block local design |
| P0-02 | Machine-readable API/data schemas and error examples | P0-01 | Route shapes, identities, state transitions and idempotency rules match the technical spec; no issue/PR contracts remain |
| P0-03 | Synthetic source fixture A/B and recorded connector responses | P0-02 | Deterministic archive hashes and expected manifests; changed/deleted/renamed files, parser edge cases and unsafe inert inputs are documented; no Git commit is needed |
| P0-04 | 24 labeled questions and fixed development/held-out split | P0-03 | Expected evidence units and unanswerable cases are reviewed; held-out labels are separated from tuning |
| P0-05 | Dependency/provider selection notes | P0-01 | Supported dependency versions checked; fake adapter contract fixed; D-03 real-provider work remains gated by budget/transmission decision |
| P0-06 | Supplied HTML screen/component mapping and frontend behavior decisions | P0-02, [UI_REFERENCE.md](UI_REFERENCE.md) | D-09 landing/theme choices recorded; desktop panes, responsive access, citation interaction and mock-feature scope corrections specified; no new visual direction invented |

**Exit evidence:** reviewable contracts, fixture specification/data, question labels, decision register. These planning documents are the starting input to M0, not proof that executable fixtures or schemas already exist.

## M1 — Local foundation and durable imports

| Task | Deliverable | Depends on | Done when / gates |
| --- | --- | --- | --- |
| P1-01 | Locked backend/frontend environments, local database setup, settings, health/readiness, API and worker entry points | P0-02, P0-05 | Clean setup can start each process; no real-provider credentials required; initial OPS-02 evidence |
| P1-02 | Migrations for repositories, snapshots, source inventory, jobs/events, owner scope and idempotency | P1-01 | Constraints reject cross-repository associations/duplicate identities; SEC-01 foundation |
| P1-03 | Registration/import enqueue, scoped job read/cancel, fenced worker claims/heartbeats/retries | P1-02 | IMP-02, JOB-01/02/04/05 pass using a deterministic checkpoint task |
| P1-04 | Public GitHub connector and safe pinned download/inventory | P1-03, P0-03 | IMP-01, SEC-02/03; transient storage can be rebuilt from persisted SHA |
| P1-05 | Staging validation, idempotent writes, atomic activation generation | P1-04 | IMP-03/04, JOB-03; failures/cancellation preserve prior active pointer |
| P1-06 | Durable event replay and worker-availability responses | P1-03 | EVT-01/02 pass through API; job progress does not depend on browser presence |

**Exit evidence:** interrupt/reclaim/replay demonstration using the fixture. At this stage inventory can be published under an explicit inventory-only configuration; it does not advertise searchable/model-ready capability. M2 creates the full searchable configuration before search is exposed.

## M2 — Structural sources and lexical exploration

| Task | Deliverable | Depends on | Done when / gates |
| --- | --- | --- | --- |
| P2-01 | Python AST, line-preserving docs/config parsers, versioned exclusion/classification rules | P1-04, P0-03 | SRC-01/02/03/04; exact original ranges and coverage counts verified |
| P2-02 | Symbols/passages, snapshot-aware source/tree APIs, retained baselines | P2-01, P1-05 | Ranges and membership enforced; VER-01 source/manifests and VER-03 read isolation |
| P2-03 | Exact/prefix symbol and lexical retrieval, filters, stable ordering | P2-02 | RET-01/02/03 for exact/lexical; no staging leakage; query/result limits enforced |
| P2-04 | Reference-based landing and three-pane workspace: owner session, import/job panel, inventory, file tree, source viewer, search | P2-03, P1-06, P0-06 | UI-01 through search/viewer, UI-02/03/04/05/06 and SEC-04; preserve supplied composition/fonts/palettes and working responsive navigation |
| P2-05 | Retrieval evaluation runner and development lexical baseline | P2-03, P0-04 | Corpus/config/per-query results recorded; semantic quality claims remain absent |

**Exit evidence:** a developer finds and opens relevant stored source at one SHA without any model service. Inventory-only M1 snapshots are not silently upgraded; reimport/reuse content under the searchable configuration.

## M3 — Embeddings and hybrid retrieval

| Task | Deliverable | Depends on | Done when / gates |
| --- | --- | --- | --- |
| P3-01 | Fake embedding adapter, effective config identity, tokenizer/batching and compatible vector cache | P2-02, P0-05 | VER-02 and identity/replay checks; model input includes headers and respects limits |
| P3-02 | Real embedding adapter and atomic model-ready snapshot validation | P3-01, resolved D-02/D-03 | One measured bounded fixture batch; actual usage and dimensions recorded; unavailable provider cannot activate incomplete corpus |
| P3-03 | Semantic search, hybrid fusion, explicit lexical fallback | P3-02, P2-03 | RET-02/04/05 across all modes; requested/effective modes exposed |
| P3-04 | Search mode/filter UI and development evaluation comparison | P3-03, P2-04, P2-05 | Same questions/corpus across modes; coverage and degradation visible; initial D-08 proposals recorded |

**Exit evidence:** measured search comparison, compatible vector reuse, and provider-failure behavior. Fake embeddings are insufficient evidence of semantic retrieval quality.

## M4 — Cited repository explanations

| Task | Deliverable | Depends on | Done when / gates |
| --- | --- | --- | --- |
| P4-01 | Answer-run/evidence/usage migrations, enqueue/read/export, token reservations | P3-03, P1-03 | Snapshot pinned at enqueue; provider budget enforced across concurrent requests; negative scope checks |
| P4-02 | Bounded evidence assembly and structured generation adapter | P4-01, resolved D-03 | ANS-01/02/04/06 with scripted outputs; source instructions cannot change privilege |
| P4-03 | Citation/output validator, bounded repair and durable publication | P4-02 | ANS-03; invalid outputs never published; stale worker cannot finalize answers |
| P4-04 | Deterministic overview inventory plus on-demand cited overview | P4-03 | ANS-05; partial coverage and static entry-point uncertainty visible |
| P4-05 | Ask/overview UI in supplied question/evidence panes, citation navigation, reopen/export | P4-04, P2-04 | Full UI-01/02/03/04/05/06, VER-03/04; source gutter markers match answer citations; no unvalidated token stream shown as final content |
| P4-06 | Real-generation development evaluation and human claim-support review | P4-05 | Real-provider behavior evaluated separately from fake contracts; proposed D-08 thresholds supported by measurements |

**Exit evidence:** source-backed overview and independent questions; unanswerable and provider-failure scenarios; exact evidence exports. This is the first complete core workflow, with release hardening still required.

## M5 — Refresh, operations and local release

| Task | Deliverable | Depends on | Done when / gates |
| --- | --- | --- | --- |
| P5-01 | B refresh, unchanged vector reuse, deletion/rename handling and old-run review | P4-05 | VER-01/02/03/04 and JOB-03 under the complete pipeline |
| P5-02 | Storage ceiling, retention cleanup, owner purge, redacted diagnostics and recovery/export/rebuild/restore runbooks | P5-01 | OPS-01/02, SEC-01/03/04; referenced evidence never silently expires |
| P5-03 | Adversarial/boundary and full browser regression | P5-02 | All mandatory mechanical gates have recorded evidence; relevant failures fixed |
| P5-04 | Freeze targets then run held-out evaluation | P4-06, P5-03, resolved D-08 | Per-query results, human support/abstention review, timing/usage sample counts and limitations published; no tuning against held-out results |
| P5-05 | Small real-repository evaluation, local demo instructions and walkthrough | P5-04, resolved D-07 | Reproducible source SHA, license handling and real-corpus limitations; no fabricated performance or resume metrics |

**Exit evidence:** complete local MVP acceptance bundle. If release targets fail, record the gap and revise the implementation or scope explicitly; do not relabel failure as success.

## Optional delivery and later repository-understanding work

| Task | Dependency | Completion condition |
| --- | --- | --- |
| H-01 Hosted private showcase feasibility | D-01/D-02/D-06 and a minimal local vertical slice | Current host/model costs, persistence, auth/TLS, backups and worker-offline behavior verified; no provisioning during this planning task |
| H-02 Hosted showcase deployment | H-01, local release gates, explicit deployment authorization | Additional hosted acceptance gate passes; any anonymous-query design reviewed before enabling it |
| E-01 Read-only MCP adapter | Stable HTTP contracts and local release | Search/symbol/file/run tools reuse scope/evidence services and return consistent baselines |
| E-02 Measured retrieval extensions | Baseline evidence of a specific weakness | Evaluate reranking, additional parsers or richer static references against a new held-out set |

Hosting feasibility can be checked early if remote delivery becomes a requirement. Neither hosting nor MCP changes the product into issue investigation or automated code modification.

## Critical path and review checkpoint

`M0 contracts/fixtures → M1 durable import → M2 lexical exploration → M3 semantic/hybrid retrieval → M4 cited explanations → M5 local release`.

Before implementation, review the product defaults and D-01/D-02. Dependency versions can be checked when scaffolding is authorized. Models must be chosen before real-provider integration. Hosting and remote authentication can remain unresolved while the local MVP is built. No implementation, Git commit, push, deployment, or paid-service activation is implied by this backlog.
