from __future__ import annotations

import os
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent


def default_staging_dir() -> Path:
    env = os.environ.get("AUDIT_KB_STAGING_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (_PKG_ROOT / "staging").resolve()


def default_sources_path() -> Path:
    env = os.environ.get("AUDIT_KB_SOURCES_PATH", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (_PKG_ROOT / "sources.yaml").resolve()
