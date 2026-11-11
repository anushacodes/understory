# Understory

Understand a small public Python repository through search, static source exploration, and cited explanations. Imports and answers stay pinned to immutable source snapshots. The meadow UI follows the supplied HTML, with light and dark themes.

The local MVP includes a durable worker, safe GitHub imports, exact/lexical/semantic/hybrid search, source-range citations, generated overviews, saved questions, exports, refreshes and owner purge. Imported code is never executed.

## Run locally

Requirements: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ (validated here with Node 26). Run commands from the repository root.

```sh
uv sync --locked --extra embeddings
npm ci --prefix frontend
cp .env.example .env  # only on first setup; preserve an existing .env
```

Set `OWNER_TOKEN` in `.env` to a random value generated locally:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

The server reads `.env`; the frontend never receives provider keys. `EMBEDDING_PROVIDER=fastembed` downloads and runs the BGE small model locally. Set it to `disabled` for exact/lexical exploration without model downloads. Semantic snapshots require a reimport after changing model configuration.

```sh
docker compose -p understory-local up -d database
uv run alembic upgrade head
uv run --extra embeddings understory-demo
```

Start these in separate terminals:

```sh
uv run --extra embeddings understory-api
uv run --extra embeddings understory-worker
npm run dev --prefix frontend
```

Open **http://127.0.0.1:5173**, choose **Open Understory**, and enter your owner token. The API uses **8017**; PostgreSQL uses **54329**. API health/readiness are `/v1/health` and `/v1/ready`; the authenticated contract is available at `/api-docs`.

The demo is clearly labeled synthetic. To import a real repository, add its canonical `owner/name` to `ALLOWED_REPOSITORIES`, restart API/worker, then use the import form. `pallets/itsdangerous` at tag `2.2.0` was verified. Keep imports small: compressed archive 20 MiB, expanded content 100 MiB, supported text 20 MiB, 5,000 entries, 512 KiB per file. Python, Markdown/RST and selected text configs are supported; inventory explains exclusions.

## Enable Groq answers

Configure locally, then restart API and worker:

```dotenv
GENERATION_PROVIDER=groq
GENERATION_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=your_local_key
DAILY_TOKEN_BUDGET=50000
```

That model passed real inference with this account; account availability can differ. Generation sends the question and selected source excerpts to Groq. Embeddings stay local. The daily limit accounts for actual usage when returned and conservative reservations when usage is unknown. It does not override provider quotas. Search remains available when generation is unavailable.

## Verify

With PostgreSQL running, deterministic tests use isolated schemas and do not call Groq:

```sh
uv run ruff check backend migrations tests scripts
uv run pytest -q
npm run build --prefix frontend
```

For browser checks, start API, worker and frontend and seed fixture A first. Browser downloads are local tooling:

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" npm exec --prefix frontend -- playwright install chromium
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" npm test --prefix frontend
```

Real generation tests are opt-in and consume the configured quota. See [verification evidence](docs/VERIFICATION.md) for all release checks, [operations](docs/OPERATIONS.md) for recovery/retention/backup, and [evaluation](evals/README.md) for corpus labels, frozen targets and reproducible commands.

## Study the project

- [Architecture decisions and interview notes](docs/ARCHITECTURE_DECISIONS.md): reasons, alternatives, tradeoffs, evidence and behavioral prompts.
- [Technical specification](docs/TECHNICAL_SPEC.md): identities, boundaries, jobs and contracts.
- [MVP scope](docs/MVP_SCOPE.md), [acceptance gates](docs/ACCEPTANCE_CRITERIA.md), and [milestone evidence](docs/IMPLEMENTATION_BACKLOG.md).
- [UI reference mapping](docs/UI_REFERENCE.md) and the original [Understory.html](Understory.html).

Local owner operation is the delivery target. Hosting, anonymous access, private-repository imports, additional language parsers and MCP are outside this MVP. Small controlled evaluation results do not establish general answer accuracy or production throughput. Source citation validation checks provenance and references; human review is still needed to assess whether a claim follows from a source.

The source repository is private. No project-wide redistribution license has been selected. Bundled third-party notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
