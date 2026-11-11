# Understory — MVP scope and user journey

Updated: November 11, 2026. Status: local MVP implemented. See [verification evidence](VERIFICATION.md) and [runnable setup](../README.md).

## Product decision

Understory helps a developer understand an unfamiliar repository through structural exploration, search, and source-backed explanations. The user has confirmed that repository understanding is the entire product focus. Issue investigation, PR research, contribution briefs, and live discussion/status tracking are outside the product scope, including the roadmap in this specification.

**Promise:** import a supported repository, find the relevant code, understand how it fits together, and inspect the exact sources behind an explanation.

Primary user: a developer onboarding to a small public Python repository. Portfolio value comes from demonstrating reliable ingestion, useful retrieval, traceable answers, and measured behavior.

## Decision status

| Decision | Status | Direction |
| --- | --- | --- |
| Product focus | User confirmed | Repository understanding only |
| UI direction | User confirmed | Follow the supplied [Understory.html](../Understory.html); preserve its visual identity and map mock content to repository-only behavior |
| Supported corpus | Existing blueprint, retained | Small public Python repositories; Python, Markdown/RST, and selected configuration files |
| Core experience | Planning baseline | Import → overview → explore/search → source viewer → cited Q&A |
| Architecture | Existing blueprint, retained | Python API, separate durable worker, one PostgreSQL database, web frontend |
| Initial operating mode | User confirmed | Local development and an owner-operated local demo; hosting is a separate readiness gate |
| Access | Implemented local choice | One owner identity; all repository/job/answer operations require owner access in the MVP |
| Cost | Bounded local choice | Local embeddings; user-enabled Groq with 50,000 daily reserved/settled tokens; provider quotas still apply |
| Models and dependency versions | Implemented and locked | FastEmbed BGE small, Groq gpt-oss-120b; uv/npm lockfiles and recorded model asset identity |

Proposed defaults make the plan concrete without presenting unconfirmed preferences as user decisions. The first release is usable locally. A hosted portfolio showcase is a delivery option after its costs and access model are settled. Public anonymous querying is not required for local MVP completion.

## Included behavior

| Capability | MVP behavior | Boundary |
| --- | --- | --- |
| Registration and import | Owner registers an allowlisted GitHub repository and selects a branch, tag, or commit | Public repositories only; no arbitrary URLs or execution of repository code |
| Import progress | Persisted stages, retry/failure state, cancellation, reconnect, worker availability | One worker process initially; durable database coordination |
| Versioned snapshots | Resolve ref to SHA; activate validated imports; retain old baselines | Each request uses exactly one ready snapshot |
| Repository overview | File/language inventory, supported coverage, entry-point candidates, cited explanation of major modules | Static evidence; runtime paths are qualified when uncertain |
| Structural exploration | File tree, classes/functions/methods/imports, exact/prefix symbol lookup | Python AST; no complete runtime call graph |
| Search | Exact symbols, lexical, semantic, and hybrid search with path/source-kind filters | Code, docs, tests, and supported configs from the selected snapshot |
| Source viewing | Stored file ranges with line numbers, symbol navigation, pinned GitHub links | Skipped source bodies are unavailable and labeled with their exclusion reason |
| Questions | Independent questions with cited answers, limitations, and explicit evidence gaps | No conversational memory dependency; follow-up questions are new requests |
| Refresh | Owner explicitly imports another ref/SHA; changed and deleted paths update safely | No automatic polling, webhooks, or branch-following |
| Review and export | Reopen retained answers and export their output, baseline, and evidence | Export contains the bounded evidence used; it is not a complete repository backup |

Semantic search and generation are required for the completed MVP, but exact and lexical search remain usable when model services fail. Generated overview text is optional at workspace opening: the deterministic inventory is always available after import.

## Outside scope

- Issue, PR, comment, maintainer-discussion, or contribution workflows.
- Editing code, proposing patches, creating PRs, running tests/builds, importing downloaded Python modules, or installing repository dependencies.
- Private repositories, arbitrary large imports, additional language parsers, multi-user collections, and public self-service imports.
- Multi-agent orchestration, autonomous tool loops, a graph database, a second queue scheduler, or speculative reranking.
- A chat-history product, architecture diagram generation, or automatic documentation rewriting.
- MCP in the MVP. A later read-only adapter may expose the same repository-understanding services.

## User journey

### 1. Choose and import

The owner opens the repository selector, enters `owner/name` and a ref, and sees the supported-file policy and limits. Import creates a durable job. The workspace shows its stage, coverage counters, last worker heartbeat, retry state, and cancellation control. If the worker is offline, the job remains queued with an explicit availability message.

Validation failure explains the rejected input. A first import has no searchable snapshot until completion. During refresh, the existing ready snapshot remains available.

### 2. Orient

The ready workspace shows repository identity, requested ref, resolved SHA, indexing time, file tree, source coverage, and skipped-file reasons. It separates deterministic inventory from generated explanation. The owner can generate an overview explaining purpose, major modules, and likely entry points; each substantive repository claim links to evidence. Unknown architecture details remain unknown.

### 3. Find a behavior

The developer searches an identifier or asks a conceptual search question. Results show file, qualified symbol/section, source kind, line range, excerpt, selected mode, and snapshot. Filters narrow paths and source kinds. No results and provider unavailability have distinct states. Exact symbol lookup supports overloaded names across modules without merging them by filename.

### 4. Inspect the source

Selecting a hit opens its stored source lines in the same workspace. The viewer preserves the chosen snapshot and highlights the cited range. Opening a GitHub link uses the full commit SHA. Unsupported or excluded files remain visible in inventory with a reason; the UI does not imply that all repository content was searched.

### 5. Ask and verify

The developer submits an independent question against the selected snapshot. The answer job persists progress. The completed answer contains an explanation, linked citations, coverage, and limitations. Clicking a citation opens the exact file and lines used. An insufficient-evidence answer explains what could not be established. A provider failure produces a failed job rather than a fabricated answer.

An active-snapshot change during generation does not change the answer's baseline. Reopening or exporting the answer preserves that baseline and its evidence.

### 6. Refresh and compare context

The owner imports commit B. Changed files are reprocessed, compatible unchanged embedding inputs are reused, and deleted files disappear from B. The developer can select retained commit A or B. This is baseline selection, not a visual diff feature. Failed/cancelled refreshes leave the existing active snapshot intact.

## Workspace information architecture

| Surface | Required information and actions |
| --- | --- |
| Repository selector | Repositories, ready/importing state, register/import controls |
| Workspace header | Repository, selected SHA/ref, snapshot selector, indexing time, coverage |
| Overview | Inventory, entry-point candidates, generate/reopen cited explanation |
| Explore | File tree, symbol list, bounded source viewer |
| Search | Query, mode, filters, result excerpts, empty/degraded/error states |
| Ask | Question, persisted run status, answer, citations, limitations, export |
| Job panel | Stage, durable events, attempts, errors, worker heartbeat, cancellation |

The supplied [Understory.html](../Understory.html) establishes the visual direction: scenic landing, serif wordmark/display type, compact three-pane repository/question/evidence workspace, and supplied light/dark treatments. [UI_REFERENCE.md](UI_REFERENCE.md) records the boards, observed styles and scope corrections. The workspace surfaces above occupy that composition rather than implying a different visual design. Include the landing as the visual entry surface; its input respects owner access and requires a selected ready repository before answering.

The component implementation follows this reference. Source rendering must remain keyboard accessible, escape untrusted content, and communicate state without relying only on color. The user selected meadow with light/dark themes; canyon remains an unused reference option.

## Demonstration

Use a clearly labeled synthetic Python fixture, then a small real repository after the fixture passes.

1. Import fixture A; interrupt and restart the worker; recover without duplicate content.
2. Inspect inventory, exclusions, a decorated function, and a documentation section.
3. Search “where is input validation handled?”; open the relevant symbol and source.
4. Generate an overview and answer a multi-file request-flow question with citations.
5. Ask an intentionally unanswerable question and inspect the evidence gap.
6. Import B with changed, removed, and renamed paths; inspect B and reopen an answer pinned to A.
7. Disable model access; demonstrate lexical search and an explicit model-unavailable state.

## Release definition

The MVP is complete when the journey above works locally from a documented setup, every mandatory gate in [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) has evidence, and the evaluation report declares its corpus, configurations, results, and limitations. A hosted showcase additionally requires the deployment gate in that document.

The next planning review should resolve the open decisions in [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md#decision-register). The implementation order is in [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md).
