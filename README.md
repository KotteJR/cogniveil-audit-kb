# cogniveil-audit-kb

Standalone repository for the Cogniveil **Audit Cowork** knowledge base pipeline.

This repo is separate from `cogniveil-legal-backend-api`. Legal KB stays in the legal platform; audit KB is built, validated locally, and published to its own AWS infra (`cvl-dev-global-audit`).

## Sprint 1 — Fetch tool

Download authoritative audit corpus sources into local staging for parse/chunk/embed (Sprint 2) and eventual Bedrock publish (Sprint 4).

### Install

**Mac (code only):**

```bash
git clone git@github.com:cogniveil/cogniveil-audit-kb.git
cd cogniveil-audit-kb
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**ZGX HP (run fetch):**

```bash
git clone git@github.com:cogniveil/cogniveil-audit-kb.git
cd cogniveil-audit-kb
pip install -e .
export AUDIT_KB_STAGING_DIR=/data/audit-kb/staging
mkdir -p "$AUDIT_KB_STAGING_DIR/manual-inbox"
```

Drop purchased PDFs (e.g. ISO 27001/27002) into `$AUDIT_KB_STAGING_DIR/manual-inbox/` before running fetch.

### Commands

```bash
audit-kb-fetch sources --phase now
audit-kb-fetch run --phase now
audit-kb-fetch run --source iaasb-handbook-2025-vol1
audit-kb-fetch run --phase now --delta
audit-kb-fetch verify
audit-kb-fetch status
```

### Repo layout

```
cogniveil-audit-kb/
├── sources.yaml          # source registry (fetch + future ingest)
├── fetch/                # Sprint 1: audit-kb-fetch CLI
├── ingest/               # Sprint 2 (planned)
├── publish/              # Sprint 4 (planned)
├── staging/              # gitignored — downloaded corpus
└── tests/
```

### Staging layout

```
$AUDIT_KB_STAGING_DIR/
├── corpus_manifest.json
├── eu-audit/dir-2006-43/
│   ├── content.en.pdf
│   └── document.meta.json
├── iaasb/handbook-2025-vol1/
│   ├── content.pdf
│   └── document.meta.json
├── nist-oscal/nist-oscal-content/
│   ├── oscal-content/
│   └── document.meta.json
└── manual-inbox/
    └── iso-27001-2022.pdf
```

Each `document.meta.json` sidecar is the handoff contract for Sprint 2 ingest. `ready_for_ingest` is set to `true` only after `audit-kb-fetch verify` passes.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUDIT_KB_STAGING_DIR` | `./staging` | Download root |
| `AUDIT_KB_SOURCES_PATH` | `./sources.yaml` | Source registry |

### Connectors

| Connector | Use |
|-----------|-----|
| `cellar` | EUR-Lex CELEX → Publications Office Cellar API |
| `http_file` | Direct PDF/HTML download (IAASB, PCAOB, IIA, …) |
| `oscal_git` | Clone/pull NIST OSCAL content repo |
| `manual_inbox` | Promote files from `manual-inbox/` |
| `xbrl`, `dataset` | Sprint 1.5 — skipped with clear message |

### Tests

```bash
pytest
```

### Roadmap

1. **Sprint 1** — `audit-kb-fetch` (this repo)
2. **Sprint 2** — `audit-kb-ingest` → Postgres pgvector on ZGX
3. **Sprint 3** — 50-question benchmark
4. **Sprint 4** — `audit-kb-publish` → S3 + Bedrock audit KB
5. **Sprint 5** — Wire Audit Cowork in legal backend to new KB id
# cogniveil-audit-kb
