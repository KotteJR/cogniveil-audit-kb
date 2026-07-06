"""Connectors not yet implemented (Sprint 1.5)."""

from __future__ import annotations

from pathlib import Path

from fetch.connectors.base import ConnectorNotImplementedError, FetchOutcome
from fetch.registry import SourceSpec


def fetch_stub(
    source: SourceSpec,
    doc_dir: Path,
    *,
    delta: bool,
    existing_meta: dict | None,
    kind: str,
) -> FetchOutcome:
    raise ConnectorNotImplementedError(
        f"Connector {kind!r} is not implemented yet (Sprint 1.5). "
        f"Source {source.source_key!r} skipped."
    )
