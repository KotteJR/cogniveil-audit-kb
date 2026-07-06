from __future__ import annotations

from pathlib import Path

import pytest

from fetch.config import default_staging_dir
from fetch.manifest import (
    atomic_write_bytes,
    atomic_write_json,
    build_content_files,
    read_meta,
    sha256_bytes,
    write_corpus_manifest,
)
from fetch.registry import filter_by_phase, find_source, load_sources
from fetch.verify import verify_document_dir, verify_meta_completeness


FIXTURES = Path(__file__).parent / "fixtures"
SOURCES = Path(__file__).parent.parent / "sources.yaml"


def test_load_sources_yaml() -> None:
    sources = load_sources(SOURCES)
    assert len(sources) >= 25
    keys = {s.source_key for s in sources}
    assert "eu-dir-2006-43" in keys
    assert "nist-oscal-content" in keys


def test_filter_by_phase_now_excludes_later() -> None:
    sources = load_sources(SOURCES)
    now = filter_by_phase(sources, "now")
    assert all(s.phase == "now" for s in now)
    assert find_source(now, "coso-icif-2013") is None


def test_filter_by_phase_all_includes_later() -> None:
    sources = load_sources(SOURCES)
    all_sources = filter_by_phase(sources, "all")
    assert find_source(all_sources, "coso-icif-2013") is not None


def test_source_dir_name_strips_scope_prefix() -> None:
    sources = load_sources(SOURCES)
    src = find_source(sources, "iaasb-handbook-2025-vol1")
    assert src is not None
    assert src.dir_name == "handbook-2025-vol1"


def test_atomic_write_json_and_read(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "document.meta.json"
    atomic_write_json(target, {"source_key": "test", "value": 1})
    assert target.is_file()
    assert read_meta(target) == {"source_key": "test", "value": 1}


def test_sha256_bytes() -> None:
    assert sha256_bytes(b"hello") == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_build_content_files(tmp_path: Path) -> None:
    pdf = tmp_path / "content.pdf"
    atomic_write_bytes(pdf, b"%PDF-1.4 test content")
    files = build_content_files(tmp_path, [("content.pdf", "application/pdf")])
    assert len(files) == 1
    assert files[0]["mime"] == "application/pdf"
    assert len(files[0]["sha256"]) == 64


def test_write_corpus_manifest(tmp_path: Path) -> None:
    path = write_corpus_manifest(
        tmp_path,
        phase_filter="now",
        documents=[{"source_key": "x", "ready_for_ingest": True}],
        stats={"total": 1, "ready": 1, "failed": 0, "skipped_unchanged": 0},
    )
    assert path.is_file()
    meta = read_meta(path)
    assert meta["phase_filter"] == "now"


def test_verify_rejects_invalid_pdf(tmp_path: Path) -> None:
    doc_dir = tmp_path / "iaasb" / "test"
    doc_dir.mkdir(parents=True)
    atomic_write_bytes(doc_dir / "content.pdf", b"not a pdf")
    atomic_write_json(
        doc_dir / "document.meta.json",
        {
            "source_key": "test",
            "scope": "iaasb",
            "connector": "http_file",
            "content_files": [{"path": "content.pdf", "mime": "application/pdf", "sha256": "x"}],
            "content_hash": "x",
            "fetch_status": "complete",
        },
    )
    result = verify_document_dir(doc_dir)
    assert not result.ok
    assert any("not a valid PDF" in e for e in result.errors)


def test_verify_accepts_valid_pdf(tmp_path: Path) -> None:
    doc_dir = tmp_path / "iaasb" / "test"
    doc_dir.mkdir(parents=True)
    body = b"%PDF-1.4\n" + b"x" * 2000
    atomic_write_bytes(doc_dir / "content.pdf", body)
    from fetch.manifest import sha256_file

    h = sha256_file(doc_dir / "content.pdf")
    atomic_write_json(
        doc_dir / "document.meta.json",
        {
            "source_key": "test",
            "scope": "iaasb",
            "connector": "http_file",
            "content_files": [{"path": "content.pdf", "mime": "application/pdf", "sha256": h}],
            "content_hash": h,
            "fetch_status": "complete",
        },
    )
    result = verify_document_dir(doc_dir)
    assert result.ok


def test_verify_meta_completeness_missing_fields() -> None:
    errors = verify_meta_completeness({"source_key": "x"})
    assert any("content_files" in e for e in errors)


def test_default_staging_dir_ends_with_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_KB_STAGING_DIR", raising=False)
    assert default_staging_dir().name == "staging"
