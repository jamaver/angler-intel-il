#!/usr/bin/env python3
"""Focused QC for V7.1.4 JSON-first catch mirror writes."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None

from persistence.catches_mirror import compare_catches, mirror_catches
from persistence.connection import connect
from persistence.gear_inventory_mirror import mirror_gear_inventory
from persistence.migrations import migrate


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-1-4-qc-") as temp_dir:
        root = Path(temp_dir); db = root / "a.sqlite3"; source = root / "catches.json"; gear = root / "gear.json"
        inventory = {"items": [{"id": "rod-1", "category": "rod", "brand": "Test", "model": "Rod", "display_name": "Test Rod", "status": "owned", "quantity": 1}], "maintenance": [], "catalog_cache": []}
        catches = [
            {"id": "catch-1", "timestamp": "2026-07-22", "species": "Largemouth Bass", "waterbody": "Pond", "lure": "Jig", "gear_refs": {"rod": "rod-1", "reel": "missing"}, "gear_labels": {"rod": "Test Rod", "reel": "Old Reel"}},
            {"id": "catch-2", "timestamp": "2026-07-22", "species": "Bluegill", "waterbody": "Creek"},
        ]
        write(gear, inventory); write(source, catches); before = hashlib.sha256(source.read_bytes()).hexdigest()
        with connect(db) as conn: migrate(conn, db_path=str(db))
        assert mirror_gear_inventory(inventory, gear, db_path=db).mirror_write_succeeded
        event = {"catch_id": "catch-1", "gear_item_id": "rod-1", "used_at": "2026-07-22", "source": "catch_log"}
        first = mirror_catches(source, usage_events=[event], db_path=db)
        assert first.mirror_write_succeeded and hashlib.sha256(source.read_bytes()).hexdigest() == before
        assert compare_catches(source, db_path=db)["status"] == "exact"
        assert mirror_catches(source, usage_events=[event], db_path=db).idempotent
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM catches").fetchone()[0] == 2
            assert conn.execute("SELECT COUNT(*) FROM catch_gear WHERE gear_item_id IS NULL").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM gear_usage WHERE catch_id = 'catch-1'").fetchone()[0] == 1
            assert conn.execute("SELECT authority FROM data_authority WHERE domain = 'catches'").fetchone()[0] == "json"
        write(source, catches[:1])
        assert mirror_catches(source, db_path=db).mirror_write_succeeded
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM catches").fetchone()[0] == 1
        duplicate = catches + [dict(catches[0])]; write(source, duplicate)
        failed = mirror_catches(source, db_path=db)
        assert failed.source_write_succeeded and not failed.mirror_write_succeeded and "duplicate ID" in (failed.error or "")
        missing = root / "missing.sqlite3"; write(source, catches)
        offline = mirror_catches(source, db_path=missing)
        assert offline.source_write_succeeded and not offline.mirror_write_succeeded and not missing.exists()
    print("PASS: V7.1.4 catch mirror QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
