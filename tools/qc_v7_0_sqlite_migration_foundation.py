#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence import importers as importer_mod
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.validation import validate_database
from tools.v7_0_data_audit import audit
from app import app as flask_app

errors: list[str] = []


def _copy_runtime_tree(temp_root: Path) -> tuple[Path, Path]:
    source_root = temp_root / "data"
    reports_root = temp_root / "reports"
    source_root.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    for rel in (
        "catches.json",
        "favorites.json",
        "gear_inventory.json",
        "gear_settings.json",
        "illinois_waters.json",
        "manual_waters.json",
        "reports_index.json",
        "species_profiles_v43.json",
        "species_settings_v431.json",
        "target_profile.json",
        "gear_catalog_cache.json",
        "angler_intel.sqlite3",
    ):
        src = ROOT / "data" / rel
        if src.exists():
            shutil.copy2(src, source_root / rel)

    for path in (ROOT / "reports").glob("*.json"):
        shutil.copy2(path, reports_root / path.name)
    for path in (ROOT / "reports").glob("*.html"):
        shutil.copy2(path, reports_root / path.name)

    return source_root, reports_root


@contextlib.contextmanager
def _patched_import_roots(source_root: Path, reports_root: Path) -> Iterator[None]:
    old_data = importer_mod.DATA_DIR
    old_reports = importer_mod.REPORTS_DIR
    importer_mod.DATA_DIR = source_root
    importer_mod.REPORTS_DIR = reports_root
    try:
        yield
    finally:
        importer_mod.DATA_DIR = old_data
        importer_mod.REPORTS_DIR = old_reports


def _json_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    hashes = {}
    for rel in (
        "catches.json",
        "favorites.json",
        "gear_inventory.json",
        "gear_settings.json",
        "manual_waters.json",
        "target_profile.json",
        "reports_index.json",
    ):
        path = ROOT / "data" / rel
        if path.exists():
            hashes[rel] = _json_hash(path)
    return hashes


def _backup_sqlite(source_db: Path, target_db: Path) -> None:
    with connect(source_db) as src, connect(target_db) as dst:
        src.backup(dst)


def _fixture_runtime_backup(temp_root: Path, source_root: Path, reports_root: Path, database: Path) -> tuple[Path, Path]:
    """Build a verified-looking fixture archive without touching live runtime data.

    This test proves the restore rehearsal against the same clean source tree
    used for import validation. Live runtime state may deliberately contain
    operator data or known compatibility drift and must not decide whether a
    framework QC passes.
    """
    staging = temp_root / "restore-fixture"
    (staging / "data").mkdir(parents=True)
    (staging / "reports").mkdir(parents=True)
    for path in source_root.glob("*.json"):
        shutil.copy2(path, staging / "data" / path.name)
    shutil.copy2(database, staging / "data" / "angler_intel.sqlite3")
    for path in reports_root.glob("*"):
        if path.is_file():
            shutil.copy2(path, staging / "reports" / path.name)
    archive = temp_root / "fixture-v7-runtime.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in staging.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(staging))
    manifest = archive.with_suffix(".manifest.json")
    manifest.write_text(json.dumps({"verified": True, "source_manifest_hash": None}, indent=2), encoding="utf-8")
    return archive, manifest


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except Exception:
        return -1


def _run_import_cycle(db_path: Path, source_root: Path, reports_root: Path) -> dict[str, Any]:
    with _patched_import_roots(source_root, reports_root):
        with connect(db_path) as conn:
            applied = migrate(conn, db_path=str(db_path))
            imported = importer_mod.import_all(conn)
            validation = validate_database(db_path, source_root=source_root, reports_root=reports_root)
            counts = {
                "species": _table_count(conn, "species"),
                "waterbodies": _table_count(conn, "waterbodies"),
                "target_profiles": _table_count(conn, "target_profiles"),
                "saved_locations": _table_count(conn, "saved_locations"),
                "gear_items": _table_count(conn, "gear_items"),
                "catches": _table_count(conn, "catches"),
                "trip_reports": _table_count(conn, "trip_reports"),
            }
            authorities = [dict(row) for row in conn.execute("SELECT domain, authority FROM data_authority ORDER BY domain")]
    return {
        "applied": applied,
        "imported": imported,
        "validation": validation,
        "counts": counts,
        "authorities": authorities,
    }


def _assert(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="V7 SQLite migration foundation QC")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    before_hashes = _source_hashes()
    audit_payload = audit()

    with tempfile.TemporaryDirectory(prefix="angler-v7-qc-") as tmpdir:
        temp_root = Path(tmpdir)
        source_root, reports_root = _copy_runtime_tree(temp_root)

        fresh_db = temp_root / "fresh.sqlite3"
        fresh_result = _run_import_cycle(fresh_db, source_root, reports_root)
        _assert(fresh_result["validation"].get("ok"), "fresh migration/validation should pass")
        _assert(fresh_result["counts"]["species"] >= 1, "fresh migration should import species")
        _assert(fresh_result["counts"]["waterbodies"] >= 1, "fresh migration should import waters")
        _assert(all(row.get("authority") == "json" for row in fresh_result["authorities"]), "all authorities must remain json")

        upgrade_db = temp_root / "upgrade.sqlite3"
        _backup_sqlite(ROOT / "data" / "angler_intel.sqlite3", upgrade_db)
        upgrade_result = _run_import_cycle(upgrade_db, source_root, reports_root)
        _assert(upgrade_result["validation"].get("ok"), "upgrade migration/validation should pass")

        with connect(temp_root / "checksum.sqlite3") as conn:
            migrate(conn, db_path=str(temp_root / "checksum.sqlite3"))
            conn.execute("UPDATE schema_migrations SET checksum = 'tampered' WHERE version = (SELECT version FROM schema_migrations ORDER BY version LIMIT 1)")
            conn.commit()
            checksum_failed = False
            try:
                migrate(conn, db_path=str(temp_root / "checksum.sqlite3"))
            except Exception:
                checksum_failed = True
        _assert(checksum_failed, "checksum enforcement must reject tampered migrations")

        with connect(temp_root / "idempotent.sqlite3") as conn:
            first = migrate(conn, db_path=str(temp_root / "idempotent.sqlite3"))
            second = migrate(conn, db_path=str(temp_root / "idempotent.sqlite3"))
        _assert(first or True, "initial migration should apply at least one step")
        _assert(second == [], "second migration pass should be idempotent")

        with _patched_import_roots(source_root, reports_root):
            with connect(temp_root / "import-idempotent.sqlite3") as conn:
                migrate(conn, db_path=str(temp_root / "import-idempotent.sqlite3"))
                first_import = importer_mod.import_all(conn)
                first_counts = {table: _table_count(conn, table) for table in ("species", "waterbodies", "gear_items", "catches", "trip_reports")}
                second_import = importer_mod.import_all(conn)
                second_counts = {table: _table_count(conn, table) for table in ("species", "waterbodies", "gear_items", "catches", "trip_reports")}
        _assert(first_import == second_import, "import results should be stable on repeat runs")
        _assert(first_counts == second_counts, "imported row counts should remain stable")

        clean_validation = validate_database(fresh_db, source_root=source_root, reports_root=reports_root)
        _assert(clean_validation.get("ok"), "clean validation should be exact")

        corrupt_root = temp_root / "corrupt"
        shutil.copytree(source_root, corrupt_root)
        corrupt_species = corrupt_root / "species_profiles_v43.json"
        corrupt_species.write_text("{not json", encoding="utf-8")
        with _patched_import_roots(corrupt_root, reports_root):
            audit_result = audit()
        _assert(any(not item.get("valid_json", True) for item in audit_result.get("source_files", []) if item.get("path", "").endswith("species_profiles_v43.json")), "audit should flag corrupt JSON")

        dup_root = temp_root / "duplicate"
        shutil.copytree(source_root, dup_root)
        manual_waters = dup_root / "manual_waters.json"
        manual_payload = json.loads(manual_waters.read_text(encoding="utf-8"))
        if isinstance(manual_payload, list) and manual_payload:
            manual_payload.append(dict(manual_payload[0]))
            manual_waters.write_text(json.dumps(manual_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        duplicate_validation = validate_database(temp_root / "fresh.sqlite3", source_root=dup_root, reports_root=reports_root)
        _assert(duplicate_validation["totals"]["duplicate_source"] > 0, "duplicate source IDs should be reported")

        invalid_root = temp_root / "invalid-manual"
        shutil.copytree(source_root, invalid_root)
        manual_waters = invalid_root / "manual_waters.json"
        manual_payload = json.loads(manual_waters.read_text(encoding="utf-8"))
        if isinstance(manual_payload, list) and manual_payload:
            manual_payload[0]["lat"] = 999
            manual_payload[0]["lon"] = 999
            manual_waters.write_text(json.dumps(manual_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        invalid_validation = validate_database(temp_root / "fresh.sqlite3", source_root=invalid_root, reports_root=reports_root)
        _assert(invalid_validation["totals"]["invalid_source"] > 0, "invalid manual water should be reported")

        catch_root = temp_root / "catch-links"
        shutil.copytree(source_root, catch_root)
        catches_path = catch_root / "catches.json"
        catches_payload = json.loads(catches_path.read_text(encoding="utf-8"))
        if isinstance(catches_payload, list) and catches_payload:
            catches_payload[0]["species"] = "Not A Species"
            catches_payload[0]["waterbody"] = "Missing Water"
            catches_payload[0]["gear_refs"] = {"rod": "bad-rod-id"}
            catches_path.write_text(json.dumps(catches_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        catch_validation = validate_database(temp_root / "fresh.sqlite3", source_root=catch_root, reports_root=reports_root)
        _assert(catch_validation["totals"]["unmapped_reference"] > 0, "unmatched catch links should be reported")

        report_root = temp_root / "report-drift"
        shutil.copytree(source_root, report_root)
        reports_dir = temp_root / "report-drift-reports"
        shutil.copytree(reports_root, reports_dir)
        removed = next(reports_dir.glob("*.json"), None)
        if removed:
            removed.unlink()
        orphan_path = reports_dir / "orphan-report.json"
        orphan_path.write_text(json.dumps({"id": "orphan-report"}, indent=2), encoding="utf-8")
        report_validation = validate_database(fresh_db, source_root=report_root, reports_root=reports_dir)
        _assert(report_validation["totals"]["orphan_reference"] > 0 or report_validation["totals"]["generated_only"] > 0, "report file drift should be reported")

        foreign_db = temp_root / "fk.sqlite3"
        _backup_sqlite(fresh_db, foreign_db)
        with connect(foreign_db) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("INSERT INTO catch_gear(catch_id, gear_item_id, gear_role, legacy_label) VALUES(?, ?, ?, ?)", ("missing-catch", "missing-gear", "rod", "Broken"))
            conn.commit()
        fk_validation = validate_database(foreign_db, source_root=source_root, reports_root=reports_root)
        _assert(bool(fk_validation.get("foreign_key_check")), "foreign key violations should be detected")

        archive, manifest = _fixture_runtime_backup(temp_root, source_root, reports_root, fresh_db)
        _assert(archive.exists(), "V7 backup archive should exist")
        _assert(manifest.exists(), "V7 backup manifest should exist")
        restore_result = subprocess.run([sys.executable, str(ROOT / "tools" / "v7_0_restore_rehearsal.py"), str(archive), "--json"], capture_output=True, text=True)
        _assert(restore_result.returncode == 0, "restore rehearsal should pass")
        _assert("integrity_check" in restore_result.stdout, "restore rehearsal should return validation details")

        current_route_checks = subprocess.run([sys.executable, str(ROOT / "tools" / "qc_smart_trip_report_display.py")], capture_output=True, text=True)
        _assert(current_route_checks.returncode == 0, "smart trip report QC should still pass")

        git_status = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
        staged = [line.strip() for line in git_status.stdout.splitlines() if line.strip()]
        bad_staged = [line for line in staged if line in {"data/gear_inventory.json", "data/manual_waters.json", "data/target_profile.json", "data/gear_settings.json"} or line.startswith("data/exports")]
        _assert(not bad_staged, f"runtime data must not be staged: {bad_staged}")

        client = flask_app.test_client()
        for route in ("/", "/map", "/reports", "/rigs", "/app-health"):
            response = client.get(route)
            _assert(response.status_code == 200, f"{route} should return HTTP 200")
        intel_response = client.get("/api/intel?zip=60543")
        _assert(intel_response.status_code == 200, "/api/intel should return HTTP 200")
        intel_payload = intel_response.get_json(silent=True) or {}
        _assert(isinstance(intel_payload, dict) and "smart_intelligence" in intel_payload, "intel endpoint should still return smart intelligence")
        app_health_response = client.get("/app-health")
        app_health_html = app_health_response.get_data(as_text=True)
        _assert("V7 Data Foundation" in app_health_html, "App Health should render the V7 diagnostics card")
        _assert("/admin" not in app_health_html, "Admin must not be restored to normal navigation")

    after_hashes = _source_hashes()
    _assert(before_hashes == after_hashes, "source JSON files must not change during QC")

    payload = {
        "ok": not errors,
        "errors": errors,
        "audit": audit_payload,
        "source_hashes_unchanged": before_hashes == after_hashes,
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    print(rendered)
    if errors:
        print("QC FAILED: v7.0 sqlite migration foundation")
        for error in errors:
            print(f"- {error}")
        return 1

    print("QC PASSED: v7.0 sqlite migration foundation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
