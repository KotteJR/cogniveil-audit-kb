from __future__ import annotations

import shutil
from pathlib import Path

from fetch.connectors.base import FetchOutcome
from fetch.manifest import build_content_files, write_document_meta
from fetch.registry import SourceSpec


def fetch_manual_inbox(
    source: SourceSpec,
    doc_dir: Path,
    *,
    delta: bool,
    existing_meta: dict | None,
    staging_root: Path,
) -> FetchOutcome:
    inbox_dir = staging_root / "manual-inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    filename = source.inbox_filename or source.expected_filename
    if not filename:
        return FetchOutcome(
            source.source_key,
            "failed",
            "manual_inbox requires inbox_filename or expected_filename",
            doc_dir,
        )

    inbox_path = inbox_dir / filename
    if not inbox_path.is_file():
        doc_dir.mkdir(parents=True, exist_ok=True)
        write_document_meta(
            doc_dir,
            source_key=source.source_key,
            scope=source.scope,
            phase=source.phase,
            connector=source.connector,
            audit_lane=source.audit_lane,
            jurisdiction=source.jurisdiction,
            publisher=source.publisher,
            title=source.title or source.source_key,
            framework_id=source.framework_id,
            version=source.version,
            effective_date=source.effective_date,
            language="en",
            canonical_url=f"manual-inbox://{filename}",
            license_tier=source.license_tier or "purchased",
            content_files=[],
            fetch_status="pending",
            fetch_error=f"Awaiting file in manual-inbox/{filename}",
            extra={"inbox_filename": filename},
        )
        return FetchOutcome(
            source.source_key,
            "failed",
            f"File not in manual-inbox: {filename}",
            doc_dir,
        )

    doc_dir.mkdir(parents=True, exist_ok=True)
    dest_name = source.expected_filename or "content.pdf"
    dest = doc_dir / dest_name

    if delta and existing_meta and dest.is_file():
        old_files = existing_meta.get("content_files") or []
        if old_files:
            from fetch.manifest import sha256_file

            new_hash = sha256_file(inbox_path)
            if old_files[0].get("sha256") == new_hash:
                return FetchOutcome(
                    source.source_key,
                    "skipped",
                    "inbox file unchanged",
                    doc_dir,
                )

    shutil.copy2(inbox_path, dest)
    mime = "application/pdf" if dest.suffix.lower() == ".pdf" else "application/octet-stream"
    content_files = build_content_files(doc_dir, [(dest_name, mime)])

    write_document_meta(
        doc_dir,
        source_key=source.source_key,
        scope=source.scope,
        phase=source.phase,
        connector=source.connector,
        audit_lane=source.audit_lane,
        jurisdiction=source.jurisdiction,
        publisher=source.publisher,
        title=source.title or source.source_key,
        framework_id=source.framework_id,
        version=source.version,
        effective_date=source.effective_date,
        language="en",
        canonical_url=f"manual-inbox://{filename}",
        license_tier=source.license_tier or "purchased",
        content_files=content_files,
        fetch_status="complete",
        ready_for_ingest=False,
        extra={"inbox_filename": filename, "promoted_from": str(inbox_path)},
    )
    return FetchOutcome(source.source_key, "complete", "", doc_dir)
