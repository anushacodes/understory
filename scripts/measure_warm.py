"""Measure warm, sequential local retrieval separately from one-pass quality metrics."""

import json
import math
import platform
import statistics
import time
from pathlib import Path

from app.config import settings
from app.connectors import FixtureConnector
from app.db import SessionLocal
from app.models import Repository, Snapshot
from app.retrieval import search
from sqlalchemy import select


def main():
    with SessionLocal() as session:
        repo = session.scalar(select(Repository).where(Repository.name == "understory/fixture"))
        sha = FixtureConnector(settings).resolve(repo.name, "a")
        snapshots = session.scalars(
            select(Snapshot).where(
                Snapshot.repository_id == repo.id, Snapshot.commit_sha == sha, Snapshot.state == "ready"
            )
        ).all()
        snapshot = next(s for s in snapshots if "hybrid" in s.coverage.get("capabilities", []))
        questions = [
            item["query"]
            for item in json.loads(Path("evals/questions.json").read_text())
            if item["split"] == "development"
        ]
        started = time.perf_counter()
        search(session, repo.id, questions[0], snapshot.id, mode="hybrid")
        cold = (time.perf_counter() - started) * 1000
        samples = []
        for _ in range(5):
            for query in questions:
                started = time.perf_counter()
                search(session, repo.id, query, snapshot.id, mode="hybrid")
                samples.append((time.perf_counter() - started) * 1000)
        ordered = sorted(samples)
        report = {
            "corpus": "synthetic fixture A",
            "snapshot_id": snapshot.id,
            "commit_sha": sha,
            "model_configuration": snapshot.config,
            "environment": platform.platform(),
            "method": "Sequential hybrid retrieval, one cold call then five repeats of sixteen development queries. No concurrent load.",
            "cold_ms": round(cold, 3),
            "warm_samples": len(samples),
            "warm_p50_ms": round(statistics.median(samples), 3),
            "warm_p95_ms": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 3),
            "warm_samples_ms": [round(value, 3) for value in samples],
        }
    Path("evals/reports/warm.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        {key: value for key, value in report.items() if key not in {"model_configuration", "warm_samples_ms"}}
    )


if __name__ == "__main__":
    main()
