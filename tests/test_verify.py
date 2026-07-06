from pathlib import Path

from fetch.manifest import atomic_write_bytes, atomic_write_json
from fetch.verify import apply_verify_to_meta, verify_document_dir


def test_apply_verify_sets_ready_for_ingest(tmp_path: Path) -> None:
    doc_dir = tmp_path / "iaasb" / "ok"
    doc_dir.mkdir(parents=True)
    body = b"%PDF-1.4\n" + b"y" * 2000
    atomic_write_bytes(doc_dir / "content.pdf", body)
    from fetch.manifest import sha256_file

    h = sha256_file(doc_dir / "content.pdf")
    atomic_write_json(
        doc_dir / "document.meta.json",
        {
            "source_key": "ok",
            "scope": "iaasb",
            "connector": "http_file",
            "content_files": [{"path": "content.pdf", "mime": "application/pdf", "sha256": h}],
            "content_hash": h,
            "fetch_status": "complete",
            "ready_for_ingest": False,
        },
    )
    result = apply_verify_to_meta(doc_dir)
    assert result.ok
    from fetch.manifest import read_meta

    meta = read_meta(doc_dir / "document.meta.json")
    assert meta is not None
    assert meta["ready_for_ingest"] is True
