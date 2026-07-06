from __future__ import annotations

from pathlib import Path

from fetch.connectors.base import FetchOutcome
from fetch.http_utils import download_cellar_resource, mime_from_content_type
from fetch.manifest import (
    atomic_write_bytes,
    build_content_files,
    write_document_meta,
)
from fetch.registry import SourceSpec


def fetch_cellar(
    source: SourceSpec,
    doc_dir: Path,
    *,
    delta: bool,
    existing_meta: dict | None,
) -> FetchOutcome:
    if not source.celex:
        return FetchOutcome(
            source.source_key,
            "failed",
            "cellar connector requires celex field",
            doc_dir,
        )

    doc_dir.mkdir(parents=True, exist_ok=True)
    canonical = f"https://publications.europa.eu/resource/celex/{source.celex}"
    written: list[tuple[str, str]] = []

    for lang in source.languages:
        result = download_cellar_resource(source.celex, language=lang, prefer_pdf=True)
        if result.get("error") or not result.get("body"):
            continue

        fmt = result.get("format", "bin")
        if fmt == "pdf":
            rel = f"content.{lang}.pdf"
            mime = "application/pdf"
        else:
            rel = f"content.{lang}.html"
            mime = "text/html"

        atomic_write_bytes(doc_dir / rel, result["body"])
        written.append((rel, mime))

    if not written:
        write_document_meta(
            doc_dir,
            source_key=source.source_key,
            scope=source.scope,
            phase=source.phase,
            connector=source.connector,
            audit_lane=source.audit_lane,
            jurisdiction=source.jurisdiction,
            publisher=source.publisher or "EU Publications Office",
            title=source.title or source.source_key,
            framework_id=source.framework_id,
            version=source.version,
            effective_date=source.effective_date,
            language=source.languages[0] if source.languages else "en",
            canonical_url=canonical,
            license_tier=source.license_tier,
            content_files=[],
            fetch_status="failed",
            fetch_error="No content retrieved from Cellar for any language",
            extra={"celex": source.celex},
        )
        return FetchOutcome(
            source.source_key,
            "failed",
            "Cellar returned no content",
            doc_dir,
        )

    content_files = build_content_files(doc_dir, written)

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
        publisher=source.publisher or "EU Publications Office",
        title=source.title or source.source_key,
        framework_id=source.framework_id,
        version=source.version,
        effective_date=source.effective_date,
        language=source.languages[0] if source.languages else "en",
        canonical_url=canonical,
        license_tier=source.license_tier,
        content_files=content_files,
        fetch_status="complete",
        ready_for_ingest=False,
        extra={"celex": source.celex, "languages_fetched": source.languages},
    )
    return FetchOutcome(source.source_key, "complete", "", doc_dir)
