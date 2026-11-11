import argparse

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.jobs import digest, enqueue
from app.models import Job, Repository
from app.worker import run_once


def main():
    parser = argparse.ArgumentParser(
        description="Import the inert, explicitly synthetic Understory source fixture."
    )
    parser.add_argument("--snapshot", choices=["a", "b"], default="a")
    args = parser.parse_args()
    with SessionLocal.begin() as session:
        repo = session.scalar(select(Repository).where(Repository.name == "understory/fixture"))
        if not repo:
            repo = Repository(name="understory/fixture")
            session.add(repo)
            session.flush()
        key = "demo-" + digest({"snapshot": args.snapshot, "config": settings.indexing_config()})
        job, _ = enqueue(session, repo.id, "import", {"ref": args.snapshot}, key)
        job_id, repo_id = job.id, repo.id
    while run_once():
        with SessionLocal() as session:
            if session.get(Job, job_id).status in {"succeeded", "failed", "cancelled", "retry_wait"}:
                break
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        print(f"Synthetic fixture repository: {repo_id}")
        print(f"Import status: {job.status}")
        if job.error:
            print(f"Error: {job.error['code']}: {job.error['message']}")
        elif job.result:
            print(f"Synthetic content SHA: {job.result['commit_sha']}")
            print(f"Coverage: {job.result['coverage']}")


if __name__ == "__main__":
    main()
