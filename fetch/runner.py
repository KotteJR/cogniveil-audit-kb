from __future__ import annotations

import logging
from pathlib import Path

from fetch.connectors.base import ConnectorNotImplementedError, FetchOutcome
from fetch.connectors.cellar import fetch_cellar
from fetch.connectors.http_file import fetch_http_file
from fetch.connectors.manual_inbox import fetch_manual_inbox
from fetch.connectors.oscal_git import fetch_oscal_git
from fetch.connectors.stub import fetch_stub
from fetch.manifest import (
    collect_manifest_documents,
    compute_stats,
    read_meta,
    write_corpus_manifest,
)
from fetch.registry import SourceSpec, filter_by_phase, find_source, load_sources
from fetch.verify import apply_verify_to_meta

logger = logging.getLogger(__name__)


def _dispatch_fetch(
    source: SourceSpec,
    doc_dir: Path,
    staging_root: Path,
    *,
    delta: bool,
    existing_meta: dict | None,
) -> FetchOutcome:
    connector = source.connector
    if connector == "cellar":
        return fetch_cellar(source, doc_dir, delta=delta, existing_meta=existing_meta)
    if connector == "http_file":
        return fetch_http_file(source, doc_dir, delta=delta, existing_meta=existing_meta)
    if connector == "oscal_git":
        return fetch_oscal_git(source, doc_dir, delta=delta, existing_meta=existing_meta)
    if connector == "manual_inbox":
        return fetch_manual_inbox(
            source,
            doc_dir,
            delta=delta,
            existing_meta=existing_meta,
            staging_root=staging_root,
        )
    if connector in {"xbrl", "dataset"}:
        return fetch_stub(
            source, doc_dir, delta=delta, existing_meta=existing_meta, kind=connector
        )
    return FetchOutcome(source.source_key, "failed", f"unknown connector {connector}")


def run_fetch(
    staging_root: Path,
    sources_path: Path,
    *,
    phase: str = "now",
    source_key: str | None = None,
    delta: bool = False,
) -> dict[str, int]:
    staging_root.mkdir(parents=True, exist_ok=True)
    all_sources = load_sources(sources_path)
    if source_key:
        found = find_source(all_sources, source_key)
        if not found:
            raise SystemExit(f"Unknown source_key: {source_key!r}")
        targets = [found]
    else:
        targets = filter_by_phase(all_sources, phase)

    stats = {"complete": 0, "failed": 0, "skipped": 0, "not_implemented": 0}

    for source in targets:
        doc_dir = source.staging_path(staging_root)
        meta_path = doc_dir / "document.meta.json"
        existing = read_meta(meta_path)
        try:
            outcome = _dispatch_fetch(
                source,
                doc_dir,
                staging_root,
                delta=delta,
                existing_meta=existing,
            )
        except ConnectorNotImplementedError as exc:
            logger.warning("%s", exc)
            stats["not_implemented"] += 1
            continue
        except Exception as exc:
            logger.exception("Fetch failed for %s", source.source_key)
            stats["failed"] += 1
            continue

        key = outcome.status
        if key in stats:
            stats[key] += 1
        else:
            stats["failed"] += 1

        if outcome.doc_dir and outcome.status == "complete":
            apply_verify_to_meta(outcome.doc_dir)

    documents = collect_manifest_documents(staging_root)
    manifest_stats = compute_stats(documents)
    manifest_stats["skipped_unchanged"] = stats["skipped"]
    write_corpus_manifest(
        staging_root,
        phase_filter=phase if not source_key else "single",
        documents=documents,
        stats=manifest_stats,
    )
    return stats


def run_verify(
    staging_root: Path,
    sources_path: Path,
    *,
    source_key: str | None = None,
) -> list[tuple[str, bool, list[str]]]:
    results: list[tuple[str, bool, list[str]]] = []
    if source_key:
        all_sources = load_sources(sources_path)
        found = find_source(all_sources, source_key)
        if not found:
            raise SystemExit(f"Unknown source_key: {source_key!r}")
        dirs = [found.staging_path(staging_root)]
    else:
        dirs = [
            p.parent
            for p in sorted(staging_root.rglob("document.meta.json"))
        ]

    for doc_dir in dirs:
        vr = apply_verify_to_meta(doc_dir)
        results.append((vr.source_key, vr.ok, vr.errors))

    documents = collect_manifest_documents(staging_root)
    write_corpus_manifest(
        staging_root,
        phase_filter="verify",
        documents=documents,
        stats=compute_stats(documents),
    )
    return results
