"""Back up the local development DB and verify a restore into a disposable DB."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

PREFIX = ["docker", "compose", "-p", "understory-local", "exec", "-T", "database"]
COUNTS = "SELECT (SELECT count(*) FROM repositories), (SELECT count(*) FROM snapshots WHERE state='ready'), (SELECT count(*) FROM answer_runs WHERE output IS NOT NULL), (SELECT count(*) FROM run_evidence), (SELECT count(*) FROM source_versions)"


def psql(database, sql):
    return subprocess.check_output(
        [*PREFIX, "psql", "-U", "understory", "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", sql],
        text=True,
    ).strip()


def main():
    backup = Path(".cache/backups/understory.dump")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("wb") as stream:
        subprocess.run(
            [*PREFIX, "pg_dump", "-U", "understory", "-Fc", "understory"], stdout=stream, check=True
        )
    before = psql("understory", COUNTS)
    target = "restore_check_" + uuid4().hex
    psql("understory", f"CREATE DATABASE {target}")
    try:
        with backup.open("rb") as stream:
            subprocess.run(
                [*PREFIX, "pg_restore", "-U", "understory", "--exit-on-error", "-d", target],
                stdin=stream,
                check=True,
            )
        restored = psql(target, COUNTS)
        assert before == restored, (before, restored)
        invalid = psql(
            target,
            "SELECT count(*) FROM run_evidence e LEFT JOIN snapshot_files f ON f.snapshot_id=e.snapshot_id AND f.source_version_id=e.source_version_id AND f.path=e.path LEFT JOIN source_versions v ON v.id=e.source_version_id WHERE f.id IS NULL OR e.start_line<1 OR e.end_line>v.line_count",
        )
        assert invalid == "0", invalid
        result = {
            "method": "pg_dump custom format; pg_restore into disposable database",
            "counts": dict(
                zip(
                    [
                        "repositories",
                        "ready_snapshots",
                        "successful_runs",
                        "evidence_rows",
                        "source_versions",
                    ],
                    map(int, before.split("|")),
                    strict=True,
                )
            ),
            "restored_counts_match": True,
            "invalid_evidence_rows": int(invalid),
        }
        Path("evals/reports/restore.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    finally:
        psql("understory", f"DROP DATABASE {target}")


if __name__ == "__main__":
    main()
