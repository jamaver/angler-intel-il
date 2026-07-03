from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
DB_PATH = DATA_DIR / "angler_intel.sqlite3"

CORE_JSON_FILES = [
    DATA_DIR / "favorites.json",
    DATA_DIR / "catches.json",
    DATA_DIR / "waters.json",
    DATA_DIR / "waterbodies.json",
    DATA_DIR / "manual_waters.json",
    DATA_DIR / "saved_reports.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json_file(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def normalize_items(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "records", "catches", "favorites", "waters", "waterbodies", "reports", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def pick_first(d: dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = d.get(key)
        if value is not None and value != "":
            return str(value)
    return default


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS json_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logical_name TEXT NOT NULL UNIQUE,
            path TEXT NOT NULL,
            sha256 TEXT,
            row_count INTEGER NOT NULL DEFAULT 0,
            source_of_truth TEXT NOT NULL DEFAULT 'json',
            last_loaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS json_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            item_index INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES json_sources(id) ON DELETE CASCADE,
            UNIQUE(source_id, item_index, payload_sha256)
        );

        CREATE TABLE IF NOT EXISTS favorites_mirror (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            json_source_id INTEGER,
            item_index INTEGER NOT NULL,
            name TEXT,
            waterbody TEXT,
            species TEXT,
            notes TEXT,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL UNIQUE,
            mirrored_at TEXT NOT NULL,
            FOREIGN KEY(json_source_id) REFERENCES json_sources(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS catches_mirror (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            json_source_id INTEGER,
            item_index INTEGER NOT NULL,
            catch_date TEXT,
            species TEXT,
            waterbody TEXT,
            lure TEXT,
            rig TEXT,
            notes TEXT,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL UNIQUE,
            mirrored_at TEXT NOT NULL,
            FOREIGN KEY(json_source_id) REFERENCES json_sources(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS reports_mirror (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            json_source_id INTEGER,
            item_index INTEGER NOT NULL,
            title TEXT,
            report_date TEXT,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL UNIQUE,
            mirrored_at TEXT NOT NULL,
            FOREIGN KEY(json_source_id) REFERENCES json_sources(id) ON DELETE SET NULL
        );

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
        );

        CREATE INDEX IF NOT EXISTS idx_catches_species ON catches_mirror(species);
        CREATE INDEX IF NOT EXISTS idx_catches_waterbody ON catches_mirror(waterbody);
        CREATE INDEX IF NOT EXISTS idx_favorites_waterbody ON favorites_mirror(waterbody);
        CREATE INDEX IF NOT EXISTS idx_waterbodies_water_id ON waterbodies_mirror(water_id);
        CREATE INDEX IF NOT EXISTS idx_waterbodies_type ON waterbodies_mirror(water_type);
        CREATE INDEX IF NOT EXISTS idx_waterbodies_favorite ON waterbodies_mirror(favorite);
        CREATE INDEX IF NOT EXISTS idx_waterbodies_manual ON waterbodies_mirror(manual);
        """
    )

    conn.execute(
        """
        INSERT INTO app_meta(key, value, updated_at)
        VALUES('sqlite_foundation_version', 'v4.5', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (utc_now(),),
    )
    conn.execute(
        """
        INSERT INTO app_meta(key, value, updated_at)
        VALUES('json_source_of_truth', 'true', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (utc_now(),),
    )
    conn.commit()


def register_json_source(conn: sqlite3.Connection, path: Path, payload: Any) -> int:
    logical_name = path.stem
    raw = path.read_bytes() if path.exists() else b""
    file_hash = sha256_bytes(raw) if raw else None
    row_count = len(normalize_items(payload))
    now = utc_now()

    conn.execute(
        """
        INSERT INTO json_sources(logical_name, path, sha256, row_count, source_of_truth, last_loaded_at)
        VALUES(?, ?, ?, ?, 'json', ?)
        ON CONFLICT(logical_name) DO UPDATE SET
            path=excluded.path,
            sha256=excluded.sha256,
            row_count=excluded.row_count,
            source_of_truth='json',
            last_loaded_at=excluded.last_loaded_at
        """,
        (logical_name, str(path.relative_to(APP_ROOT)), file_hash, row_count, now),
    )

    row = conn.execute(
        "SELECT id FROM json_sources WHERE logical_name = ?",
        (logical_name,),
    ).fetchone()
    return int(row["id"])


def mirror_json_file(conn: sqlite3.Connection, path: Path) -> dict[str, Any]:
    payload = load_json_file(path)
    if payload is None:
        return {
            "path": str(path.relative_to(APP_ROOT)),
            "exists": path.exists(),
            "items": 0,
            "mirrored": False,
        }

    source_id = register_json_source(conn, path, payload)
    items = normalize_items(payload)
    now = utc_now()

    conn.execute("DELETE FROM json_documents WHERE source_id = ?", (source_id,))

    for idx, item in enumerate(items):
        payload_json = json.dumps(item, sort_keys=True, ensure_ascii=False)
        payload_hash = sha256_text(payload_json)
        conn.execute(
            """
            INSERT OR IGNORE INTO json_documents(
                source_id, item_index, payload_json, payload_sha256, captured_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, idx, payload_json, payload_hash, now),
        )

    if path.name == "favorites.json":
        mirror_favorites(conn, source_id, items)

    if path.name == "catches.json":
        mirror_catches(conn, source_id, items)

    if path.name == "saved_reports.json":
        mirror_reports(conn, source_id, items)

    conn.commit()

    return {
        "path": str(path.relative_to(APP_ROOT)),
        "exists": True,
        "items": len(items),
        "mirrored": True,
    }


def mirror_favorites(conn: sqlite3.Connection, source_id: int, items: list[Any]) -> None:
    conn.execute("DELETE FROM favorites_mirror WHERE json_source_id = ?", (source_id,))
    now = utc_now()

    for idx, item in enumerate(items):
        d = item if isinstance(item, dict) else {"value": item}
        payload_json = json.dumps(d, sort_keys=True, ensure_ascii=False)
        payload_hash = sha256_text(payload_json)

        conn.execute(
            """
            INSERT OR IGNORE INTO favorites_mirror(
                json_source_id, item_index, name, waterbody, species, notes,
                payload_json, payload_sha256, mirrored_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                idx,
                pick_first(d, ("name", "title", "label")),
                pick_first(d, ("waterbody", "water", "lake", "river", "location")),
                pick_first(d, ("species", "fish", "target_species")),
                pick_first(d, ("notes", "note", "description")),
                payload_json,
                payload_hash,
                now,
            ),
        )


def mirror_catches(conn: sqlite3.Connection, source_id: int, items: list[Any]) -> None:
    conn.execute("DELETE FROM catches_mirror WHERE json_source_id = ?", (source_id,))
    now = utc_now()

    for idx, item in enumerate(items):
        d = item if isinstance(item, dict) else {"value": item}
        payload_json = json.dumps(d, sort_keys=True, ensure_ascii=False)
        payload_hash = sha256_text(payload_json)

        conn.execute(
            """
            INSERT OR IGNORE INTO catches_mirror(
                json_source_id, item_index, catch_date, species, waterbody,
                lure, rig, notes, payload_json, payload_sha256, mirrored_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                idx,
                pick_first(d, ("date", "catch_date", "created_at", "timestamp")),
                pick_first(d, ("species", "fish", "target_species")),
                pick_first(d, ("waterbody", "water", "lake", "river", "location")),
                pick_first(d, ("lure", "bait", "presentation")),
                pick_first(d, ("rig", "setup", "technique")),
                pick_first(d, ("notes", "note", "description")),
                payload_json,
                payload_hash,
                now,
            ),
        )


def mirror_reports(conn: sqlite3.Connection, source_id: int, items: list[Any]) -> None:
    conn.execute("DELETE FROM reports_mirror WHERE json_source_id = ?", (source_id,))
    now = utc_now()

    for idx, item in enumerate(items):
        d = item if isinstance(item, dict) else {"value": item}
        payload_json = json.dumps(d, sort_keys=True, ensure_ascii=False)
        payload_hash = sha256_text(payload_json)

        conn.execute(
            """
            INSERT OR IGNORE INTO reports_mirror(
                json_source_id, item_index, title, report_date,
                payload_json, payload_sha256, mirrored_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                idx,
                pick_first(d, ("title", "name", "label")),
                pick_first(d, ("date", "report_date", "created_at", "timestamp")),
                payload_json,
                payload_hash,
                now,
            ),
        )


def discover_json_files() -> list[Path]:
    found: list[Path] = []

    for path in CORE_JSON_FILES:
        if path.exists():
            found.append(path)

    saved_reports_dir = DATA_DIR / "saved_reports"
    if saved_reports_dir.exists():
        found.extend(sorted(saved_reports_dir.glob("*.json")))

    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for path in found:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)

    return unique


def initialize_and_mirror() -> dict[str, Any]:
    with connect() as conn:
        init_schema(conn)
        files = discover_json_files()
        results = [mirror_json_file(conn, path) for path in files]
        from intelligence.sqlite_waterbodies import mirror_waterbodies

        waterbody_result = mirror_waterbodies(conn)

        table_counts = {}
        for table in (
            "app_meta",
            "json_sources",
            "json_documents",
            "favorites_mirror",
            "catches_mirror",
            "reports_mirror",
            "waterbodies_mirror",
        ):
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            table_counts[table] = int(row["n"])

    return {
        "database": str(DB_PATH.relative_to(APP_ROOT)),
        "json_source_of_truth": True,
        "files": results,
        "waterbodies": waterbody_result,
        "table_counts": table_counts,
    }


def status() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {
            "database": str(DB_PATH.relative_to(APP_ROOT)),
            "exists": False,
            "message": "SQLite database has not been initialized yet.",
        }

    with connect() as conn:
        tables = [
            "app_meta",
            "json_sources",
            "json_documents",
            "favorites_mirror",
            "catches_mirror",
            "reports_mirror",
            "waterbodies_mirror",
        ]
        counts = {}
        for table in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                counts[table] = int(row["n"])
            except sqlite3.Error:
                counts[table] = None

        sources = [
            dict(row)
            for row in conn.execute(
                """
                SELECT logical_name, path, row_count, source_of_truth, last_loaded_at
                FROM json_sources
                ORDER BY logical_name
                """
            ).fetchall()
        ]

    return {
        "database": str(DB_PATH.relative_to(APP_ROOT)),
        "exists": True,
        "json_source_of_truth": True,
        "table_counts": counts,
        "sources": sources,
    }
