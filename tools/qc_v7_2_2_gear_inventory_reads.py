#!/usr/bin/env python3
"""Focused QC for V7.2.2 JSON-returning gear inventory comparison reads."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.gear_inventory_mirror import mirror_gear_inventory
from persistence.migrations import migrate
from persistence.repositories import JsonGearInventoryRepository, SQLiteGearInventoryRepository, read_domain


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-2-2-qc-") as temp_dir:
        temp = Path(temp_dir); source = temp / "gear.json"; db = temp / "gear.sqlite3"
        inventory = {"version": "test", "updated_at": "2026-07-23T13:00:00", "items": [{"id": "rod-1", "category": "rod", "brand": "Test", "model": "Rod", "status": "owned"}], "maintenance": [{"note": "legacy"}], "catalog_cache": []}
        source.write_text(json.dumps(inventory), encoding="utf-8")
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
        assert mirror_gear_inventory(inventory, source, db_path=db).mirror_write_succeeded
        json_repo, sqlite_repo = JsonGearInventoryRepository(source), SQLiteGearInventoryRepository(db)
        compared = read_domain("gear_inventory", json_repository=json_repo, sqlite_repository=sqlite_repo, source="compare_json")
        assert compared.effective_source == "json" and compared.comparison_status == "exact"
        fallback = read_domain("gear_inventory", json_repository=json_repo, sqlite_repository=SQLiteGearInventoryRepository(temp / "missing.sqlite3"), source="sqlite_with_json_fallback")
        assert fallback.fallback_used and fallback.value["items"][0]["id"] == "rod-1"
    print("PASS: V7.2.2 gear inventory staged reads QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
