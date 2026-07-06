from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = (
    "source_key",
    "phase",
    "scope",
    "connector",
    "audit_lane",
    "jurisdiction",
)

KNOWN_CONNECTORS = frozenset(
    {
        "cellar",
        "http_file",
        "oscal_git",
        "manual_inbox",
        "xbrl",
        "dataset",
    }
)


@dataclass(frozen=True)
class SourceSpec:
    source_key: str
    phase: str
    scope: str
    connector: str
    audit_lane: list[str]
    jurisdiction: str
    publisher: str = ""
    title: str = ""
    framework_id: str = ""
    version: str = ""
    effective_date: str = ""
    license_tier: str = "free_download"
    refresh_cron: str = ""
    celex: str = ""
    languages: list[str] = field(default_factory=lambda: ["en"])
    url: str = ""
    repo: str = ""
    ref: str = "main"
    expected_filename: str = ""
    inbox_filename: str = ""
    slug: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def dir_name(self) -> str:
        if self.slug:
            return self.slug
        prefix = f"{self.scope}-"
        if self.source_key.startswith(prefix):
            return self.source_key[len(prefix) :]
        return self.source_key

    def staging_path(self, staging_root: Path) -> Path:
        return staging_root / self.scope / self.dir_name


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _parse_source(entry: dict[str, Any]) -> SourceSpec:
    missing = [f for f in REQUIRED_FIELDS if f not in entry or entry[f] in (None, "")]
    if missing:
        raise ValueError(
            f"Source {entry.get('source_key', '?')!r} missing required fields: {missing}"
        )
    connector = str(entry["connector"])
    if connector not in KNOWN_CONNECTORS:
        raise ValueError(
            f"Source {entry['source_key']!r} has unknown connector {connector!r}"
        )
    return SourceSpec(
        source_key=str(entry["source_key"]),
        phase=str(entry["phase"]),
        scope=str(entry["scope"]),
        connector=connector,
        audit_lane=_coerce_list(entry["audit_lane"]),
        jurisdiction=str(entry["jurisdiction"]),
        publisher=str(entry.get("publisher", "")),
        title=str(entry.get("title", "")),
        framework_id=str(entry.get("framework_id", "")),
        version=str(entry.get("version", "")),
        effective_date=str(entry.get("effective_date", "")),
        license_tier=str(entry.get("license_tier", "free_download")),
        refresh_cron=str(entry.get("refresh_cron", "")),
        celex=str(entry.get("celex", "")),
        languages=_coerce_list(entry.get("languages") or ["en"]),
        url=str(entry.get("url", "")),
        repo=str(entry.get("repo", "")),
        ref=str(entry.get("ref", "main")),
        expected_filename=str(entry.get("expected_filename", "")),
        inbox_filename=str(entry.get("inbox_filename", "")),
        slug=str(entry.get("slug", "")),
        raw=dict(entry),
    )


def load_sources(path: Path) -> list[SourceSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "sources" not in data:
        raise ValueError(f"{path}: expected top-level 'sources' list")
    entries = data["sources"]
    if not isinstance(entries, list):
        raise ValueError(f"{path}: 'sources' must be a list")
    return [_parse_source(e) for e in entries]


def filter_by_phase(sources: list[SourceSpec], phase: str) -> list[SourceSpec]:
    if phase == "all":
        return list(sources)
    return [s for s in sources if s.phase == phase]


def find_source(sources: list[SourceSpec], source_key: str) -> SourceSpec | None:
    for s in sources:
        if s.source_key == source_key:
            return s
    return None
