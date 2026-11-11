# Local operations

Run commands from the project root. Preserve `.env`; it is ignored by Git. Start and upgrade using the [README](../README.md). The Docker volume survives `docker compose stop`; `down -v` destroys it and is not a restart command.

## Inspect and recover work

API `/v1/ready` checks the database migration revision. Repository details report worker presence separately; a healthy API can still have an offline worker. The UI reloads accepted work from persisted repository/job state after reconnecting with the owner token.

Restart `understory-worker` after a crash. A running job is eligible for reclaim after its lease expires (60 seconds by default). Fencing rejects writes from the old attempt. Retries retain the resolved SHA, committed batches and active-time/request budgets; the old active snapshot stays usable. Maximum attempts: 3. Active execution budgets: 900 seconds for imports, 90 for answers, excluding queue/backoff time. A single bounded network call can finish just after the deadline; the following checkpoint prevents publication. Cancellation is cooperative at bounded checkpoints, with queued work cancelled immediately.

The job panel shows stage, attempts and structured errors. Use its cancellation button before purging. API access requires `Authorization: Bearer <owner token>`; never put tokens in URLs or paste `.env` into logs. Terminal runs remain in History even when a provider fails. A successful answer is published only after schema, selected evidence ID, source range and snapshot checks.

If Groq returns `model_unavailable`, choose a model accessible to your account in `.env` and restart API/worker. A failed terminal run is retained; submit a new question rather than modifying its history. Transient provider failures use bounded retry delays, including capped `Retry-After`. Unknown provider usage retains its full reservation, so failed calls can exhaust the daily application budget. Daily accounting resets at UTC midnight. Do not raise the limit just to make a test pass.

## Refresh or change models

Use Import with a new ref. The worker resolves it once, builds staging content, checks placements/vectors, then activates atomically if this is still the latest requested import. Old baselines remain available. Reimport after changing embedding model, assets or parser/chunker configuration; incompatible vectors cannot be mixed with the old snapshot. Exact and lexical search can still use old snapshots, and explicit API lexical fallback is labeled.

The first model load downloads assets into `.cache/models`; later loads use the local cache. Set `EMBEDDING_PROVIDER=disabled` and reimport for a model-free exact/lexical snapshot. This does not silently upgrade or downgrade existing snapshots.

## Retention and purge

Run explicit retention cleanup after stopping the worker, or during an idle maintenance window:

```sh
uv run python -m app.maintenance
```

It removes terminal progress events and unreferenced failed/staging snapshots older than seven days, then collects unreferenced source/vector rows. Ready snapshots, saved runs and job/idempotency summaries remain until owner purge. Expired SSE cursors return `410`; the client reloads durable job state and resets its cursor.

The import ceiling is **retained source bytes** (default 512 MiB), not total physical database size. Vectors, indexes, events, backups and PostgreSQL overhead also consume disk; inspect Docker volume usage. A new import fails rather than deleting retained evidence. This bounded local source policy is not an unlimited-storage promise.

Export important answers from the UI first. Repository deletion is the authenticated `DELETE /v1/repositories/{id}` API. It refuses pending jobs, removes the repository and dependent data, and only collects vectors with no remaining references. The two-repository integration test verifies isolation. There is no automatic purge.

## Backup and restore

For a consistent backup while active writes may occur, PostgreSQL `pg_dump` takes a database snapshot. To compare row counts in the verification drill, keep the app idle while it runs:

```sh
uv run python scripts/check_restore.py
```

The script writes `.cache/backups/understory.dump`, restores into a uniquely named disposable database, compares repository/snapshot/source/run/evidence counts, checks evidence membership/ranges, and drops only that disposable database. [Recorded result](../evals/reports/restore.json). The dump contains repository source and questions/answers; store it on a protected disk. Keep `.env` separately; this dump does not back up provider credentials or the local model cache.

For actual recovery, stop API/worker, create a **new database** in PostgreSQL, restore the dump there with `pg_restore --exit-on-error`, point `DATABASE_URL` to that database, run migrations, inspect readiness and retained sources, then restart API/worker. Keep the previous database until recovery is verified. The automated drill intentionally does not replace or delete the live database.

## Reproduce release evidence

```sh
uv run --extra embeddings python -m app.evaluate --split development --output .cache/development-rerun.json
uv run --extra embeddings python -m app.evaluate --split held_out --output .cache/held-out-rerun.json
uv run --extra embeddings python scripts/measure_warm.py
```

Committed reports preserve the first development/held-out measurements. Do not tune against held-out questions. `scripts/verify_live.py` performs explicitly authorized real Groq calls and the real-repository import; it refuses to overwrite an existing `evals/reports/live.json`. Preserve prior reports before intentionally running another quota-consuming demonstration.

With the live fixtures prepared, full release browser checks are:

```sh
UNDERSTORY_LIVE_TESTS=1 UNDERSTORY_TEST_WORKER_PID=<project-worker-pid> \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" npm test --prefix frontend
```

Only supply the PID of this project's worker. The recovery check verifies its command and working directory before pausing it (using local `ps` and `lsof`). The desktop recovery test pauses that worker, reloads a queued import, waits for worker presence to expire, cancels the job, and resumes the worker in `finally`. The owner token is deliberately memory-only, so reauthentication after a full page reload is expected. To rerun UI checks without another provider call, optionally set `UNDERSTORY_REPLAY_KEY` to the idempotency key of a successful same-body question job in this database; a changed snapshot/body correctly returns an idempotency conflict.
