from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from fetch.connectors.http_file import fetch_http_file
from fetch.manifest import read_meta
from fetch.registry import load_sources


SOURCES = Path(__file__).parent.parent / "sources.yaml"


@pytest.fixture
def iaasb_source():
    sources = load_sources(SOURCES)
    for s in sources:
        if s.source_key == "iaasb-handbook-2025-vol1":
            return s
    raise AssertionError("source not found")


def test_http_file_delta_skips_unchanged(tmp_path: Path, iaasb_source) -> None:
    doc_dir = iaasb_source.staging_path(tmp_path)
    doc_dir.mkdir(parents=True)
    body = b"%PDF-1.4 unchanged"
    from fetch.manifest import sha256_bytes, write_document_meta

    h = sha256_bytes(body)
    write_document_meta(
        doc_dir,
        source_key=iaasb_source.source_key,
        scope=iaasb_source.scope,
        phase=iaasb_source.phase,
        connector=iaasb_source.connector,
        audit_lane=iaasb_source.audit_lane,
        jurisdiction=iaasb_source.jurisdiction,
        publisher=iaasb_source.publisher,
        title=iaasb_source.title,
        framework_id=iaasb_source.framework_id,
        version=iaasb_source.version,
        effective_date=iaasb_source.effective_date,
        language="en",
        canonical_url=iaasb_source.url,
        license_tier=iaasb_source.license_tier,
        content_files=[{"path": "content.pdf", "mime": "application/pdf", "sha256": h}],
        fetch_status="complete",
    )
    existing = read_meta(doc_dir / "document.meta.json")

    def fake_download(url: str, **kwargs):
        return {
            "body": body,
            "content_type": "application/pdf",
            "filename": "handbook.pdf",
            "final_url": url,
            "etag": "",
            "error": None,
        }

    with patch("fetch.connectors.http_file.download_url", side_effect=fake_download):
        outcome = fetch_http_file(
            iaasb_source, doc_dir, delta=True, existing_meta=existing
        )
    assert outcome.status == "skipped"


def test_http_file_downloads_and_writes_meta(tmp_path: Path, iaasb_source) -> None:
    doc_dir = iaasb_source.staging_path(tmp_path)
    body = b"%PDF-1.4 new content here" + b" " * 2000

    def fake_download(url: str, **kwargs):
        return {
            "body": body,
            "content_type": "application/pdf",
            "filename": "IAASB-2025-Handbook-Volume-1.pdf",
            "final_url": url,
            "etag": "abc",
            "error": None,
        }

    with patch("fetch.connectors.http_file.download_url", side_effect=fake_download):
        outcome = fetch_http_file(
            iaasb_source, doc_dir, delta=False, existing_meta=None
        )
    assert outcome.status == "complete"
    assert (doc_dir / "content.pdf").is_file()
    meta = read_meta(doc_dir / "document.meta.json")
    assert meta is not None
    assert meta["fetch_status"] == "complete"
    assert meta["content_files"][0]["sha256"]
