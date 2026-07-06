from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    atomic_write_bytes(path, data.encode("utf-8"))


def read_meta(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def build_content_files(
    doc_dir: Path, files: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Build content_files entries from (relative_path, mime) pairs."""
    out: list[dict[str, Any]] = []
    for rel_path, mime in files:
        full = doc_dir / rel_path
        if not full.is_file():
            continue
        out.append(
            {
                "path": rel_path,
                "mime": mime,
                "sha256": sha256_file(full),
            }
        )
    return out


def write_document_meta(
    doc_dir: Path,
    *,
    source_key: str,
    scope: str,
    phase: str,
    connector: str,
    audit_lane: list[str],
    jurisdiction: str,
    publisher: str,
    title: str,
    framework_id: str,
    version: str,
    effective_date: str,
    language: str,
    canonical_url: str,
    license_tier: str,
    content_files: list[dict[str, Any]],
    fetch_status: str,
    ready_for_ingest: bool = False,
    fetch_error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary_hash = content_files[0]["sha256"] if content_files else ""
    meta: dict[str, Any] = {
        "source_key": source_key,
        "scope": scope,
        "dataset_source": scope,
        "phase": phase,
        "connector": connector,
        "audit_lane": audit_lane,
        "jurisdiction": jurisdiction,
        "framework_id": framework_id,
        "publisher": publisher,
        "title": title,
        "version": version,
        "effective_date": effective_date,
        "language": language,
        "canonical_url": canonical_url,
        "license_tier": license_tier,
        "content_files": content_files,
        "content_hash": primary_hash,
        "fetched_at": utc_now_iso(),
        "fetch_status": fetch_status,
        "ready_for_ingest": ready_for_ingest,
    }
    if fetch_error:
        meta["fetch_error"] = fetch_error
    if extra:
        meta.update(extra)
    atomic_write_json(doc_dir / "document.meta.json", meta)
    return meta


def write_corpus_manifest(
    staging_root: Path,
    *,
    phase_filter: str,
    documents: list[dict[str, Any]],
    stats: dict[str, int],
) -> Path:
    manifest_path = staging_root / "corpus_manifest.json"
    payload = {
        "corpus_version": utc_now_iso(),
        "phase_filter": phase_filter,
        "documents": documents,
        "stats": stats,
    }
    atomic_write_json(manifest_path, payload)
    return manifest_path


def collect_manifest_documents(staging_root: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if not staging_root.is_dir():
        return docs
    for meta_path in sorted(staging_root.rglob("document.meta.json")):
        meta = read_meta(meta_path)
        if not meta:
            continue
        rel = meta_path.parent.relative_to(staging_root).as_posix()
        docs.append(
            {
                "source_key": meta.get("source_key", ""),
                "meta_path": f"{rel}/document.meta.json",
                "ready_for_ingest": bool(meta.get("ready_for_ingest")),
                "fetch_status": meta.get("fetch_status", "unknown"),
            }
        )
    return docs


def compute_stats(documents: list[dict[str, Any]]) -> dict[str, int]:
    ready = sum(1 for d in documents if d.get("ready_for_ingest"))
    failed = sum(1 for d in documents if d.get("fetch_status") == "failed")
    total = len(documents)
    return {
        "total": total,
        "ready": ready,
        "failed": failed,
        "skipped_unchanged": 0,
    }
