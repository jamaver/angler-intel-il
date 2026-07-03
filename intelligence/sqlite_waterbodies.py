from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.sqlite_foundation import APP_ROOT, DB_PATH, connect, sha256_text
from intelligence.water_registry import load_water_records


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_waterbodies_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS waterbodies_mirror (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            water_id TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            source_path TEXT,
            source_sha256 TEXT,
            source_row_index INTEGER NOT NULL,
            name TEXT,
            water_type TEXT,
            city TEXT,
            county TEXT,
            state TEXT,
            lat REAL,
            lon REAL,
            species_json TEXT,
            species_ids_json TEXT,
            access_json TEXT,
            habitat_json TEXT,
            notes TEXT,
            confidence TEXT,
            manual INTEGER NOT NULL DEFAULT 0,
            favorite INTEGER NOT NULL DEFAULT 0,
            stocked_trout INTEGER NOT NULL DEFAULT 0,
            catch_history_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL UNIQUE,
            mirrored_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_waterbodies_water_id ON waterbodies_mirror(water_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_waterbodies_type ON waterbodies_mirror(water_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_waterbodies_favorite ON waterbodies_mirror(favorite)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_waterbodies_manual ON waterbodies_mirror(manual)")


def mirror_waterbodies(conn) -> dict[str, Any]:
    ensure_waterbodies_table(conn)

    from intelligence.water_registry import BASE_WATERS_PATH, CUSTOM_WATERS_PATH, load_water_catalog

    catalog = load_water_catalog()
    records = catalog.get("records", [])
    now = utc_now()

    conn.execute("DELETE FROM waterbodies_mirror")

    for idx, water in enumerate(records):
        payload_json = json.dumps(water, sort_keys=True, ensure_ascii=False)
        payload_hash = sha256_text(payload_json)
        conn.execute(
            """
            INSERT OR IGNORE INTO waterbodies_mirror(
                water_id, source, source_path, source_sha256, source_row_index,
                name, water_type, city, county, state, lat, lon,
                species_json, species_ids_json, access_json, habitat_json,
                notes, confidence, manual, favorite, stocked_trout,
                catch_history_count, created_at, payload_json, payload_sha256, mirrored_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(water.get("id") or f"water-{idx}"),
                str(water.get("source") or "starter"),
                str(BASE_WATERS_PATH.relative_to(APP_ROOT)) if not bool(water.get("manual")) else str(CUSTOM_WATERS_PATH.relative_to(APP_ROOT)),
                catalog.get("source_path") if not bool(water.get("manual")) else catalog.get("custom_source_path"),
                idx,
                water.get("name"),
                water.get("type"),
                water.get("city"),
                water.get("county"),
                water.get("state"),
                water.get("lat"),
                water.get("lon"),
                json.dumps(water.get("species", []), ensure_ascii=False),
                json.dumps(water.get("species_ids", []), ensure_ascii=False),
                json.dumps(water.get("access", []), ensure_ascii=False),
                json.dumps(water.get("habitat", []), ensure_ascii=False),
                water.get("notes"),
                water.get("confidence"),
                1 if water.get("manual") else 0,
                1 if water.get("favorite") else 0,
                1 if water.get("stocked_trout") else 0,
                int(water.get("catch_history_count") or 0),
                water.get("created_at"),
                payload_json,
                payload_hash,
                now,
            ),
        )

    conn.commit()

    return {
        "waterbody_count": len(records),
        "starter_count": catalog.get("base_count", 0),
        "manual_count": catalog.get("custom_count", 0),
        "mirrored_at": now,
    }


def load_waterbody_snapshot() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {"exists": False, "waterbody_count": 0, "items": []}

    with connect() as conn:
        ensure_waterbodies_table(conn)
        rows = [dict(row) for row in conn.execute("SELECT * FROM waterbodies_mirror ORDER BY water_type, name")]
        return {
            "exists": True,
            "waterbody_count": len(rows),
            "items": rows,
        }
