"""JSON-first SQLite mirroring for user-managed manual water records."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .connection import DEFAULT_DB, connect
from .mirror import MirrorResult, mirror_after_json_write
from .provenance import file_sha256

BASE_DIR = Path(__file__).resolve().parents[1]
DOMAIN = "manual_waters"
CATALOG_ENVELOPE_KEY = "v7.water_catalog.envelope"
MANUAL_WATERS_ENVELOPE_KEY = "v7.manual_waters.envelope"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, fallback: str = "") -> str:
    value = " ".join(str(value or "").split()).strip()
    return value or fallback


def _source_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _source_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("waters"), list):
        return payload["waters"]
    raise ValueError("Manual waters source must be a list or an object with a waters list")


def _read_source(path: Path) -> tuple[Any, list[Any]]:
    if not path.exists():
        return [], []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, _source_items(payload)


def _record_id(item: dict[str, Any]) -> str:
    return _text(item.get("id"))


def manual_waters_operation_id(source_payload: Any) -> str:
    """Derive a retry-safe operation ID from the complete JSON source document."""
    return f"manual-waters-{record_hash(source_payload)}"


def _validation_note(item: dict[str, Any]) -> str | None:
    if not _text(item.get("name")):
        return "Missing waterbody name."
    if not _record_id(item):
        return "Missing waterbody ID."
    try:
        lat = item.get("lat")
        lon = item.get("lon")
        if lat in (None, "") or lon in (None, ""):
            return "Coordinates are missing; retained for validation but not map display."
        float(lat)
        float(lon)
    except (TypeError, ValueError):
        return "Coordinates are invalid; retained for validation but not map display."
    return None


def _write_record_map(
    conn: sqlite3.Connection,
    *,
    source_label: str,
    source_key: str,
    normalized_id: str | None,
    payload: Any,
    source_hash: str | None,
    status: str,
    notes: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO legacy_record_map(
            domain, source_path, source_key, normalized_id, payload_hash, source_hash,
            status, notes, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain, source_path, source_key) DO UPDATE SET
            normalized_id=excluded.normalized_id, payload_hash=excluded.payload_hash,
            source_hash=excluded.source_hash, status=excluded.status, notes=excluded.notes
        """,
        (DOMAIN, source_label, source_key, normalized_id, record_hash(payload), source_hash, status, notes, _utc_now()),
    )


def _write_waterbody(conn: sqlite3.Connection, item: dict[str, Any], *, source_label: str, source_hash: str | None) -> None:
    water_id = _record_id(item)
    species = item.get("species") if isinstance(item.get("species"), list) else []
    species_ids = item.get("species_ids") if isinstance(item.get("species_ids"), list) else []
    conn.execute(
        """
        INSERT INTO waterbodies(
            id, name, water_type, city, county, state, lat, lon, source_kind,
            source_path, source_hash, source_key, manual, favorite, stocked_trout,
            catch_history_count, confidence, access_json, habitat_json, species_json,
            species_ids_json, notes, legacy_payload_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, water_type=excluded.water_type, city=excluded.city,
            county=excluded.county, state=excluded.state, lat=excluded.lat, lon=excluded.lon,
            source_kind='manual', source_path=excluded.source_path, source_hash=excluded.source_hash,
            source_key=excluded.source_key, manual=1, favorite=excluded.favorite,
            stocked_trout=excluded.stocked_trout, catch_history_count=excluded.catch_history_count,
            confidence=excluded.confidence, access_json=excluded.access_json,
            habitat_json=excluded.habitat_json, species_json=excluded.species_json,
            species_ids_json=excluded.species_ids_json, notes=excluded.notes,
            legacy_payload_json=excluded.legacy_payload_json, created_at=excluded.created_at,
            updated_at=excluded.updated_at
        """,
        (
            water_id, _text(item.get("name")), _text(item.get("type"), "water"),
            _text(item.get("city")), _text(item.get("county")), _text(item.get("state")),
            item.get("lat"), item.get("lon"), source_label, source_hash, water_id,
            1 if item.get("favorite") else 0, 1 if item.get("stocked_trout") else 0,
            int(item.get("catch_history_count") or 0), _text(item.get("confidence"), "manual"),
            canonical_dumps(item.get("access", [])), canonical_dumps(item.get("habitat", [])),
            canonical_dumps(species), canonical_dumps(species_ids), _text(item.get("notes")),
            canonical_dumps(item), _text(item.get("created_at"), _utc_now()),
            _text(item.get("updated_at"), _utc_now()),
        ),
    )
    for alias in {_text(item.get("name")), _text(item.get("city")), _text(item.get("county"))}:
        if alias:
            conn.execute(
                "INSERT INTO waterbody_aliases(waterbody_id, alias, source_path) VALUES(?, ?, ?)",
                (water_id, alias, source_label),
            )
    for species_id in species_ids:
        normalized_species_id = _text(species_id)
        if normalized_species_id and conn.execute("SELECT 1 FROM species WHERE id = ?", (normalized_species_id,)).fetchone():
            conn.execute(
                "INSERT OR IGNORE INTO waterbody_species(waterbody_id, species_id, confidence, source_path) VALUES(?, ?, ?, ?)",
                (water_id, normalized_species_id, _text(item.get("confidence")), source_label),
            )
    for tag in item.get("habitat", []) if isinstance(item.get("habitat"), list) else []:
        if _text(tag):
            conn.execute(
                "INSERT INTO waterbody_tags(waterbody_id, tag, source_path) VALUES(?, ?, ?)",
                (water_id, _text(tag), source_label),
            )


def _write_manual_waters(
    conn: sqlite3.Connection,
    source_payload: Any,
    source_path: Path,
    *,
    authority: str = "json",
    update_catalog_snapshot: bool = True,
) -> None:
    authority_row = conn.execute(
        "SELECT authority FROM data_authority WHERE domain = ?", (DOMAIN,)
    ).fetchone()
    if authority_row and authority_row["authority"] == "sqlite" and authority != "sqlite":
        raise RuntimeError("manual_waters is SQLite-authoritative; JSON-to-SQLite mirroring is disabled.")
    records = _source_items(source_payload)
    source_label = _source_label(source_path)
    source_hash = file_sha256(source_path)
    seen_ids: set[str] = set()
    valid_records: list[dict[str, Any]] = []
    record_map_entries: list[tuple[str, str | None, Any, str, str | None]] = []

    for index, raw_item in enumerate(records):
        source_key = f"index-{index}"
        if not isinstance(raw_item, dict):
            record_map_entries.append((source_key, None, raw_item, "invalid_source", "Manual water record is not an object."))
            continue
        water_id = _record_id(raw_item)
        source_key = water_id or source_key
        if water_id and water_id in seen_ids:
            raise ValueError(f"Manual waters contains duplicate ID: {water_id}")
        if water_id:
            seen_ids.add(water_id)
        note = _validation_note(raw_item)
        if not water_id or not _text(raw_item.get("name")):
            record_map_entries.append((source_key, None, raw_item, "invalid_source", note))
            continue
        valid_records.append(dict(raw_item))
        record_map_entries.append((source_key, water_id, raw_item, "mapped" if note is None else "invalid_source", note))

    manual_ids = [str(item["id"]) for item in valid_records]
    existing_manual_ids = [
        row[0]
        for row in conn.execute("SELECT id FROM waterbodies WHERE manual = 1 AND source_path = ?", (source_label,))
    ]
    cleanup_ids = sorted(set(existing_manual_ids).union(manual_ids))
    if cleanup_ids:
        placeholders = ", ".join("?" for _ in cleanup_ids)
        for table in ("waterbody_aliases", "waterbody_species", "waterbody_tags"):
            conn.execute(f"DELETE FROM {table} WHERE waterbody_id IN ({placeholders})", tuple(cleanup_ids))
    if existing_manual_ids:
        if manual_ids:
            placeholders = ", ".join("?" for _ in manual_ids)
            conn.execute(
                f"DELETE FROM waterbodies WHERE manual = 1 AND source_path = ? AND id NOT IN ({placeholders})",
                (source_label, *manual_ids),
            )
        else:
            conn.execute("DELETE FROM waterbodies WHERE manual = 1 AND source_path = ?", (source_label,))

    active_keys = [entry[0] for entry in record_map_entries]
    if active_keys:
        placeholders = ", ".join("?" for _ in active_keys)
        conn.execute(
            f"DELETE FROM legacy_record_map WHERE domain = ? AND source_path = ? AND source_key NOT IN ({placeholders})",
            (DOMAIN, source_label, *active_keys),
        )
    else:
        conn.execute("DELETE FROM legacy_record_map WHERE domain = ? AND source_path = ?", (DOMAIN, source_label))

    for item in valid_records:
        _write_waterbody(conn, item, source_label=source_label, source_hash=source_hash)
    for source_key, normalized_id, raw_item, status, note in record_map_entries:
        _write_record_map(
            conn, source_label=source_label, source_key=source_key, normalized_id=normalized_id,
            payload=raw_item, source_hash=source_hash, status=status, notes=note,
        )

    now = _utc_now()
    conn.execute(
        """
        INSERT INTO source_files(domain, logical_name, path, file_hash, record_count, source_of_truth, generated_only, last_seen_at, last_imported_at)
        VALUES(?, 'manual_waters', ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(domain, path) DO UPDATE SET
            file_hash=excluded.file_hash, record_count=excluded.record_count, source_of_truth=excluded.source_of_truth,
            generated_only=0, last_seen_at=excluded.last_seen_at, last_imported_at=excluded.last_imported_at
        """,
        (DOMAIN, source_label, source_hash, len(records), "sqlite" if authority == "sqlite" else "json", now, now),
    )
    conn.execute(
        """
        INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            authority=excluded.authority, source_path=excluded.source_path, source_hash=excluded.source_hash,
            note=excluded.note, updated_at=excluded.updated_at
        """,
        (
            DOMAIN,
            authority,
            source_label,
            source_hash,
            "SQLite is authoritative; JSON is a compatibility export."
            if authority == "sqlite"
            else "JSON remains authoritative during V7.1 manual-water mirroring.",
            now,
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)",
        (MANUAL_WATERS_ENVELOPE_KEY, canonical_dumps(source_payload), now),
    )
    # Keep the exact JSON-derived map projection for V7.2 comparison reads.
    # This is a mirror snapshot only; the registry remains JSON-authoritative.
    if update_catalog_snapshot:
        from intelligence.water_registry import _load_water_catalog_json
        catalog = _load_water_catalog_json(include_custom=True)
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)",
            (CATALOG_ENVELOPE_KEY, canonical_dumps(catalog), now),
        )


def mirror_manual_waters(
    source_path: str | Path,
    *,
    db_path: str | Path = DEFAULT_DB,
    force: bool = False,
) -> MirrorResult:
    """Mirror a complete already-saved manual-water JSON document into SQLite."""
    path = Path(source_path)
    try:
        source_payload, records = _read_source(path)
    except Exception as exc:
        return MirrorResult(DOMAIN, f"manual-waters-invalid-{path.name}", True, False, error=f"Invalid manual waters JSON: {exc}", completed_at=_utc_now())
    base_operation_id = manual_waters_operation_id(source_payload)
    return mirror_after_json_write(
        DOMAIN,
        lambda conn: _write_manual_waters(conn, source_payload, path),
        operation_id=f"{base_operation_id}-reconcile-{uuid.uuid4().hex}" if force else base_operation_id,
        db_path=db_path,
        details={
            "source_path": _source_label(path),
            "source_hash": file_sha256(path),
            "record_count": len(records),
        },
    )


def compare_manual_waters(source_path: str | Path, *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Read-only drift comparison for valid manual records and source metadata."""
    result: dict[str, Any] = {"status": "missing_in_sqlite", "differences": []}
    path = Path(source_path)
    try:
        source_payload, records = _read_source(path)
    except Exception as exc:
        return {"status": "invalid_source", "differences": [str(exc)]}
    database = Path(db_path)
    if not database.exists():
        result["differences"].append("SQLite database is unavailable.")
        return result
    source_label = _source_label(path)
    expected: dict[str, str] = {}
    invalid_keys: set[str] = set()
    for index, raw_item in enumerate(records):
        if not isinstance(raw_item, dict):
            invalid_keys.add(f"index-{index}")
            continue
        source_key = _record_id(raw_item) or f"index-{index}"
        if not _record_id(raw_item) or not _text(raw_item.get("name")):
            invalid_keys.add(source_key)
            continue
        expected[_record_id(raw_item)] = record_hash(raw_item)
    try:
        with connect(database, read_only=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT id, legacy_payload_json FROM waterbodies WHERE manual = 1 AND source_path = ?", (source_label,))]
            actual = {str(row["id"]): record_hash(json.loads(row["legacy_payload_json"])) for row in rows}
            if set(expected) != set(actual):
                result["differences"].append("water_ids")
            for water_id in sorted(set(expected).intersection(actual)):
                if expected[water_id] != actual[water_id]:
                    result["differences"].append(f"water:{water_id}")
            if invalid_keys:
                mapped_invalid = {
                    str(row[0]) for row in conn.execute(
                        "SELECT source_key FROM legacy_record_map WHERE domain = ? AND source_path = ? AND status = 'invalid_source'",
                        (DOMAIN, source_label),
                    )
                }
                if not invalid_keys.issubset(mapped_invalid):
                    result["differences"].append("invalid_records")
            source_row = conn.execute("SELECT file_hash, record_count FROM source_files WHERE domain = ? AND path = ?", (DOMAIN, source_label)).fetchone()
            if not source_row or source_row["file_hash"] != file_sha256(path) or int(source_row["record_count"]) != len(records):
                result["differences"].append("source_file")
            result["status"] = "exact" if not result["differences"] else "changed"
            return result
    except Exception as exc:
        return {"status": "invalid_source", "differences": [str(exc)]}
