"""JSON-first SQLite mirroring for the authoritative catch log."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .connection import DEFAULT_DB, connect
from .mirror import MirrorResult, mirror_after_json_write
from .provenance import file_sha256

BASE_DIR = Path(__file__).resolve().parents[1]
DOMAIN = "catches"
CATCHEs_ENVELOPE_KEY = "v7.catches.envelope"


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


def _records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("catches"), list):
        return payload["catches"]
    raise ValueError("Catch source must be a list or an object with a catches list")


def _read_source(path: Path) -> tuple[Any, list[Any]]:
    if not path.exists():
        return [], []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, _records(payload)


def catches_operation_id(payload: Any, usage_events: list[dict[str, Any]] | None = None) -> str:
    return f"catches-{record_hash({'payload': payload, 'usage_events': usage_events or []})}"


def _write_map(conn, source_label: str, source_key: str, normalized_id: str | None, payload: Any, source_hash: str | None, status: str, notes: str | None) -> None:
    conn.execute(
        """INSERT INTO legacy_record_map(domain, source_path, source_key, normalized_id, payload_hash, source_hash, status, notes, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain, source_path, source_key) DO UPDATE SET
          normalized_id=excluded.normalized_id, payload_hash=excluded.payload_hash, source_hash=excluded.source_hash,
          status=excluded.status, notes=excluded.notes""",
        (DOMAIN, source_label, source_key, normalized_id, record_hash(payload), source_hash, status, notes, _utc_now()),
    )


def _write_catches(conn, source_payload: Any, source_path: Path, usage_events: list[dict[str, Any]] | None) -> None:
    records = _records(source_payload)
    source_label = _source_label(source_path)
    source_hash = file_sha256(source_path)
    valid: list[dict[str, Any]] = []
    mappings: list[tuple[str, str | None, Any, str, str | None]] = []
    seen: set[str] = set()
    for index, raw in enumerate(records):
        key = f"index-{index}"
        if not isinstance(raw, dict):
            mappings.append((key, None, raw, "invalid_source", "Catch record is not an object."))
            continue
        catch_id = _text(raw.get("id"))
        key = catch_id or key
        if not catch_id:
            mappings.append((key, None, raw, "invalid_source", "Catch record is missing a stable ID."))
            continue
        if catch_id in seen:
            raise ValueError(f"Catches contains duplicate ID: {catch_id}")
        seen.add(catch_id)
        valid.append(dict(raw))
        mappings.append((key, catch_id, raw, "mapped", None))

    catch_ids = [str(item["id"]) for item in valid]
    existing = [row[0] for row in conn.execute("SELECT id FROM catches WHERE source_path = ?", (source_label,))]
    cleanup_ids = sorted(set(existing).union(catch_ids))
    if cleanup_ids:
        placeholders = ", ".join("?" for _ in cleanup_ids)
        conn.execute(f"DELETE FROM catch_gear WHERE catch_id IN ({placeholders})", tuple(cleanup_ids))
    if existing:
        if catch_ids:
            placeholders = ", ".join("?" for _ in catch_ids)
            conn.execute(f"DELETE FROM catches WHERE source_path = ? AND id NOT IN ({placeholders})", (source_label, *catch_ids))
        else:
            conn.execute("DELETE FROM catches WHERE source_path = ?", (source_label,))
    if catch_ids:
        placeholders = ", ".join("?" for _ in catch_ids)
        conn.execute(f"DELETE FROM gear_usage WHERE catch_id IS NOT NULL AND catch_id NOT IN ({placeholders})", tuple(catch_ids))
    else:
        conn.execute("DELETE FROM gear_usage WHERE catch_id IS NOT NULL")

    map_keys = [entry[0] for entry in mappings]
    if map_keys:
        placeholders = ", ".join("?" for _ in map_keys)
        conn.execute(f"DELETE FROM legacy_record_map WHERE domain = ? AND source_path = ? AND source_key NOT IN ({placeholders})", (DOMAIN, source_label, *map_keys))
    else:
        conn.execute("DELETE FROM legacy_record_map WHERE domain = ? AND source_path = ?", (DOMAIN, source_label))

    for item in valid:
        catch_id = _text(item.get("id"))
        refs = item.get("gear_refs") if isinstance(item.get("gear_refs"), dict) else {}
        labels = item.get("gear_labels") if isinstance(item.get("gear_labels"), dict) else {}
        conn.execute(
            """INSERT INTO catches(id, timestamp, species, waterbody, lure, rig, notes, zip, gear_refs_json, gear_labels_json,
               legacy_payload_json, source_path, source_hash, source_key, created_at, updated_at)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET timestamp=excluded.timestamp, species=excluded.species, waterbody=excluded.waterbody,
               lure=excluded.lure, rig=excluded.rig, notes=excluded.notes, zip=excluded.zip,
               gear_refs_json=excluded.gear_refs_json, gear_labels_json=excluded.gear_labels_json,
               legacy_payload_json=excluded.legacy_payload_json, source_path=excluded.source_path,
               source_hash=excluded.source_hash, source_key=excluded.source_key, created_at=excluded.created_at,
               updated_at=excluded.updated_at""",
            (catch_id, _text(item.get("timestamp")), _text(item.get("species")), _text(item.get("waterbody")),
             _text(item.get("lure")), _text(item.get("rig") or item.get("setup_name")), _text(item.get("notes")),
             _text(item.get("zip")), canonical_dumps(refs), canonical_dumps(labels), canonical_dumps(item),
             source_label, source_hash, catch_id, _text(item.get("created_at"), _utc_now()), _text(item.get("updated_at"), _utc_now())),
        )
        for role, raw_ref in refs.items():
            gear_id = _text(raw_ref)
            if gear_id and not conn.execute("SELECT 1 FROM gear_items WHERE id = ?", (gear_id,)).fetchone():
                gear_id = ""
            conn.execute("INSERT INTO catch_gear(catch_id, gear_item_id, gear_role, legacy_label) VALUES(?, ?, ?, ?)",
                         (catch_id, gear_id or None, _text(role), _text(labels.get(role))))

    for key, normalized_id, raw, status, notes in mappings:
        _write_map(conn, source_label, key, normalized_id, raw, source_hash, status, notes)

    for event in usage_events or []:
        if not isinstance(event, dict):
            continue
        catch_id = _text(event.get("catch_id"))
        gear_id = _text(event.get("gear_item_id"))
        if not catch_id or not gear_id or catch_id not in catch_ids:
            continue
        if not conn.execute("SELECT 1 FROM gear_items WHERE id = ?", (gear_id,)).fetchone():
            continue
        exists = conn.execute("SELECT 1 FROM gear_usage WHERE gear_item_id = ? AND catch_id = ?", (gear_id, catch_id)).fetchone()
        if not exists:
            conn.execute("INSERT INTO gear_usage(gear_item_id, trip_id, catch_id, used_at, notes) VALUES(?, NULL, ?, ?, ?)",
                         (gear_id, catch_id, _text(event.get("used_at"), _utc_now()), canonical_dumps(event)))

    now = _utc_now()
    conn.execute("""INSERT INTO source_files(domain, logical_name, path, file_hash, record_count, source_of_truth, generated_only, last_seen_at, last_imported_at)
                 VALUES('catches', 'catches', ?, ?, ?, 'json', 0, ?, ?)
                 ON CONFLICT(domain, path) DO UPDATE SET file_hash=excluded.file_hash, record_count=excluded.record_count,
                 source_of_truth='json', generated_only=0, last_seen_at=excluded.last_seen_at, last_imported_at=excluded.last_imported_at""",
                 (source_label, source_hash, len(records), now, now))
    conn.execute("""INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
                 VALUES('catches', 'json', ?, ?, 'JSON remains authoritative during V7.1 catch mirroring.', ?)
                 ON CONFLICT(domain) DO UPDATE SET authority='json', source_path=excluded.source_path, source_hash=excluded.source_hash,
                 note=excluded.note, updated_at=excluded.updated_at""", (source_label, source_hash, now))
    conn.execute("INSERT OR REPLACE INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)",
                 (CATCHEs_ENVELOPE_KEY, canonical_dumps(source_payload), now))


def mirror_catches(source_path: str | Path, *, usage_events: list[dict[str, Any]] | None = None, db_path: str | Path = DEFAULT_DB, force: bool = False) -> MirrorResult:
    path = Path(source_path)
    try:
        payload, records = _read_source(path)
    except Exception as exc:
        return MirrorResult(DOMAIN, f"catches-invalid-{path.name}", True, False, error=f"Invalid catches JSON: {exc}", completed_at=_utc_now())
    events = [dict(item) for item in usage_events or [] if isinstance(item, dict)]
    base_operation_id = catches_operation_id(payload, events)
    return mirror_after_json_write(DOMAIN, lambda conn: _write_catches(conn, payload, path, events),
        operation_id=f"{base_operation_id}-reconcile-{uuid.uuid4().hex}" if force else base_operation_id,
        db_path=db_path, details={"source_path": _source_label(path), "source_hash": file_sha256(path), "record_count": len(records), "usage_event_count": len(events)})


def compare_catches(source_path: str | Path, *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    try:
        _, records = _read_source(Path(source_path))
    except Exception as exc:
        return {"status": "invalid_source", "differences": [str(exc)]}
    path = Path(source_path); database = Path(db_path); result = {"status": "missing_in_sqlite", "differences": []}
    if not database.exists():
        result["differences"].append("SQLite database is unavailable."); return result
    expected = {str(item.get("id")): record_hash(item) for item in records if isinstance(item, dict) and _text(item.get("id"))}
    try:
        with connect(database, read_only=True) as conn:
            source_label = _source_label(path)
            rows = [dict(row) for row in conn.execute("SELECT id, legacy_payload_json FROM catches WHERE source_path = ?", (source_label,))]
            actual = {str(row["id"]): record_hash(json.loads(row["legacy_payload_json"])) for row in rows}
            if set(expected) != set(actual): result["differences"].append("catch_ids")
            for catch_id in sorted(set(expected).intersection(actual)):
                if expected[catch_id] != actual[catch_id]: result["differences"].append(f"catch:{catch_id}")
            result["status"] = "exact" if not result["differences"] else "changed"
            return result
    except Exception as exc:
        return {"status": "invalid_source", "differences": [str(exc)]}
