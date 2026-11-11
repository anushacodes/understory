# Understory — project plan

Updated: November 11, 2026. Status: local MVP implemented. Start with [README.md](README.md), [verification evidence](docs/VERIFICATION.md), and [architecture decisions](docs/ARCHITECTURE_DECISIONS.md).

## Confirmed purpose

Help a developer understand an unfamiliar repository through structural exploration, search and explanations backed by inspectable source.

The user confirmed that repository understanding is the entire product focus. Remove issue/PR research, discussion ingestion, contribution briefs, status checking and their associated schema/routes from the active plan. They are outside the product, not deferred MVP features.

## Planning package

| Artifact | Defines |
| --- | --- |
| [MVP_SCOPE.md](docs/MVP_SCOPE.md) | User, product promise, features/boundaries, user journey, workspace surfaces and demo |
| [ACCEPTANCE_CRITERIA.md](docs/ACCEPTANCE_CRITERIA.md) | Controlled corpus, behavior gates, evaluation protocol and release evidence |
| [TECHNICAL_SPEC.md](docs/TECHNICAL_SPEC.md) | Data identities, constraints, jobs, source handling, search/answer contracts, APIs and decisions |
| [IMPLEMENTATION_BACKLOG.md](docs/IMPLEMENTATION_BACKLOG.md) | Dependencies, tasks and milestone completion conditions |
| [UI_REFERENCE.md](docs/UI_REFERENCE.md) | User-supplied HTML design, screen mapping and functional scope corrections |

This summary replaces the previous contribution-research blueprint. Detailed contracts live in the artifacts rather than being duplicated here. [README (1).md](<README (1).md>) is the project introduction. [Understory.html](Understory.html) is the user-supplied UI design reference; preserve its visual identity and composition with the scope corrections documented in UI_REFERENCE.md. The SVG is an earlier architecture concept; current technical contracts govern architecture.

## First release

Supported corpus: small public Python repositories with Python source, tests, Markdown/RST and selected configuration files. The owner imports an allowlisted repository at a ref; the worker pins a SHA and safely builds an immutable snapshot.

The developer gets:

- Durable import progress, cancellation/retry state, worker availability and visible coverage.
- Inventory, file tree, structural symbols, source viewer and retained snapshot selection.
- Exact, lexical, semantic and hybrid search with source/path filters.
- Deterministic inventory plus an on-demand cited architectural overview.
- Independent questions with validated citations, evidence gaps and explicit limitations.
- Owner-triggered refresh, historical answer review and JSON evidence export.

No repository code, build or test execution occurs. Static tests are evidence about test source, not executed coverage. There is no code modification, autonomous tool loop or issue/PR workflow.

## Architecture baseline

Use a modular Python application, separate API/worker entry points, one PostgreSQL database with vector support and a web frontend. Keep one PostgreSQL-backed durable scheduler, fenced leases, persisted checkpoints/events and atomic snapshot activation.

Retain the existing proposed Python/FastAPI, PostgreSQL, SQLAlchemy, React/TypeScript/Vite and local tooling choices. Exact versions and provider compatibility require verification during implementation. No particular hosted database, auth service, inference provider or hosting plan is selected.

Each request binds to one ready snapshot. Code/docs/config evidence uses stored immutable source text, original line ranges and commit-pinned links. Failed/staging snapshots are never ordinary search results. Old runs retain their exact evidence after a new import.

## Proposed operating defaults

The following are planning defaults, not newly confirmed user preferences:

| Area | Proposed default |
| --- | --- |
| Delivery | Local owner-operated demo first; optional hosted showcase after feasibility checks |
| Access | One owner identity; authenticated repository/job/run/source operations |
| Imports | Curated public Python repositories; bounded source processing; one worker |
| Generation | Fake adapters first; real calls disabled until provider/budget/transmission choices are settled |
| Retention | Keep ready baselines and runs until explicit purge; reject new work at storage ceiling |
| Questions | Independent requests; durable completed answers; no chat-memory requirement |
| Streaming | Durable job progress over SSE; completed validated output rather than token streaming |
| Refresh | Explicit owner import of another ref; compatible input/vector reuse and safe activation |
| Evaluation | Synthetic A/B corpus, 24 labeled questions, development/held-out split; then a real corpus |

The original $0 showcase objective remains an aspiration. Do not assume free always-on hosting, cloud workers, backups, model quotas or price figures.

## Milestones

| Stage | Goal | Exit evidence |
| --- | --- | --- |
| M0 | Review decisions/contracts; build fixtures and question labels | Reproducible corpus and reviewable contracts; unresolved provider/hosting choices recorded |
| M1 | Durable safe importer | Interrupt/reclaim/replay; stale writes rejected; active baseline preserved |
| M2 | Structural and lexical exploration | Correct source ranges, symbols/filters, inventory and working source viewer |
| M3 | Semantic/hybrid retrieval | Compatible cache identity, model-ready publication and measured mode comparison |
| M4 | Cited repository explanations | Supported answers, explicit gaps, validated citations, overview and evidence export |
| M5 | Refresh, operations and release | Two-snapshot correctness, retention/purge, full acceptance evidence and evaluation report |

The complete local MVP includes M0–M5. M4 delivers the core experience; M5 supplies the release evidence. Optional hosted delivery and later read-only MCP reuse the same scope and services.

## Decisions before and during implementation

Review delivery/access defaults, budget, source transmission and proposed limits before implementation. Verify and pin dependency versions during M0/foundation work. Select model provider/configuration before real embeddings/generation. Resolve remote hosting/authentication only if hosted delivery is required. Choose a real evaluation repository and project license before distribution.

Quality, latency and cost targets cannot be claimed from the plan. Establish a development baseline, freeze proposed numeric release thresholds, then evaluate the held-out split. Mechanical requirements such as valid citations, scope isolation and safe publication remain mandatory regardless of model quality.

The [technical decision register](docs/TECHNICAL_SPEC.md#decision-register) tracks timing and proposed evidence. The backlog contains no dates or claims that implementation is already complete.

## Next action

Review the four artifacts and resolve any changes to the proposed defaults. Implementation begins only when requested. No code scaffold, paid-service activation, deployment, Git commit or push is authorized by this planning package.
