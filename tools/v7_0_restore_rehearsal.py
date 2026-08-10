#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.importers import export_domain_rows
from persistence import importers as importer_mod
from persistence.migrations import migrate
from persistence.validation import validate_database
from persistence.connection import connect
from persistence.safe_zip import safe_extract


REFERENCE_DEFAULTS = (
    "species_profiles_v43.json",
    "species_settings_v431.json",
    "illinois_waters.json",
)


def _sqlite_authoritative_domains(db_path: Path) -> list[str]:
    """Return transitioned domains without trusting legacy JSON artifacts.

    A restore rehearsal must never re-import JSON over a database that already
    owns a domain.  The extracted DB is the object being rehearsed in that
    case; JSON files are compatibility exports and validation inputs only.
    """
    with connect(db_path, read_only=True) as conn:
        rows = conn.execute("SELECT domain FROM data_authority WHERE authority='sqlite' ORDER BY domain").fetchall()
    return [str(row["domain"]) for row in rows]


def _seed_reference_defaults(data_dir: Path) -> list[str]:
    """Supply tracked reference data that a runtime-only backup excludes.

    Runtime backups intentionally omit repository seed data. A real restore is
    performed into an installed application tree, so rehearsal supplies only
    the immutable defaults from that tree when the archive does not contain
    them. Personal/runtime files are never copied from the live deployment.
    """
    seeded: list[str] = []
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in REFERENCE_DEFAULTS:
        source = ROOT / "data" / filename
        target = data_dir / filename
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
            seeded.append(filename)
    return seeded


def _safe_extract(archive: Path, target_dir: Path) -> None:
    safe_extract(archive, target_dir)


def _export_legacy_json(db_path: Path, export_dir: Path) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    exports: dict[str, str] = {}
    with connect(db_path) as conn:
        for domain in ("species", "waters", "target_profile", "favorites", "gear_inventory", "catches", "reports"):
            rows = export_domain_rows(conn, domain)
            export_path = export_dir / f"{domain}.json"
            export_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            exports[domain] = str(export_path)
    return exports


def rehearse_restore(archive: str | Path) -> dict:
    """Validate a verified V7 backup without touching live runtime paths."""
    archive = Path(archive)
    manifest_path = archive.with_suffix(".manifest.json")
    if not archive.exists():
        raise ValueError(f"Archive not found: {archive}")
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not manifest.get("verified"):
        raise ValueError("Backup manifest is not verified")

    with tempfile.TemporaryDirectory(prefix="angler-v7-restore-") as tmpdir:
        root = Path(tmpdir)
        _safe_extract(archive, root)
        db_path = root / "data" / "angler_intel.sqlite3"
        export_dir = root / "legacy_exports"
        seeded_reference_defaults = _seed_reference_defaults(root / "data")
        old_data_dir = importer_mod.DATA_DIR
        old_reports_dir = importer_mod.REPORTS_DIR
        importer_mod.DATA_DIR = root / "data"
        importer_mod.REPORTS_DIR = root / "reports"
        try:
            sqlite_authoritative = _sqlite_authoritative_domains(db_path)
            with connect(db_path) as conn:
                migrate(conn, db_path=str(db_path))
                # JSON import is only safe for an all-JSON backup. Once a
                # domain has transitioned, use the restored SQLite database
                # as-is and validate its compatibility exports separately.
                if not sqlite_authoritative:
                    importer_mod.import_all(conn)
            exports = _export_legacy_json(db_path, export_dir)
            validation = validate_database(
                db_path,
                source_manifest_hash=manifest.get("source_manifest_hash"),
                source_root=root / "data",
                reports_root=root / "reports",
            )
        finally:
            importer_mod.DATA_DIR = old_data_dir
            importer_mod.REPORTS_DIR = old_reports_dir
        return {
            "archive": str(archive),
            "manifest": str(manifest_path),
            "verified": True,
            "exports": exports,
            "sqlite_authoritative_domains": sqlite_authoritative,
            "json_reimport": "skipped" if sqlite_authoritative else "completed",
            "seeded_reference_defaults": seeded_reference_defaults,
            "validation": validation,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rehearse restore for a V7 backup archive")
    parser.add_argument("archive", help="Path to a V7 runtime backup zip")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--output", help="Write JSON to PATH")
    args = parser.parse_args()

    try:
        result = rehearse_restore(args.archive)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    if args.json or not args.output:
        print(rendered)

    if not result["validation"].get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
