#!/usr/bin/env python3
"""Rebuild deterministic V7 reference mirrors while JSON stays authoritative.

This tool is intentionally separate from production mirror writes.  It is for
operator-triggered recovery of imported reference domains only: species, base
and manual water catalogs, and legacy saved locations.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.importers import import_domain
from persistence.migrations import migrate
from persistence.validation import validate_database

DEFAULT_DB = ROOT / "data" / "angler_intel.sqlite3"
DOMAINS = ("species", "waters", "favorites")


def _verify_manifest(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Backup manifest is unreadable: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("json_source_of_truth"):
        raise ValueError("Backup manifest does not confirm JSON source-of-truth coverage.")


def _sqlite_copy(source: Path, destination: Path) -> None:
    """Copy a live database through SQLite rather than copying WAL files."""
    with connect(source, read_only=True) as source_conn:
        import sqlite3

        target = sqlite3.connect(destination)
        try:
            source_conn.backup(target)
        finally:
            target.close()


def reconcile(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database is unavailable: {db_path}")
    imported: dict[str, int] = {}
    with connect(db_path) as conn:
        migrations = migrate(conn, db_path=str(db_path))
        for domain in DOMAINS:
            imported[domain] = len(import_domain(conn, domain))
    validation = validate_database(db_path)
    return {
        "db_path": str(db_path),
        "imported": imported,
        "applied_migrations": migrations,
        "validation": validation,
        "json_authoritative": True,
        "note": "Reference data was rebuilt from JSON. SQLite authority remains json.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile V7 reference data from authoritative JSON")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Reconcile an SQLite-safe temporary copy")
    mode.add_argument("--apply", action="store_true", help="Reconcile the supplied runtime database")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--backup-manifest", help="Required verified V7 backup manifest for --apply")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()
    database = Path(args.db)

    if args.apply:
        if not args.backup_manifest:
            raise SystemExit("--apply requires --backup-manifest")
        _verify_manifest(Path(args.backup_manifest))
        result = reconcile(database)
    else:
        with tempfile.TemporaryDirectory(prefix="angler-v7-reference-") as tmpdir:
            temporary_db = Path(tmpdir) / "reference-reconcile.sqlite3"
            _sqlite_copy(database, temporary_db)
            result = reconcile(temporary_db)
            result["db_path"] = str(temporary_db)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["validation"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
