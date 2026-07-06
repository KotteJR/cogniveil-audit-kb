from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fetch.manifest import read_meta


MIN_PDF_BYTES = 1024
PDF_MAGIC = b"%PDF"


@dataclass
class VerifyResult:
    source_key: str
    ok: bool
    errors: list[str]
    warnings: list[str]


def _check_pdf(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing file: {path.name}"]
    size = path.stat().st_size
    if size < MIN_PDF_BYTES:
        errors.append(f"{path.name}: too small ({size} bytes)")
    with path.open("rb") as f:
        head = f.read(8)
    if not head.startswith(PDF_MAGIC):
        errors.append(f"{path.name}: not a valid PDF (missing %PDF header)")
    return errors


def _check_html(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing file: {path.name}"]
    if path.stat().st_size < 64:
        errors.append(f"{path.name}: too small")
    return errors


def verify_meta_completeness(meta: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "source_key",
        "scope",
        "connector",
        "content_files",
        "content_hash",
        "fetch_status",
    )
    for key in required:
        if key not in meta or meta[key] in (None, "", []):
            errors.append(f"missing meta field: {key}")
    files = meta.get("content_files") or []
    if meta.get("fetch_status") == "complete" and not files:
        errors.append("fetch_status complete but content_files empty")
    return errors


def verify_document_dir(doc_dir: Path) -> VerifyResult:
    meta_path = doc_dir / "document.meta.json"
    meta = read_meta(meta_path)
    if not meta:
        return VerifyResult(
            source_key=doc_dir.name,
            ok=False,
            errors=["document.meta.json missing or invalid"],
            warnings=[],
        )

    source_key = str(meta.get("source_key", doc_dir.name))
    errors = verify_meta_completeness(meta)
    warnings: list[str] = []

    if meta.get("fetch_status") == "failed":
        errors.append(f"fetch_status failed: {meta.get('fetch_error', 'unknown')}")

    connector = meta.get("connector", "")
    for entry in meta.get("content_files") or []:
        rel = entry.get("path", "")
        mime = (entry.get("mime") or "").lower()
        full = doc_dir / rel
        if "pdf" in mime or rel.endswith(".pdf"):
            errors.extend(_check_pdf(full))
        elif "html" in mime or rel.endswith(".html"):
            errors.extend(_check_html(full))
        elif not full.is_dir() and not full.is_file():
            errors.append(f"missing content file: {rel}")

    if connector == "oscal_git":
        git_dir = doc_dir / "oscal-content"
        if not git_dir.is_dir():
            errors.append("oscal-content directory missing")
        elif not (git_dir / ".git").is_dir():
            warnings.append("oscal-content exists but .git not found")

    ok = len(errors) == 0 and meta.get("fetch_status") != "failed"
    return VerifyResult(source_key=source_key, ok=ok, errors=errors, warnings=warnings)


def apply_verify_to_meta(doc_dir: Path) -> VerifyResult:
    result = verify_document_dir(doc_dir)
    meta_path = doc_dir / "document.meta.json"
    meta = read_meta(meta_path)
    if not meta:
        return result

    from fetch.manifest import atomic_write_json

    meta["ready_for_ingest"] = result.ok
    if not result.ok and result.errors:
        meta["verify_errors"] = result.errors
    else:
        meta.pop("verify_errors", None)
    atomic_write_json(meta_path, meta)
    return result
