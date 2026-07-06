from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from fetch.config import default_sources_path, default_staging_dir
from fetch.manifest import collect_manifest_documents, read_meta
from fetch.registry import filter_by_phase, load_sources
from fetch.runner import run_fetch, run_verify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


@click.group()
@click.option(
    "--staging-dir",
    type=click.Path(path_type=str),
    default=None,
    envvar="AUDIT_KB_STAGING_DIR",
    help="Staging root (default: tools/audit-kb/staging or AUDIT_KB_STAGING_DIR)",
)
@click.option(
    "--sources",
    type=click.Path(exists=True, path_type=str),
    default=None,
    envvar="AUDIT_KB_SOURCES_PATH",
    help="Path to sources.yaml",
)
@click.pass_context
def main(ctx: click.Context, staging_dir: str | None, sources: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["staging_dir"] = (
        default_staging_dir() if staging_dir is None else Path(staging_dir)
    )
    ctx.obj["sources"] = (
        default_sources_path() if sources is None else Path(sources)
    )


@main.command("run")
@click.option("--phase", default="now", type=click.Choice(["now", "all", "later"]))
@click.option("--source", "source_key", default=None, help="Fetch single source_key")
@click.option("--delta", is_flag=True, help="Skip unchanged content (sha256 / git SHA)")
@click.pass_context
def cmd_run(ctx: click.Context, phase: str, source_key: str | None, delta: bool) -> None:
    stats = run_fetch(
        ctx.obj["staging_dir"],
        ctx.obj["sources"],
        phase=phase,
        source_key=source_key,
        delta=delta,
    )
    click.echo(
        f"Fetch complete: complete={stats['complete']} failed={stats['failed']} "
        f"skipped={stats['skipped']} not_implemented={stats['not_implemented']}"
    )
    if stats["failed"] > 0:
        sys.exit(1)


@main.command("verify")
@click.option("--source", "source_key", default=None)
@click.pass_context
def cmd_verify(ctx: click.Context, source_key: str | None) -> None:
    results = run_verify(
        ctx.obj["staging_dir"],
        ctx.obj["sources"],
        source_key=source_key,
    )
    failed = [r for r in results if not r[1]]
    for key, ok, errors in results:
        status = "OK" if ok else "FAIL"
        click.echo(f"  [{status}] {key}")
        for err in errors:
            click.echo(f"         - {err}")
    click.echo(f"Verified {len(results)} document(s); {len(failed)} failed")
    if failed:
        sys.exit(1)


@main.command("status")
@click.pass_context
def cmd_status(ctx: click.Context) -> None:
    staging = ctx.obj["staging_dir"]
    documents = collect_manifest_documents(staging)
    if not documents:
        click.echo(f"No documents in staging: {staging}")
        return
    click.echo(f"Staging: {staging}")
    click.echo(f"{'SOURCE_KEY':<40} {'STATUS':<12} {'READY':<6}")
    click.echo("-" * 62)
    for doc in documents:
        meta = read_meta(staging / doc["meta_path"])
        status = (meta or {}).get("fetch_status", "?")
        ready = "yes" if doc.get("ready_for_ingest") else "no"
        click.echo(f"{doc['source_key']:<40} {status:<12} {ready:<6}")


@main.command("sources")
@click.option("--phase", default="now", type=click.Choice(["now", "all", "later"]))
@click.pass_context
def cmd_sources(ctx: click.Context, phase: str) -> None:
    specs = filter_by_phase(load_sources(ctx.obj["sources"]), phase)
    click.echo(f"{'SOURCE_KEY':<36} {'SCOPE':<14} {'CONNECTOR':<14} {'PHASE':<6}")
    click.echo("-" * 74)
    for s in specs:
        click.echo(
            f"{s.source_key:<36} {s.scope:<14} {s.connector:<14} {s.phase:<6}"
        )
    click.echo(f"\nTotal: {len(specs)}")
