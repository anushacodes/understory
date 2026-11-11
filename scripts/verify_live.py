"""Opt-in real-provider release check. Uses configured local credentials without printing them."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from app.config import settings
from app.connectors import FixtureConnector
from app.db import SessionLocal
from app.models import Repository, Snapshot
from sqlalchemy import select


def main():
    output = Path("evals/reports/live.json")
    if output.exists():
        raise SystemExit(
            "A live report already exists. Preserve it before explicitly running new paid/quota-limited calls."
        )
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "provider": settings.generation_provider,
        "model": settings.generation_model,
        "cases": [],
    }
    with httpx.Client(
        base_url=f"http://127.0.0.1:{settings.api_port}/v1",
        headers={"Authorization": f"Bearer {settings.owner_token}"},
        timeout=35,
        trust_env=False,
    ) as api:

        def post(path, body, key):
            result = api.post(path, json=body, headers={"Idempotency-Key": key})
            result.raise_for_status()
            return result.json()

        def wait(accepted):
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                response = api.get(f"/jobs/{accepted['job_id']}")
                response.raise_for_status()
                job = response.json()
                if job["status"] in {"succeeded", "failed", "cancelled"}:
                    if job["status"] != "succeeded":
                        raise RuntimeError(f"Live check failed: {job['error']}")
                    return job
                time.sleep(0.75)
            raise RuntimeError("Live check exceeded 180 seconds; inspect durable job state.")

        repo = post("/repositories", {"github_repository": "pallets/itsdangerous"}, "release-public-repo")
        started = time.monotonic()
        imported = wait(
            post(f"/repositories/{repo['id']}/imports", {"ref": "2.2.0"}, "release-itsdangerous-2.2.0")
        )
        license_response = httpx.get(
            "https://raw.githubusercontent.com/pallets/itsdangerous/"
            + imported["commit_sha"]
            + "/LICENSE.txt",
            follow_redirects=False,
            timeout=30,
            trust_env=False,
        )
        license_response.raise_for_status()
        report["real_repository"] = {
            "name": repo["name"],
            "requested_ref": "2.2.0",
            "commit_sha": imported["commit_sha"],
            "coverage": imported["result"]["coverage"],
            "import_seconds": round(time.monotonic() - started, 3),
            "license": "BSD-3-Clause",
            "license_url": str(license_response.url),
        }
        with SessionLocal() as session:
            fixture = session.scalar(select(Repository).where(Repository.name == "understory/fixture"))
            sha = FixtureConnector(settings).resolve(fixture.name, "a")
            snapshots = session.scalars(
                select(Snapshot).where(
                    Snapshot.repository_id == fixture.id,
                    Snapshot.commit_sha == sha,
                    Snapshot.state == "ready",
                )
            ).all()
            snapshot = next(s for s in snapshots if "hybrid" in s.coverage.get("capabilities", []))
            fixture_id, snapshot_id = fixture.id, snapshot.id
        cases = [
            ("single_file", "Which account and amount fields must a valid transfer contain?", False),
            ("multi_file", "How does create_transfer delegate to TransferService and LedgerStore?", False),
            ("overview", "", True),
            ("held-07", "What is the production encryption key value?", False),
            ("held-08", "Who reviewed the latest open pull request?", False),
        ]
        for label, question, overview in cases:
            started = time.monotonic()
            body = (
                {"snapshot_id": snapshot_id}
                if overview
                else {"question": question, "snapshot_id": snapshot_id, "retrieval_mode": "hybrid"}
            )
            accepted = post(
                f"/repositories/{fixture_id}/{'overviews' if overview else 'questions'}",
                body,
                "release-live-" + label,
            )
            job = wait(accepted)
            result = api.get(f"/runs/{accepted['run_id']}/export")
            result.raise_for_status()
            exported = result.json()
            report["cases"].append(
                {"label": label, "seconds": round(time.monotonic() - started, 3), **exported}
            )
            # Write partial progress so interrupted verification does not silently spend again.
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(label, job["status"], exported["output"]["outcome"], flush=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
    print("Live verification report saved; no credentials included.")


if __name__ == "__main__":
    main()
