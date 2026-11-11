# Understory

Understand an unfamiliar repository through structural exploration, search, and source-backed explanations.

**Status: planning only. No application scaffold or runnable quickstart exists yet.** Updated November 10, 2026.

Understory focuses exclusively on repository understanding. Import a small public Python repository, explore its structure, search for relevant code, ask questions, and inspect the exact source behind each explanation. Issue/PR investigation and contribution research are outside the product scope.

## Planning artifacts

| Document | Purpose |
| --- | --- |
| [MVP scope and user journey](docs/MVP_SCOPE.md) | Product boundary, included behavior, workspace flow, proposed operating defaults and demonstration |
| [Acceptance criteria](docs/ACCEPTANCE_CRITERIA.md) | Observable gates, synthetic fixture design, evaluation split, verification methods and release evidence |
| [Technical specification](docs/TECHNICAL_SPEC.md) | Architecture, identities, source policy, proposed limits, jobs, snapshot publication, retrieval, answers and API contracts |
| [Implementation backlog](docs/IMPLEMENTATION_BACKLOG.md) | Ordered tasks, dependencies, milestone exits and optional delivery work |
| [UI reference mapping](docs/UI_REFERENCE.md) | Supplied HTML boards, visual identity, screen composition and scope-compatible behavior |
| [Project plan](PROJECT_PLAN.md) | Short project overview and decision summary |

These documents replace the earlier repository-plus-contribution-research blueprint. Repository understanding and the supplied HTML's role as UI reference are user-confirmed; operating defaults, limits and technical details are proposals for review.

## Intended experience

1. The owner registers an approved public Python repository and requests an import at a ref.
2. Durable progress shows stages, retries, coverage and worker availability.
3. A ready snapshot opens with a file tree, inventory, symbols and selected commit.
4. The developer searches exact symbols or concepts and opens stored source ranges.
5. An on-demand overview and independent questions return explanations with citations and limitations.
6. A later import updates the active baseline safely; older answers retain their original evidence.

Example questions:

- Where does this project validate incoming requests?
- How does this request handler delegate to storage?
- Which modules define the public interface?
- What do the configuration and tests say about this behavior?

Answers describe inspected source, not executed behavior. A missing result does not establish repository-wide absence.

## Core design

A Python API and separate durable worker share one PostgreSQL database with vector support. A web frontend exposes import progress, overview, search, source viewing and cited Q&A. Source is pinned to a full commit SHA; incomplete imports remain unsearchable. Exact/lexical search stays useful during model failure.

The existing proposed stack is retained, with dependency versions and model providers to be verified before implementation. There is no autonomous code execution, issue/PR ingestion, code editing, multi-agent system, or second scheduler.

Proposed initial delivery is an owner-operated local demo. A hosted showcase is optional and requires a separate cost/access readiness gate. The $0 showcase objective is an aspiration, not a verified hosting or inference guarantee. Real-provider calls require a selected provider, explicit usage ceilings and a source-transmission decision.

## Implementation sequence

| Milestone | Result |
| --- | --- |
| M0 | Reviewed contracts, decisions, synthetic A/B fixture and labeled questions |
| M1 | Durable safe import, leases/checkpoints, atomic publication and event replay |
| M2 | Structural parsing, symbols, lexical search, inventory and source viewer |
| M3 | Compatible embeddings, semantic/hybrid search and retrieval comparison |
| M4 | Cited overview and questions, validation, durable runs and export |
| M5 | Refresh, retention/purge, boundary checks, evaluation and local demo |

No milestone is complete merely because its specification exists. The backlog defines exit evidence. MCP and measured retrieval extensions may follow the local MVP; issue research is not a later milestone.

## Before implementation

Review [the decision register](docs/TECHNICAL_SPEC.md#decision-register), especially local versus hosted delivery, owner access, provider budget, source transmission and proposed limits. Select exact dependency versions during foundation work and models before real integration. Numeric quality/latency/cost thresholds need a development baseline before they can be frozen.

There are no installation commands yet because the application entry points, manifests and migrations do not exist. This planning work does not authorize implementation, paid-service activation, deployment, Git commits or pushes.

## UI and architecture references

[Understory.html](Understory.html) is the user-supplied visual reference for the UI. Follow its landing page, three-pane dashboard, logo, typography and light/dark treatments. [UI_REFERENCE.md](docs/UI_REFERENCE.md) maps its boards to the repository-only product and identifies mock features/copy that need scope correction. The canyon landing is a supplied alternative, not a silently selected replacement. The original HTML remains intact.

[architecture.svg](architecture.svg) remains an earlier architecture concept and may contain contribution-research components. The technical specification governs current architecture; the HTML governs the supplied visual direction and the MVP scope governs behavior.

## Evaluation and limitations

Begin with a labeled synthetic repository at two source snapshots, recorded connector responses and 24 questions split into development and held-out sets. Add a small real repository after the fixture workflow works. Measure retrieval separately from citation validity and human-reviewed claim support. Publish actual corpus/configuration, recovery evidence, latency, usage and limitations.

Static parsing has incomplete knowledge of runtime behavior. Retrieval can miss relevant evidence, and generation can misinterpret valid excerpts. Coverage and uncertainty must remain visible. Private repositories, additional language parsers, arbitrary large imports and public self-service access require separate scope decisions.
