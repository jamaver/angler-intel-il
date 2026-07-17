#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.importers import import_all, import_domain
from persistence.migrations import migrate
from persistence.validation import record_validation_results, validate_database

DEFAULT_DB = ROOT / "data" / "v7_migration_preview.sqlite3"


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Backup manifest must be a JSON object")
    return payload


def _run_pipeline(db_path: Path, *, domain: str | None, all_domains: bool, source_root: Path, reports_root: Path) -> dict[str, Any]:
    with connect(db_path) as conn:
        applied = migrate(conn, db_path=str(db_path))
        imported = import_all(conn) if all_domains else {domain: len(import_domain(conn, domain or "species"))}
        summary = validate_database(db_path, source_root=source_root, reports_root=reports_root)
        try:
            record_validation_results(db_path, summary)
            summary["recorded"] = True
        except Exception as exc:
            summary["recorded"] = False
            summary.setdefault("warnings", []).append(f"Could not record validation summary: {exc}")
    return {
        "db_path": str(db_path),
        "applied_migrations": applied,
        "imported": imported,
        "validation": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Angler Intel V7 migration foundation")
    parser.add_argument("--dry-run", action="store_true", help="Run against a temporary database")
    parser.add_argument("--apply", action="store_true", help="Apply to the supplied database path")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Database path")
    parser.add_argument("--domain", help="Import a single domain")
    parser.add_argument("--all", action="store_true", help="Import all supported domains")
    parser.add_argument("--backup-manifest", help="Verified backup manifest path required for apply")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--output", help="Write JSON to PATH")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        args.dry_run = True

    if args.apply:
        if not args.backup_manifest:
            raise SystemExit("--apply requires --backup-manifest")
        manifest_path = Path(args.backup_manifest)
        if not manifest_path.exists():
            raise SystemExit(f"Backup manifest not found: {manifest_path}")
        _load_manifest(manifest_path)

    source_root = ROOT / "data"
    reports_root = ROOT / "reports"

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="angler-v7-migrate-") as tmpdir:
            temp_db = Path(tmpdir) / "v7-migration.sqlite3"
            result = _run_pipeline(temp_db, domain=args.domain, all_domains=args.all, source_root=source_root, reports_root=reports_root)
    else:
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        result = _run_pipeline(db_path, domain=args.domain, all_domains=args.all, source_root=source_root, reports_root=reports_root)

    result["json_remains_authoritative"] = True
    result["authority"] = "json"
    result["note"] = "V7.0 does not change production reads or writes."

    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    if args.json or not args.output:
        print(rendered)

    validation = result.get("validation", {})
    if validation and not validation.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
