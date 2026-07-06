from __future__ import annotations

import shutil
from pathlib import Path

from git import Repo

from fetch.connectors.base import FetchOutcome
from fetch.manifest import write_document_meta
from fetch.registry import SourceSpec


def fetch_oscal_git(
    source: SourceSpec,
    doc_dir: Path,
    *,
    delta: bool,
    existing_meta: dict | None,
) -> FetchOutcome:
    if not source.repo:
        return FetchOutcome(
            source.source_key,
            "failed",
            "oscal_git connector requires repo field",
            doc_dir,
        )

    doc_dir.mkdir(parents=True, exist_ok=True)
    clone_dir = doc_dir / "oscal-content"
    commit_sha = ""

    try:
        if clone_dir.is_dir() and (clone_dir / ".git").is_dir():
            repo = Repo(clone_dir)
            origin = repo.remotes.origin
            origin.fetch()
            repo.git.checkout(source.ref)
            if delta:
                before = repo.head.commit.hexsha
                origin.pull()
                after = repo.head.commit.hexsha
                commit_sha = after
                if before == after and existing_meta:
                    old_sha = (existing_meta.get("git_commit_sha") or "").strip()
                    if old_sha == after:
                        return FetchOutcome(
                            source.source_key,
                            "skipped",
                            "git commit unchanged",
                            doc_dir,
                        )
            else:
                origin.pull()
                commit_sha = repo.head.commit.hexsha
        else:
            if clone_dir.exists():
                shutil.rmtree(clone_dir)
            repo = Repo.clone_from(source.repo, clone_dir, branch=source.ref)
            commit_sha = repo.head.commit.hexsha
    except Exception as exc:
        write_document_meta(
            doc_dir,
            source_key=source.source_key,
            scope=source.scope,
            phase=source.phase,
            connector=source.connector,
            audit_lane=source.audit_lane,
            jurisdiction=source.jurisdiction,
            publisher=source.publisher or "NIST",
            title=source.title or source.source_key,
            framework_id=source.framework_id,
            version=source.version,
            effective_date=source.effective_date,
            language="en",
            canonical_url=source.repo,
            license_tier=source.license_tier,
            content_files=[],
            fetch_status="failed",
            fetch_error=str(exc),
            extra={"repo": source.repo, "ref": source.ref},
        )
        return FetchOutcome(source.source_key, "failed", str(exc), doc_dir)

    write_document_meta(
        doc_dir,
        source_key=source.source_key,
        scope=source.scope,
        phase=source.phase,
        connector=source.connector,
        audit_lane=source.audit_lane,
        jurisdiction=source.jurisdiction,
        publisher=source.publisher or "NIST",
        title=source.title or source.source_key,
        framework_id=source.framework_id,
        version=source.version,
        effective_date=source.effective_date,
        language="en",
        canonical_url=source.repo,
        license_tier=source.license_tier,
        content_files=[
            {
                "path": "oscal-content",
                "mime": "application/vnd.git-repo",
                "sha256": commit_sha,
            }
        ],
        fetch_status="complete",
        ready_for_ingest=False,
        extra={
            "repo": source.repo,
            "ref": source.ref,
            "git_commit_sha": commit_sha,
        },
    )
    return FetchOutcome(source.source_key, "complete", "", doc_dir)
