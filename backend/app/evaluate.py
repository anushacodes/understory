"""Reproducible retrieval evaluation; generation and claim support are separate."""

import argparse
import hashlib
import json
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.connectors import FixtureConnector
from app.db import SessionLocal
from app.models import Repository, Snapshot
from app.retrieval import search

ROOT = Path(__file__).resolve().parents[2]


def relevant(hit: dict, unit: dict) -> bool:
    return (
        hit["path"] == unit["path"]
        and hit["start_line"] <= unit["end_line"]
        and hit["end_line"] >= unit["start_line"]
    )


def score(hits: list[dict], units: list[dict]) -> tuple[float | None, float | None]:
    if not units:
        return None, None
    recall = sum(any(relevant(hit, unit) for hit in hits[:5]) for unit in units) / len(units)
    reciprocal = next(
        (1 / rank for rank, hit in enumerate(hits[:10], 1) if any(relevant(hit, unit) for unit in units)), 0.0
    )
    return recall, reciprocal


def run(split: str, output: Path):
    question_file = ROOT / "evals/questions.json"
    question_bytes = question_file.read_bytes()
    questions = [item for item in json.loads(question_bytes) if item["split"] == split]
    with SessionLocal() as session:
        repo = session.scalar(select(Repository).where(Repository.name == "understory/fixture"))
        if not repo:
            raise SystemExit("Import the synthetic fixture with `understory-demo` first.")
        sha = FixtureConnector(settings).resolve(repo.name, "a")
        snapshots = session.scalars(
            select(Snapshot)
            .where(Snapshot.repository_id == repo.id, Snapshot.commit_sha == sha, Snapshot.state == "ready")
            .order_by(Snapshot.ready_at.desc())
        ).all()
        snapshot = next((s for s in snapshots if "hybrid" in s.coverage.get("capabilities", [])), None)
        if not snapshot:
            raise SystemExit(
                "Reimport fixture A with EMBEDDING_PROVIDER=fastembed before evaluating all modes."
            )
        rows = []
        for mode in ("exact", "lexical", "semantic", "hybrid"):
            for item in questions:
                started = time.perf_counter()
                result = search(session, repo.id, item["query"], snapshot.id, mode=mode, limit=10)
                elapsed = (time.perf_counter() - started) * 1000
                recall, reciprocal = score(result["results"], item["relevance"])
                rows.append(
                    {
                        "question_id": item["id"],
                        "query": item["query"],
                        "category": item["category"],
                        "mode": mode,
                        "recall_at_5": recall,
                        "mrr_at_10": reciprocal,
                        "latency_ms": round(elapsed, 3),
                        "relevance": item["relevance"],
                        "results": [
                            {k: hit[k] for k in ("path", "label", "start_line", "end_line")}
                            for hit in result["results"]
                        ],
                    }
                )
        summary = {}
        for mode in ("exact", "lexical", "semantic", "hybrid"):
            answerable = [row for row in rows if row["mode"] == mode and row["recall_at_5"] is not None]
            latencies = sorted(row["latency_ms"] for row in rows if row["mode"] == mode)
            summary[mode] = {
                "answerable_questions": len(answerable),
                "recall_at_5": statistics.mean(row["recall_at_5"] for row in answerable),
                "mrr_at_10": statistics.mean(row["mrr_at_10"] for row in answerable),
                "latency_p50_ms": statistics.median(latencies),
                "latency_p95_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
                "latency_samples": len(latencies),
            }
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "corpus": "synthetic fixture A",
            "commit_sha": sha,
            "snapshot_id": snapshot.id,
            "configuration": snapshot.config,
            "coverage": snapshot.coverage,
            "questions_sha256": hashlib.sha256(question_bytes).hexdigest(),
            "split": split,
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            "method": "One pass per mode in fixed order. First semantic query includes cold model initialization; small sample sizes. Relevance is path plus overlapping labeled original range. Unanswerable questions excluded from Recall/MRR and reported individually.",
            "summary": summary,
            "queries": rows,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"Report written to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["development", "held_out"], default="development")
    parser.add_argument("--output", type=Path, default=ROOT / "evals/reports/development.json")
    args = parser.parse_args()
    run(args.split, args.output)


if __name__ == "__main__":
    main()
