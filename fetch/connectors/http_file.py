from __future__ import annotations

from pathlib import Path

from fetch.connectors.base import FetchOutcome
from fetch.http_utils import download_url, mime_from_content_type
from fetch.manifest import (
    atomic_write_bytes,
    build_content_files,
    write_document_meta,
)
from fetch.registry import SourceSpec


def _output_name(source: SourceSpec, filename: str) -> str:
    if source.expected_filename:
        return source.expected_filename
    lower = filename.lower()
    if lower.endswith((".pdf", ".html", ".json", ".csv", ".xml", ".zip")):
        ext = lower.rsplit(".", 1)[-1]
        return f"content.{ext}"
    if "pdf" in lower:
        return "content.pdf"
    return "content.bin"


def fetch_http_file(
    source: SourceSpec,
    doc_dir: Path,
    *,
    delta: bool,
    existing_meta: dict | None,
) -> FetchOutcome:
    if not source.url:
        return FetchOutcome(
            source.source_key,
            "failed",
            "http_file connector requires url field",
            doc_dir,
        )

    doc_dir.mkdir(parents=True, exist_ok=True)
    result = download_url(source.url)
    if result.get("error") or not result.get("body"):
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
            canonical_url=source.url,
            license_tier=source.license_tier,
            content_files=[],
            fetch_status="failed",
            fetch_error=result.get("error") or "empty response",
        )
        return FetchOutcome(
            source.source_key,
            "failed",
            result.get("error") or "empty response",
            doc_dir,
        )

    rel_name = _output_name(source, result["filename"])
    mime = mime_from_content_type(result["content_type"])
    if rel_name.endswith(".pdf"):
        mime = "application/pdf"
    elif rel_name.endswith(".html"):
        mime = "text/html"

    atomic_write_bytes(doc_dir / rel_name, result["body"])
    content_files = build_content_files(doc_dir, [(rel_name, mime)])

    if delta and existing_meta:
        old_hash = existing_meta.get("content_hash", "")
        new_hash = content_files[0]["sha256"] if content_files else ""
        if old_hash and old_hash == new_hash:
            return FetchOutcome(
                source.source_key,
                "skipped",
                "content unchanged (sha256 match)",
                doc_dir,
            )

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
        canonical_url=result.get("final_url") or source.url,
        license_tier=source.license_tier,
        content_files=content_files,
        fetch_status="complete",
        ready_for_ingest=False,
        extra={"etag": result.get("etag", "")},
    )
    return FetchOutcome(source.source_key, "complete", "", doc_dir)
