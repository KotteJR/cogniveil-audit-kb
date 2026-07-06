from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fetch.registry import SourceSpec


@dataclass
class FetchOutcome:
    source_key: str
    status: str  # complete | failed | skipped
    message: str = ""
    doc_dir: Path | None = None


class Connector(Protocol):
    def fetch(
        self,
        source: SourceSpec,
        doc_dir: Path,
        *,
        delta: bool,
        existing_meta: dict | None,
    ) -> FetchOutcome: ...


class ConnectorNotImplementedError(Exception):
    pass
