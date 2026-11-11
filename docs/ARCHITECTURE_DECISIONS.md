# Understory — architecture decisions and interview notes

This is a living decision record for the actual project. Read it with the [technical specification](TECHNICAL_SPEC.md), [implementation backlog](IMPLEMENTATION_BACKLOG.md), and code. Update it whenever an architectural choice changes.

**Honesty rule:** alternatives below are design alternatives considered, not systems we necessarily built or benchmarked. A reason for choosing an approach is not a measured result. Verification references show what can support an interview answer; they do not imply that every release gate has passed. Understory is still being implemented.

## Decision index

| ID | Decision | Current status |
| --- | --- | --- |
| ADR-01 | Repository understanding is the product boundary | User confirmed; reflected in implementation |
| ADR-02 | Modular Python backend with separate API and worker | Implemented |
| ADR-03 | One PostgreSQL database, including pgvector and durable jobs | Implemented locally |
| ADR-04 | At-least-once jobs with leases, fencing and idempotency | Implemented; recovery tests exist |
| ADR-05 | Commit-pinned immutable snapshots and atomic activation | Implemented; further database hardening remains in progress |
| ADR-06 | Static parsing and bounded, read-only source handling | Implemented |
| ADR-07 | Structural passages with exact source provenance | Implemented |
| ADR-08 | Exact, lexical, semantic and hybrid retrieval | Implemented; quality evaluation remains in progress |
| ADR-09 | Local embeddings and Groq answer generation | Local inference verified; real answer validation in progress |
| ADR-10 | Cache embeddings by effective input and model identity | Implemented; reuse/version tests are being expanded |
| ADR-11 | Retrieve, assemble, generate, validate; bounded evidence | Implemented; deterministic publication tests exist |
| ADR-12 | Persisted runs and evidence over conversational memory | Implemented |
| ADR-13 | SSE for durable progress; publish answers after validation | Implemented; reconnect/reload verification being expanded |
| ADR-14 | React/Vite frontend following the supplied HTML | Implemented; initial desktop/mobile checks pass |
| ADR-15 | Owner-operated local delivery before hosting | User confirmed; implemented locally |
| ADR-16 | Controlled A/B fixtures and separate quality measures | Fixtures/tests implemented; evaluation report still in progress |
| ADR-17 | Locked tooling, migrations, focused commits and private remote | Implemented; delivery work ongoing |

## ADR-01 — Keep the product focused on repository understanding

**Problem.** The earlier blueprint mixed codebase onboarding with issue/PR investigation. That introduced additional evidence clocks, mutable discussions, live status checks, and relationship provenance before the core search experience worked.

**Decision and reason.** Follow the user's explicit correction: import code/docs/configs, explore structure, search, and answer questions with source citations. Remove issue tabs, discussion ingestion and contribution briefs from the active scope. The supplied HTML remains visual authority, while the product specification determines which capabilities are real.

**Alternative.** Implement the broader contribution-research system from the earlier plan. It could answer a different set of questions, but would add a second ingestion and freshness problem. It is outside this product rather than a hidden next milestone.

**Tradeoff.** Understory cannot answer maintainer-discussion or current-issue questions. It can give a coherent repository-understanding workflow with a smaller evidence model.

**Evidence.** [MVP scope](MVP_SCOPE.md), [UI mapping](UI_REFERENCE.md), and the implemented frontend omit issue workflows.

**Interview prompt.** “Tell me about reducing scope.” Explain how a user correction changed the data/API/UI scope together. Do not describe removed features as shipped.

## ADR-02 — Use a modular backend with separate API and worker processes

**Problem.** Imports can download, parse and embed many files. Keeping that work inside an HTTP request makes progress dependent on the request lifetime and occupies API capacity.

**Decision and reason.** Keep one shared Python application package with separate API and worker entry points. The API validates and queues work; the worker handles bounded long-running tasks. Shared services keep snapshot, access and retrieval semantics consistent.

**Alternatives.** A synchronous request handler is simpler initially but harder to recover. Separate ingestion/search/answer microservices offer independent deployment boundaries but add network contracts and operations before there is evidence that they are needed.

**Tradeoff.** Two local processes must be started and observed. They still share a database/schema and release lifecycle, so this is not independent microservice deployment.

**Evidence.** [main.py](../backend/app/main.py), [worker.py](../backend/app/worker.py), and the separate console entry points in [pyproject.toml](../pyproject.toml).

**Interview explanation.** “I separated execution lifetimes without prematurely separating the whole codebase into services.” Revisit the boundary if independently measured scaling or ownership requires it.

## ADR-03 — Use one PostgreSQL database for content, vectors and coordination

**Problem.** Snapshot publication needs to agree with job completion and the repository's active baseline. Splitting content, queue state and vector membership across systems introduces cross-system consistency work.

**Decision and reason.** PostgreSQL stores repositories, source versions, manifests, symbols, passages, vectors, jobs/events, runs and usage. pgvector supplies vector operations alongside relational filtering. The durable queue is ordinary application tables, not a separately hosted scheduler.

**Alternatives.** A dedicated vector service plus Redis/Celery or a managed job executor could be appropriate at another scale. SQLite would make setup lighter but would not exercise the intended PostgreSQL locking/vector behavior. None is claimed to be slower based on this project's measurements.

**Tradeoff.** Database storage, indexes and queue traffic share resources. We own lease/retry/recovery correctness and will need monitoring before larger workloads. PostgreSQL is an additional local dependency.

**Evidence.** [compose.yaml](../compose.yaml), [models.py](../backend/app/models.py), [jobs.py](../backend/app/jobs.py), and real PostgreSQL integration tests. No SQLite substitute is used to claim PostgreSQL recovery behavior.

**Interview prompt.** “Why didn't you use a dedicated vector database?” Lead with transaction boundaries and corpus size, then explain the conditions under which you would reconsider.

## ADR-04 — Prefer at-least-once execution with fenced writes to an exactly-once claim

**Problem.** A worker can stop after a provider call but before committing the corresponding application state. A lease can expire while the original worker is still alive.

**Decision and reason.** Claim jobs transactionally, increment a fencing token, renew an expiring lease, and check the token on writes. Use unique identities and idempotent checkpoints to make replay safe. Scope enqueue idempotency keys to owner/repository/operation and compare normalized request hashes.

**Alternatives.** In-memory tasks lose work on process exit. A lock without fencing does not prevent an old worker from committing after a replacement takes over. Claiming exactly-once external API execution would be stronger than we can prove.

**Tradeoff.** A provider call can repeat and incur repeated usage even when database writes are deduplicated. Heartbeats, reclaim, cancellation and retry accounting add implementation complexity.

**Evidence.** [test_jobs.py](../tests/test_jobs.py) expires/reclaims a lease and rejects old checkpoints. [test_imports.py](../tests/test_imports.py) checks replay identities. These controlled failures are actual project evidence; they are not a production outage story.

**Interview prompt.** “How did you handle concurrency or failure?” Walk through worker A losing its lease, worker B claiming a higher token, and A's next write being rejected. State the remaining external-call duplication risk.

## ADR-05 — Pin source to a commit and publish complete snapshots atomically

**Problem.** A branch can move during import or generation. Replacing the active index file by file can expose a mixture of old, new and missing content. An older import can also finish after a newer request.

**Decision and reason.** Resolve the ref once, persist the full SHA, and use it on retries. Build a staging snapshot, validate it, then change the active pointer in the completion transaction. Each import reserves a generation; only the latest requested generation can activate. Search and answer requests bind to one ready snapshot.

**Alternatives.** A mutable “latest” index is simpler but cannot reproduce historical answers. Activating whichever import finishes last lets a slow old import replace a newer requested baseline.

**Tradeoff.** Retained history consumes storage. A superseded import may finish as a ready historical snapshot without becoming active. If the latest request fails, an older late completion is not automatically promoted; the previous active snapshot remains.

**Evidence.** Refresh/deletion tests in [test_imports.py](../tests/test_imports.py), activation-order tests in [test_jobs.py](../tests/test_jobs.py), and the mid-generation refresh case in [test_answers.py](../tests/test_answers.py).

**Interview explanation.** The important unit of consistency is the selected snapshot, not the branch name shown in the UI. Remaining database-level invariant hardening should be described separately from already-tested service behavior.

## ADR-06 — Inspect downloaded source without executing it

**Problem.** Public repositories are untrusted inputs. Running their imports, setup hooks, tests or builds would turn repository understanding into a sandboxed-execution product.

**Decision and reason.** Use Python AST and line-preserving document/config extraction. Permit only canonical allowlisted public GitHub repositories through the connector. Bound archive bytes, extracted sizes, entries, depth and file sizes; reject traversal, links and special entries. Inventory skipped paths without retaining excluded bodies.

**Alternatives.** Runtime introspection could reveal relationships that static parsing misses, but needs a separate sandbox and execution policy. Broad arbitrary URL ingestion expands the network and source-trust boundary.

**Tradeoff.** Dynamic imports, decorators and runtime dispatch cannot be completely resolved. Static test files are not proof of executed coverage. Secret-path heuristics are useful exclusions, not a guarantee that every supported text file is safe to transmit externally.

**Evidence.** [connectors.py](../backend/app/connectors.py), [indexing.py](../backend/app/indexing.py), and adversarial inert archive/parser fixtures in [test_archives.py](../tests/test_archives.py) and [test_indexing.py](../tests/test_indexing.py).

**Interview prompt.** “What security boundary did you design?” Explain the deliberate exclusion of execution, then the limits and remaining static-analysis uncertainty.

## ADR-07 — Chunk around source structure and preserve original ranges

**Problem.** Arbitrary text windows can split functions or omit the symbol/path context needed for retrieval. Rewriting source into embedding input can also break citation alignment.

**Decision and reason.** Parse functions, classes, methods and nested definitions; retain imports/module-level spans and document/config sections. Store original excerpts and inclusive line ranges separately from embedding input. Include path/qualified-name context in retrieval input. Split large spans with bounded line-preserving chunks.

**Alternatives.** Whole-file embedding is simple but can dilute a specific function and exceed model limits. Plain fixed-size character windows lose structural boundaries. Richer language parsers could support more languages but are outside the initial Python scope.

**Tradeoff.** Nested definitions can overlap parent excerpts. Long single lines may require partial embedding input, while the original citation remains intact. Chunking quality needs measurement rather than assuming AST boundaries always improve recall.

**Evidence.** Decorated/async/nested/non-ASCII range assertions in [test_indexing.py](../tests/test_indexing.py); source-viewer range comparisons in [test_api.py](../tests/test_api.py).

**Interview explanation.** Distinguish the representation optimized for finding evidence from the original source used to verify the answer.

## ADR-08 — Expose complementary search modes and start with simple rank fusion

**Problem.** An exact identifier query and a conceptual behavior question do not need the same ranking signal. A model-only search path would make basic exploration dependent on model availability.

**Decision and reason.** Provide exact/prefix symbols, PostgreSQL lexical retrieval, local vector retrieval, and reciprocal-rank fusion of lexical/vector candidates. Apply repository/snapshot/kind/path filters before selecting candidates. Begin with exact vector scans for the bounded corpus.

**Alternatives.** Vector-only search can miss literal identifiers. Lexical-only search may miss paraphrases. A reranker, approximate vector index or BM25 implementation adds complexity that should be justified by held-out results.

**Tradeoff.** PostgreSQL full-text search is not BM25. RRF rank scores are not confidence probabilities. Different search modes can disagree, and hybrid may not outperform lexical retrieval on a given corpus.

**Evidence.** [retrieval.py](../backend/app/retrieval.py) and filter/fallback API tests. A numeric quality improvement is not yet established; it must come from the evaluation report.

**Interview prompt.** “How did you choose the retrieval approach?” Discuss query intent, failure modes and reproducible comparison. Never invent an accuracy percentage.

## ADR-09 — Run embeddings locally; use Groq for generation

**Problem.** The user wants a free-first local project and has a Groq key. Semantic search needs embeddings independently of the answer-generation service.

**Decision and reason.** Use FastEmbed with `BAAI/bge-small-en-v1.5` for CPU-local embeddings and a configurable Groq generation adapter. The current local model produces 384-dimensional vectors. Keep generation credentials server-side, with explicit token ceilings and visible rate-limit failures.

**Alternatives.** A paid embedding API would add per-import dependency/cost. A fully local generator removes external generation calls but adds substantially different hardware/model-delivery requirements. Other free API tiers could work, but this project does not establish a universal provider ranking.

**Tradeoff.** Local embeddings consume CPU/memory and need an initial model download. Groq's free plan has model-specific limits; free availability is not an unlimited or permanent guarantee. Selected source evidence leaves the machine when Groq generation is enabled.

**Evidence.** Local model identity/inference was exercised against the installed FastEmbed version. Real answer tests are ongoing. Provider references: [FastEmbed](https://qdrant.tech/documentation/embeddings/fastembed/), [Groq rate limits](https://console.groq.com/docs/rate-limits), and [Groq JSON output behavior](https://console.groq.com/docs/structured-outputs).

**Interview explanation.** Separate embedding and generation workloads, data transmission and operating costs. The architecture does not require them to use the same vendor.

## ADR-10 — Key vector reuse by actual input and effective model identity

**Problem.** The same model name can refer to changed assets, and the same source bytes can have different embedded path/symbol headers. Reusing incompatible vectors silently corrupts retrieval.

**Decision and reason.** Hash effective embedding input together with model/provider configuration, dimensions, preprocessing and local asset fingerprints. Keep cache vectors separate from source placement. A renamed path can intentionally require re-embedding because the path is part of the input.

**Alternative.** Cache by file hash or model name alone. It is cheaper to compute but ignores inputs that can change the vector space or representation.

**Tradeoff.** Computing the effective local-model fingerprint costs startup/import work. Some content-equivalent placements cannot reuse vectors. Model changes require another snapshot configuration rather than silently modifying ready content.

**Evidence.** [providers.py](../backend/app/providers.py), snapshot configuration hashes and the embedding cache identity. Expanded reuse/configuration tests remain part of implementation verification.

**Interview prompt.** “Tell me about a cache invalidation decision.” Explain what must be in the key and the intentional cost of conservative invalidation.

## ADR-11 — Validate generated output against bounded source evidence

**Problem.** A fluent answer can invent paths, cite another snapshot, or misinterpret a valid excerpt. Giving a generator unrestricted tools also broadens the execution and access boundary.

**Decision and reason.** Use a fixed bounded pipeline: retrieve → assemble → generate → validate → publish. Persist selected evidence before generation. Require structured answer segments with selected evidence IDs, validate schema/references/ranges/scope, and construct source URLs on the server. A failure is a failed run; insufficient evidence is a valid explicit outcome.

**Alternatives.** Trust free-form markdown citations, stream unvalidated output as final, or add an autonomous agent loop. Those approaches make evidence validation or behavior bounds harder to enforce at this stage.

**Tradeoff.** No unbounded exploration; some questions need more evidence than the context budget allows. Mechanical validation cannot prove semantic support. A model can still misunderstand correctly cited source, so human-reviewed support evaluation remains necessary.

**Evidence.** [test_answers.py](../tests/test_answers.py) checks invalid IDs, actual usage settlement, budget prevention and snapshot pinning. These deterministic-provider tests prove application contracts, not real-model answer quality.

**Interview explanation.** Describe citation integrity and claim support as two separate reliability problems. A token budget also differs from a guaranteed dollar-spending ceiling.

## ADR-12 — Persist answer runs; defer chat-memory semantics

**Problem.** Reopening an answer after a refresh should show what the user originally saw. Implicitly rebuilding it from current source changes its meaning.

**Decision and reason.** Retain the question/task, pinned snapshot, evidence selections, provider/retrieval configuration and validated output. History reopens independent runs. Export carries bounded evidence and source identity. The composer does not claim conversation memory.

**Alternatives.** Recompute an answer on open, retain only prose, or add multi-turn retrieval/memory immediately. Each makes historical attribution or request semantics more complicated.

**Tradeoff.** Repeated questions can be independent work. Historical sources and outputs require retention/storage policy. Exporting an answer is not a full database or repository backup.

**Evidence.** [models.py](../backend/app/models.py), [worker.py](../backend/app/worker.py), run read/export APIs and history UI. More database-level evidence normalization and purge checks should be tracked as hardening rather than assumed complete.

**Interview prompt.** “How did you make results reproducible?” Explain the retained inputs and configuration, while noting that recreating the same external model text is not guaranteed.

## ADR-13 — Use durable SSE progress and publish completed answers

**Problem.** Browser disconnects must not erase import progress, and the UI should not depend on an in-memory worker notification channel.

**Decision and reason.** Commit ordered job events before delivery. SSE replays events after `Last-Event-ID`; the browser deduplicates sequence IDs and reloads authoritative job state. Worker presence is separate from process/database readiness. Publish generated answers only after validation rather than treating streamed tokens as final evidence.

**Alternatives.** Polling alone is easy but repeatedly asks for unchanged state. WebSockets add a bidirectional protocol that this one-way progress flow does not require. In-memory-only events cannot reconstruct missed history.

**Tradeoff.** Reconnect/cursor expiry and event retention need explicit handling. SSE is progress streaming, not answer-token streaming. Authentication uses fetch-based streaming so the owner credential stays in headers.

**Evidence.** [main.py](../backend/app/main.py) event endpoint, [useJob.ts](../frontend/src/useJob.ts), [api.ts](../frontend/src/api.ts), durable replay API tests. Reconnect/reload browser coverage is being expanded.

**Interview explanation.** A notification tells the client that something changed; durable state determines what actually happened.

## ADR-14 — Follow the supplied design with a React/Vite SPA

**Problem.** The user already supplied detailed landing/dashboard/logo/light/dark boards. Inventing another dashboard would miss the brief even if the backend worked.

**Decision and reason.** Preserve the supplied fonts, imagery, palettes and three-pane repository/question/evidence composition. Use a React/TypeScript/Vite SPA backed by the Python API. Extract embedded assets without executing the reference packaging runtime. Adapt unsupported issue/caller/test claims to actual product capabilities.

**Alternatives.** Reuse the custom bundled reference runtime as the application, redesign the screens, or introduce a server-rendered frontend framework. None is needed for this owner-operated workspace and explicit backend architecture.

**Tradeoff.** The SPA needs a separate API and owner-connection state. Narrow screens switch among accessible panes instead of squeezing three desktop columns into a phone. Static mockups do not define every loading/failure state.

**Evidence.** [UI reference mapping](UI_REFERENCE.md), extracted assets, frontend components and desktop/mobile Playwright tests. Initial screenshots were inspected; this does not establish that every future UI change is correct.

**Interview prompt.** “How did you handle an existing design?” Explain how you preserved visual authority while reconciling product truth, accessibility and responsiveness.

## ADR-15 — Prove the local product before selecting hosting

**Problem.** Hosting, auth, inference and worker availability can add costs and credentials before the core product is demonstrable. The user explicitly chose local-first delivery.

**Decision and reason.** Use Docker PostgreSQL, local API/worker/frontend processes, loopback binding and a server-configured owner bearer credential. Keep the credential out of frontend builds and persistent browser storage. Use API port 8017 because an unrelated service already occupied 8000; make it configurable rather than terminating the other service.

**Alternatives.** Anonymous public access, a hosted multi-user auth system or immediate cloud workers. Those are different access/operating requirements and need a separate verified hosting gate.

**Tradeoff.** The owner must run the local processes and authenticate again after a browser reload. Local bearer access is not a completed remote authentication design. A worker-offline state leaves queued work pending rather than pretending imports are running.

**Evidence.** Local settings, container configuration, owner-negative tests, body-size checks, and the port-conflict correction. Hosted persistence, TLS, backups and remote auth are not claimed as shipped.

**Interview explanation.** Explain the scope of the security/operating model. Do not turn a local-demo decision into a claim of production readiness.

## ADR-16 — Evaluate retrieval, citation validity and semantic support separately

**Problem.** A polished demonstration can hide retrieval misses, incorrect source attribution or answers that overstate the evidence. Live repositories alone make failure/recovery scenarios difficult to reproduce.

**Decision and reason.** Begin with deterministic synthetic A/B source snapshots, known behavior, parser/security edge cases, and recorded connector/provider fixtures. Reserve development and held-out questions before tuning. Measure retrieval relevance separately from citation validity, claim support, abstention, latency and usage; add a real repository afterward.

**Alternatives.** Evaluate only answer fluency, tune against every question, or publish hoped-for accuracy/cost numbers. Those would not substantiate the reliability claims.

**Tradeoff.** Synthetic fixtures are narrower than real repository behavior. Human relevance/support review takes effort. Held-out results may show that hybrid is not better or that a release target is not met.

**Evidence.** [Acceptance plan](ACCEPTANCE_CRITERIA.md), fixture A/B and existing tests. The benchmark corpus/report and remaining recovery/real-provider checks are still being completed; no improvement percentage is asserted here.

**Interview prompt.** “How did you know it worked?” Name the failure cases and test/evaluation layers, then quote only results present in the final evidence report.

## ADR-17 — Make delivery reproducible and reviewable

**Problem.** A demo that depends on unrecorded dependencies, manual database changes or one large opaque commit is harder to reproduce and explain.

**Decision and reason.** Lock Python/frontend dependencies, use versioned database migrations, isolate PostgreSQL test schemas, preserve the UI source reference, and use focused commits on a private GitHub repository. The user explicitly requested at least 50 small commits, lowercase short messages, and continuing pushes; that is a delivery preference rather than an architectural quality metric.

**Alternatives.** Floating dependencies, mutable initial schema creation, or a single final dump. We corrected the initial migration to frozen DDL so later model edits do not silently change its meaning.

**Tradeoff.** More setup and migration maintenance. A commit count by itself proves neither feature completeness nor code quality. Private hosting of source is separate from deploying the application.

**Evidence.** [uv.lock](../uv.lock), frontend lockfile, migration revisions, isolated integration fixtures, Git history and the private [Understory repository](https://github.com/anushacodes/understory). Final test/push state must be checked at delivery.

**Interview prompt.** “Tell me about improving engineering quality.” Discuss reproducibility and review boundaries, not the number of commits as a performance result.

## Turning these into behavioral answers

Use the decisions above as evidence for a truthful STAR outline:

1. **Situation:** a developer needs to understand an unfamiliar repository, with a fixed UI reference and a free-first local operating constraint.
2. **Task:** build a usable system whose imports recover and whose explanations can be inspected against one source baseline.
3. **Action:** choose one concrete decision, explain the rejected alternative and tradeoff, then show the relevant code/test or observed failure.
4. **Result:** report only verified outcomes from the final evaluation/test record. During implementation say “implemented and tested in controlled scenarios,” not “production proven.”

Useful story pairings:

| Interview theme | Decisions to study | Evidence to bring |
| --- | --- | --- |
| Prioritization and ambiguity | ADR-01, ADR-15 | Corrected scope, retained UI direction, local-first decision |
| Reliability and ownership | ADR-04, ADR-05, ADR-13 | Stale-worker rejection, failed-refresh preservation, progress replay |
| Technical tradeoffs | ADR-02, ADR-03, ADR-08 | Shared-service boundaries, transactional publication, retrieval comparison |
| Cost awareness | ADR-09, ADR-10, ADR-11 | Local inference, compatible vector reuse, usage ceilings/actual consumption |
| Trust and safety | ADR-06, ADR-07, ADR-11 | Inert malicious inputs, exact ranges, invalid-citation rejection |
| Collaboration and product judgment | ADR-01, ADR-14 | User correction propagated into contracts and UI behavior |
| Learning and correction | ADR-15, ADR-17 | Non-destructive port correction, isolated test schemas, frozen migrations |

Do not invent a team disagreement, production incident, user count, latency reduction or accuracy improvement. Explain what you personally built/reviewed and what assistance was used. This document records technical reasoning, not a claim that every project action was performed unaided.

## When to amend this record

For each new material decision, add the concrete trigger, chosen approach, alternatives, tradeoffs, implemented/planned status, and a code/test/report reference. When replacing a decision, preserve the old rationale and explain the new evidence rather than rewriting history. Before interviews, review the latest implementation/evaluation status so examples reflect what actually shipped.
