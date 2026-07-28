#!/usr/bin/env python3
"""Focused QC for V7.1.2 JSON-first Gear Inventory mirror writes."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gear import inventory as inventory_mod
from persistence.authority import V7_AUTHORITY
from persistence.connection import connect
from persistence.gear_inventory_mirror import compare_gear_inventory, mirror_gear_inventory
from persistence.migrations import migrate
from persistence.mirror import MirrorResult


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture_inventory() -> dict:
    return {
        "version": "v6.13-test",
        "updated_at": "2026-07-22T12:00:00-05:00",
        "items": [
            {
                "id": "rod-test", "category": "rod", "brand": "Test", "model": "Rod",
                "display_name": "Test Rod", "status": "owned", "favorite": True, "quantity": 1,
                "length_ft": 7.0, "length_label": "7 ft", "power": "medium_heavy", "action": "fast",
                "pieces": 1, "lure_weight_min_oz": 0.25, "lure_weight_max_oz": 1.0,
                "line_rating_min_lb": 12, "line_rating_max_lb": 20,
                "technique_tags": ["jig"], "species_tags": ["Largemouth Bass"],
                "image": "/static/gear/fallback/rod.svg", "image_source": "local", "source": "manual",
                "confidence": "user-added", "specifications": {"custom": "kept"}, "identifiers": {"mpn": "TEST-ROD"},
                "trips_used": 8, "catches_logged": 3, "updated_at": "2026-07-22T12:00:00-05:00",
            },
            {
                "id": "reel-test", "category": "reel", "brand": "Test", "model": "Reel",
                "display_name": "Test Reel", "status": "retired", "favorite": False, "quantity": 1,
                "reel_type": "baitcasting", "gear_ratio": 7.1, "max_drag_lb": 12,
                "line_capacity": "120 yd", "weight_oz": 7.2, "handedness": "right",
                "retired_at": "2026-07-20", "retired_reason": "backup", "source": "manual",
            },
            {
                "id": "line-test", "category": "line", "brand": "Test", "model": "Line",
                "display_name": "Test Line", "status": "owned", "favorite": False, "quantity": 1,
                "line_type": "braid", "strength_lb": 30, "color": "green", "length_yd": 150,
                "source": "manual",
            },
            {
                "id": "lure-test", "category": "lure", "brand": "Test", "model": "Lure",
                "display_name": "Test Lure", "status": "owned", "favorite": False, "quantity": 2,
                "lure_type": "spinnerbait", "color": "white_chartreuse", "weight_oz": 0.375,
                "technique_tags": ["steady_retrieve"], "species_tags": ["Largemouth Bass"],
                "provider": "manual", "source_name": "Manual", "source_url": "https://example.test/lure",
                "image_url": "https://example.test/lure.png", "confidence": "user-added",
            },
            {
                "id": "terminal-test", "category": "terminal", "brand": "Test", "model": "Hook",
                "display_name": "Test Hook", "status": "owned", "favorite": False, "quantity": 5,
                "subtype": "hook", "size": "3/0", "hook_size": "3/0", "source": "manual",
                "last_cleaned": "2026-07-21", "maintenance_interval_days": 30, "maintenance_notes": "Inspect points",
            },
        ],
        "maintenance": [],
        "catalog_cache": [{"provider": "cache-only", "title": "must not become gear"}],
    }


def main() -> int:
    for rel in ("gear/inventory.py", "persistence/gear_inventory_mirror.py", "angler_species_rigs_v43.py"):
        ast.parse((ROOT / rel).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="angler-v7-1-2-qc-") as temp_dir:
        temp = Path(temp_dir)
        db = temp / "angler_intel.sqlite3"
        source = temp / "gear_inventory.json"
        inventory = fixture_inventory()
        write_json(source, inventory)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

        with connect(db) as conn:
            migrate(conn, db_path=str(db))

        first = mirror_gear_inventory(inventory, source, db_path=db)
        assert first.source_write_succeeded and first.mirror_write_succeeded and not first.idempotent
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "mirror changed gear JSON"
        assert compare_gear_inventory(inventory, db_path=db)["status"] == "exact"
        duplicate = mirror_gear_inventory(inventory, source, db_path=db)
        assert duplicate.mirror_write_succeeded and duplicate.idempotent

        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM gear_items").fetchone()[0] == 5
            assert conn.execute("SELECT COUNT(*) FROM rod_specs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM reel_specs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM line_specs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM lure_specs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM terminal_tackle_specs").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM product_sources").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM gear_images").fetchone()[0] >= 2
            assert conn.execute("SELECT COUNT(*) FROM gear_maintenance").fetchone()[0] == 2
            assert conn.execute("SELECT COUNT(*) FROM gear_usage").fetchone()[0] == 0, "legacy counters created usage events"
            rod = conn.execute("SELECT status, favorite, legacy_payload_json FROM gear_items WHERE id='rod-test'").fetchone()
            assert rod and rod["status"] == "owned" and rod["favorite"] == 1
            assert json.loads(rod["legacy_payload_json"])["specifications"]["custom"] == "kept"
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='gear_inventory'").fetchone()[0] == V7_AUTHORITY

        # Full reconciliation reflects archive/favorite changes and deletes removed gear.
        updated = fixture_inventory()
        updated["items"][0]["favorite"] = False
        updated["items"][0]["status"] = "retired"
        updated["items"] = [item for item in updated["items"] if item["id"] != "reel-test"]
        updated["updated_at"] = "2026-07-22T12:10:00-05:00"
        write_json(source, updated)
        assert mirror_gear_inventory(updated, source, db_path=db).mirror_write_succeeded
        assert compare_gear_inventory(updated, db_path=db)["status"] == "exact"
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM gear_items WHERE id='reel-test'").fetchone()[0] == 0
            row = conn.execute("SELECT status, favorite FROM gear_items WHERE id='rod-test'").fetchone()
            assert row and row["status"] == "retired" and row["favorite"] == 0

        # Only a new usage call produces an event, and duplicate retries do not duplicate it.
        event = {"gear_item_id": "rod-test", "used_at": "2026-07-22T13:00:00-05:00", "trips": 1, "catches": 1, "source": "record_item_usage"}
        usage_result = mirror_gear_inventory(updated, source, usage_event=event, db_path=db)
        assert usage_result.mirror_write_succeeded
        assert mirror_gear_inventory(updated, source, usage_event=event, db_path=db).idempotent
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM gear_usage WHERE gear_item_id='rod-test'").fetchone()[0] == 1

        # Missing SQLite is non-fatal and never creates a new database or changes JSON.
        before_missing = hashlib.sha256(source.read_bytes()).hexdigest()
        missing_db = temp / "missing.sqlite3"
        missing = mirror_gear_inventory(updated, source, db_path=missing_db)
        assert not missing.mirror_write_succeeded and missing.source_write_succeeded and not missing_db.exists()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before_missing

        # Actual inventory writer saves JSON before a non-fatal mirror failure.
        original_path = inventory_mod.inventory_path
        original_mirror = inventory_mod.mirror_gear_inventory
        original_authority_check = inventory_mod.is_gear_inventory_sqlite_authoritative
        original_write_authority = inventory_mod.require_write_authority
        original_sqlite_save = inventory_mod.save_gear_inventory_sqlite_authoritative
        original_db = os.environ.get("AI_SQLITE_DB_PATH")
        try:
            inventory_mod.inventory_path = lambda: source
            os.environ["AI_SQLITE_DB_PATH"] = str(db)
            inventory_mod.is_gear_inventory_sqlite_authoritative = lambda _path: False
            inventory_mod.require_write_authority = lambda *_args, **_kwargs: "json"

            def sqlite_save_must_not_run(*_args, **_kwargs):
                raise AssertionError("V7.1 mirror QC attempted the SQLite-authoritative Gear Locker writer")

            inventory_mod.save_gear_inventory_sqlite_authoritative = sqlite_save_must_not_run
            captured: dict[str, object] = {}

            def temp_mirror(saved_inventory, saved_path, *, usage_event=None):
                return mirror_gear_inventory(saved_inventory, saved_path, usage_event=usage_event, db_path=db)

            inventory_mod.mirror_gear_inventory = temp_mirror
            usage_item = inventory_mod.record_item_usage("rod-test", used_at="2026-07-22T14:00:00-05:00", trips=2, catches=1)
            assert usage_item is not None
            with connect(db, read_only=True) as conn:
                assert conn.execute("SELECT COUNT(*) FROM gear_usage WHERE gear_item_id='rod-test'").fetchone()[0] == 2

            def failed_mirror(saved_inventory, saved_path, *, usage_event=None):
                captured["inventory"] = saved_inventory
                captured["path"] = saved_path
                return MirrorResult("gear_inventory", "fixture", True, False, error="fixture unavailable")

            inventory_mod.mirror_gear_inventory = failed_mirror
            saved = inventory_mod.upsert_item({"category": "lure", "brand": "Local", "model": "Manual"})
            payload = json.loads(source.read_text(encoding="utf-8"))
            assert any(item.get("id") == saved["id"] for item in payload["items"])
            assert captured["inventory"] == payload and captured["path"] == source
        finally:
            inventory_mod.inventory_path = original_path
            inventory_mod.mirror_gear_inventory = original_mirror
            inventory_mod.is_gear_inventory_sqlite_authoritative = original_authority_check
            inventory_mod.require_write_authority = original_write_authority
            inventory_mod.save_gear_inventory_sqlite_authoritative = original_sqlite_save
            if original_db is None:
                os.environ.pop("AI_SQLITE_DB_PATH", None)
            else:
                os.environ["AI_SQLITE_DB_PATH"] = original_db

        # Locker CRUD remains JSON-first even when the mirror database is absent.
        offline_source = temp / "offline_inventory.json"
        write_json(offline_source, {"version": "fixture", "items": [], "maintenance": [], "catalog_cache": []})
        offline_db = temp / "offline.sqlite3"
        original_path = inventory_mod.inventory_path
        original_mirror = inventory_mod.mirror_gear_inventory
        original_authority_check = inventory_mod.is_gear_inventory_sqlite_authoritative
        original_write_authority = inventory_mod.require_write_authority
        original_sqlite_save = inventory_mod.save_gear_inventory_sqlite_authoritative
        original_db = os.environ.get("AI_SQLITE_DB_PATH")
        try:
            inventory_mod.inventory_path = lambda: offline_source
            os.environ["AI_SQLITE_DB_PATH"] = str(offline_db)
            inventory_mod.is_gear_inventory_sqlite_authoritative = lambda _path: False
            inventory_mod.require_write_authority = lambda *_args, **_kwargs: "json"
            inventory_mod.save_gear_inventory_sqlite_authoritative = sqlite_save_must_not_run

            def unavailable_mirror(saved_inventory, saved_path, *, usage_event=None):
                return mirror_gear_inventory(saved_inventory, saved_path, usage_event=usage_event, db_path=offline_db)

            inventory_mod.mirror_gear_inventory = unavailable_mirror
            offline_item = inventory_mod.upsert_item({"category": "rod", "brand": "Offline", "model": "Rod"})
            assert offline_item and not offline_db.exists()
            assert inventory_mod.toggle_favorite(offline_item["id"], True)
            assert inventory_mod.set_status(offline_item["id"], "retired")
            assert inventory_mod.restore_item(offline_item["id"])
            assert inventory_mod.delete_item(offline_item["id"])
            assert json.loads(offline_source.read_text(encoding="utf-8"))["items"] == []
        finally:
            inventory_mod.inventory_path = original_path
            inventory_mod.mirror_gear_inventory = original_mirror
            inventory_mod.is_gear_inventory_sqlite_authoritative = original_authority_check
            inventory_mod.require_write_authority = original_write_authority
            inventory_mod.save_gear_inventory_sqlite_authoritative = original_sqlite_save
            if original_db is None:
                os.environ.pop("AI_SQLITE_DB_PATH", None)
            else:
                os.environ["AI_SQLITE_DB_PATH"] = original_db

    print("PASS: V7.1.2 gear inventory mirror QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
