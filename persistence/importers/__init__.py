from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from ..authority import V7_AUTHORITY
from ..canonical_json import canonical_dumps, record_hash
from ..migrations import ensure_metadata_schema
from ..provenance import file_sha256, text_sha256

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: Any, fallback: str = "item") -> str:
    text = " ".join(str(value or "").split()).strip().lower()
    text = "".join(ch if ch.isalnum() else "-" for ch in text)
    text = "-".join(part for part in text.split("-") if part)
    return text or fallback


def _text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_json_status(path: Path, default: Any) -> tuple[bool, Any, str | None]:
    if not path.exists():
        return False, default, "missing"
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return True, default, "empty"
        return True, json.loads(text), None
    except Exception as exc:
        return True, default, str(exc)


def _safe_rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(BASE_DIR))
    except Exception:
        return str(path)


def _write_source_file(conn, *, domain: str, path: Path, record_count: int, generated_only: bool = False, source_of_truth: str = "json", last_imported_at: str | None = None) -> None:
    ensure_metadata_schema(conn)
    file_hash = file_sha256(path)
    conn.execute(
        """
        INSERT INTO source_files(domain, logical_name, path, file_hash, record_count, source_of_truth, generated_only, last_seen_at, last_imported_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain, path) DO UPDATE SET
            logical_name=excluded.logical_name,
            file_hash=excluded.file_hash,
            record_count=excluded.record_count,
            source_of_truth=excluded.source_of_truth,
            generated_only=excluded.generated_only,
            last_seen_at=excluded.last_seen_at,
            last_imported_at=excluded.last_imported_at
        """,
        (
            domain,
            path.stem,
            _safe_rel(path),
            file_hash,
            record_count,
            source_of_truth,
            1 if generated_only else 0,
            utc_now(),
            last_imported_at,
        ),
    )


def _write_authority(conn, domain: str, source_path: Path | None = None, source_hash: str | None = None) -> None:
    ensure_metadata_schema(conn)
    conn.execute(
        """
        INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
        VALUES(?, 'json', ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            authority='json',
            source_path=excluded.source_path,
            source_hash=excluded.source_hash,
            note=excluded.note,
            updated_at=excluded.updated_at
        """,
        (
            domain,
            _safe_rel(source_path) if source_path else None,
            source_hash,
            "JSON remains authoritative in V7.0",
            utc_now(),
        ),
    )


def _record_map(conn, *, domain: str, source_path: Path, source_key: str, normalized_id: str | None, payload: dict[str, Any], status: str = "mapped", notes: str | None = None) -> None:
    ensure_metadata_schema(conn)
    payload_hash = record_hash(payload)
    conn.execute(
        """
        INSERT INTO legacy_record_map(domain, source_path, source_key, normalized_id, payload_hash, source_hash, status, notes, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain, source_path, source_key) DO UPDATE SET
            normalized_id=excluded.normalized_id,
            payload_hash=excluded.payload_hash,
            source_hash=excluded.source_hash,
            status=excluded.status,
            notes=excluded.notes
        """,
        (
            domain,
            _safe_rel(source_path),
            source_key,
            normalized_id,
            payload_hash,
            file_sha256(source_path),
            status,
            notes,
            utc_now(),
        ),
    )


def _source_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "records", "catches", "favorites", "waters", "waterbodies", "reports", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def _stable_key(record: dict[str, Any], keys: Iterable[str], fallback: str) -> str:
    for key in keys:
        value = _text(record.get(key), "")
        if value:
            return value
    return fallback


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _clear_table(conn, table: str) -> None:
    conn.execute(f"DELETE FROM {table}")


def _upsert_many(conn, table: str, rows: list[dict[str, Any]], unique_keys: Iterable[str]) -> None:
    if not rows:
        return
    columns = sorted({key for row in rows for key in row.keys()})
    placeholders = ", ".join("?" for _ in columns)
    column_clause = ", ".join(columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in set(unique_keys))
    unique_clause = ", ".join(unique_keys)
    if update_clause:
        sql = f"INSERT INTO {table} ({column_clause}) VALUES ({placeholders}) ON CONFLICT({unique_clause}) DO UPDATE SET {update_clause}"
    else:
        sql = f"INSERT OR IGNORE INTO {table} ({column_clause}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(sql, tuple(row.get(column) for column in columns))


def _species_id(name: Any) -> str:
    return _slug(name, "species")


def _water_id(record: dict[str, Any], default_prefix: str = "water") -> str:
    return _slug(record.get("id") or record.get("name") or default_prefix, default_prefix)


def _gear_id(record: dict[str, Any], index: int) -> str:
    return _slug(record.get("id") or record.get("display_name") or f"gear-{index}", f"gear-{index}")


def _report_id(record: dict[str, Any], fallback: str) -> str:
    return _slug(record.get("id") or record.get("meta", {}).get("id") or fallback, fallback)


def _target_profile_id(record: dict[str, Any]) -> str:
    return _slug(record.get("id") or "current", "current")


def import_species(conn, source_path: Path) -> list[dict[str, Any]]:
    payload = _read_json(source_path, [])
    records = _source_items(payload)
    _clear_table(conn, "species")
    _clear_table(conn, "species_aliases")
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        sid = _species_id(item.get("id") or item.get("name") or f"species-{idx}")
        row = {
            "id": sid,
            "name": _text(item.get("name"), sid.replace("-", " ").title()),
            "group_name": _text(item.get("group"), ""),
            "tier": _text(item.get("tier"), ""),
            "enabled": 1 if item.get("enabled", True) else 0,
            "legacy_payload_json": canonical_dumps(item),
            "source_path": _safe_rel(source_path),
            "source_hash": file_sha256(source_path),
            "source_key": _stable_key(item, ("id", "name"), sid),
            "created_at": _text(item.get("created_at"), utc_now()),
            "updated_at": _text(item.get("updated_at"), utc_now()),
        }
        rows.append(row)
        _record_map(conn, domain="species", source_path=source_path, source_key=row["source_key"], normalized_id=sid, payload=item)
    _upsert_many(conn, "species", rows, ("id",))
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        sid = _species_id(item.get("id") or item.get("name") or f"species-{idx}")
        aliases = item.get("aliases") if isinstance(item.get("aliases"), list) else []
        for alias in aliases:
            conn.execute(
                "INSERT INTO species_aliases(species_id, alias, source_path) VALUES(?, ?, ?)",
                (sid, _text(alias), _safe_rel(source_path)),
            )
    _write_source_file(conn, domain="species", path=source_path, record_count=len(rows))
    _write_authority(conn, "species", source_path, file_sha256(source_path))
    conn.commit()
    return rows


def import_waters(conn, source_path: Path, *, clear_existing: bool = True) -> list[dict[str, Any]]:
    payload = _read_json(source_path, [])
    records = _source_items(payload)
    rows: list[dict[str, Any]] = []
    if clear_existing:
        _clear_table(conn, "waterbodies")
        _clear_table(conn, "waterbody_aliases")
        _clear_table(conn, "waterbody_species")
        _clear_table(conn, "waterbody_tags")
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        wid = _water_id(item, "water")
        species = item.get("species") if isinstance(item.get("species"), list) else []
        species_ids = item.get("species_ids") if isinstance(item.get("species_ids"), list) else []
        row = {
            "id": wid,
            "name": _text(item.get("name"), wid.replace("-", " ").title()),
            "water_type": _text(item.get("type"), ""),
            "city": _text(item.get("city"), ""),
            "county": _text(item.get("county"), ""),
            "state": _text(item.get("state"), ""),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
            "source_kind": "manual" if item.get("manual") else "json",
            "source_path": _safe_rel(source_path),
            "source_hash": file_sha256(source_path),
            "source_key": _stable_key(item, ("id", "name"), wid),
            "manual": 1 if item.get("manual") else 0,
            "favorite": 1 if item.get("favorite") else 0,
            "stocked_trout": 1 if item.get("stocked_trout") else 0,
            "catch_history_count": int(item.get("catch_history_count") or 0),
            "confidence": _text(item.get("confidence"), ""),
            "access_json": canonical_dumps(item.get("access", [])),
            "habitat_json": canonical_dumps(item.get("habitat", [])),
            "species_json": canonical_dumps(species),
            "species_ids_json": canonical_dumps(species_ids),
            "notes": _text(item.get("notes"), ""),
            "legacy_payload_json": canonical_dumps(item),
            "created_at": _text(item.get("created_at"), utc_now()),
            "updated_at": _text(item.get("updated_at"), utc_now()),
        }
        rows.append(row)
        _record_map(conn, domain="waters", source_path=source_path, source_key=row["source_key"], normalized_id=wid, payload=item)
    _upsert_many(conn, "waterbodies", rows, ("id",))
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        wid = _water_id(item, "water")
        for alias in { _text(item.get("name"), wid.replace("-", " ").title()), _text(item.get("city"), ""), _text(item.get("county"), "") }:
            if alias:
                conn.execute(
                    "INSERT INTO waterbody_aliases(waterbody_id, alias, source_path) VALUES(?, ?, ?)",
                    (wid, alias, _safe_rel(source_path)),
                )
        species = item.get("species") if isinstance(item.get("species"), list) else []
        for species_name in species:
            sid = _species_id(species_name)
            if conn.execute("SELECT 1 FROM species WHERE id = ?", (sid,)).fetchone():
                conn.execute(
                    "INSERT OR IGNORE INTO waterbody_species(waterbody_id, species_id, confidence, source_path) VALUES(?, ?, ?, ?)",
                    (wid, sid, _text(item.get("confidence"), ""), _safe_rel(source_path)),
                )
        for tag in item.get("habitat", []) if isinstance(item.get("habitat"), list) else []:
            conn.execute(
                "INSERT INTO waterbody_tags(waterbody_id, tag, source_path) VALUES(?, ?, ?)",
                (wid, _text(tag), _safe_rel(source_path)),
            )
    _write_source_file(conn, domain="waters", path=source_path, record_count=len(rows))
    _write_authority(conn, "waters", source_path, file_sha256(source_path))
    conn.commit()
    return rows


def import_target_profile(conn, source_path: Path) -> list[dict[str, Any]]:
    payload = _read_json(source_path, {})
    record = payload if isinstance(payload, dict) else {}
    profile_id = _target_profile_id(record)
    row = {
        "id": profile_id,
        "default_target_species": _text(record.get("default_target_species"), ""),
        "current_trip_target": _text(record.get("current_trip_target"), ""),
        "favorite_species_json": canonical_dumps(record.get("favorite_species", [])),
        "legacy_payload_json": canonical_dumps(record),
        "source_path": _safe_rel(source_path),
        "source_hash": file_sha256(source_path),
        "source_key": profile_id,
        "created_at": _text(record.get("created_at"), utc_now()),
        "updated_at": _text(record.get("updated_at"), utc_now()),
    }
    _clear_table(conn, "target_profiles")
    _clear_table(conn, "target_profile_species")
    _upsert_many(conn, "target_profiles", [row], ("id",))
    favorite_species = record.get("favorite_species") if isinstance(record.get("favorite_species"), list) else []
    for idx, species_name in enumerate(favorite_species):
        species_id = _species_id(species_name)
        if conn.execute("SELECT 1 FROM species WHERE id = ?", (species_id,)).fetchone():
            conn.execute(
                "INSERT INTO target_profile_species(target_profile_id, species_id, preference, source_path) VALUES(?, ?, ?, ?)",
                (profile_id, species_id, f"favorite-{idx + 1}", _safe_rel(source_path)),
            )
    _write_source_file(conn, domain="target_profile", path=source_path, record_count=1)
    _write_authority(conn, "target_profile", source_path, file_sha256(source_path))
    conn.commit()
    return [row]


def import_favorites(conn, source_path: Path) -> list[dict[str, Any]]:
    payload = _read_json(source_path, [])
    records = _source_items(payload)
    rows: list[dict[str, Any]] = []
    _clear_table(conn, "saved_locations")
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        lid = _slug(item.get("id") or item.get("name") or f"location-{idx}", f"location-{idx}")
        row = {
            "id": lid,
            "name": _text(item.get("name"), lid.replace("-", " ").title()),
            "zip": _text(item.get("zip"), ""),
            "city": _text(item.get("city"), ""),
            "county": _text(item.get("county"), ""),
            "state": _text(item.get("state"), ""),
            "notes": _text(item.get("notes"), ""),
            "legacy_payload_json": canonical_dumps(item),
            "source_path": _safe_rel(source_path),
            "source_hash": file_sha256(source_path),
            "source_key": _stable_key(item, ("id", "name", "zip"), lid),
            "created_at": _text(item.get("created_at"), utc_now()),
            "updated_at": _text(item.get("updated_at"), utc_now()),
        }
        rows.append(row)
        _record_map(conn, domain="favorites", source_path=source_path, source_key=row["source_key"], normalized_id=lid, payload=item)
    _upsert_many(conn, "saved_locations", rows, ("id",))
    _write_source_file(conn, domain="favorites", path=source_path, record_count=len(rows))
    _write_authority(conn, "favorites", source_path, file_sha256(source_path))
    conn.commit()
    return rows


def _gear_row(item: dict[str, Any], idx: int, source_path: Path) -> dict[str, Any]:
    gid = _gear_id(item, idx)
    return {
        "id": gid,
        "category": _text(item.get("category"), "misc"),
        "subtype": _text(item.get("subtype"), ""),
        "brand": _text(item.get("brand"), ""),
        "model": _text(item.get("model"), ""),
        "display_name": _text(item.get("display_name"), ""),
        "status": _text(item.get("status"), "owned"),
        "favorite": 1 if item.get("favorite") else 0,
        "retired_at": _text(item.get("retired_at"), ""),
        "notes": _text(item.get("notes"), ""),
        "source_kind": _text(item.get("source"), "json"),
        "source_name": _text(item.get("source_name"), ""),
        "source_url": _text(item.get("source_url"), ""),
        "provider": _text(item.get("provider"), ""),
        "provider_product_id": _text(item.get("provider_product_id"), ""),
        "confidence": _text(item.get("confidence"), ""),
        "quantity": int(item.get("quantity") or 1),
        "legacy_payload_json": canonical_dumps(item),
        "field_sources_json": canonical_dumps(item.get("field_sources", {})),
        "specifications_json": canonical_dumps(item.get("specifications", {})),
        "identifiers_json": canonical_dumps(item.get("identifiers", {})),
        "image_path": _text(item.get("image_path"), _text(item.get("image"), "")),
        "image_url": _text(item.get("image_url"), _text(item.get("image"), "")),
        "image_source": _text(item.get("image_source"), ""),
        "created_at": _text(item.get("created_at"), utc_now()),
        "updated_at": _text(item.get("updated_at"), utc_now()),
    }


def import_gear_inventory(conn, source_path: Path, settings_path: Path | None = None, cache_path: Path | None = None) -> list[dict[str, Any]]:
    payload = _read_json(source_path, {})
    records = _source_items(payload.get("items") if isinstance(payload, dict) else payload)
    rows = [_gear_row(item, idx, source_path) for idx, item in enumerate(records) if isinstance(item, dict)]

    _clear_table(conn, "gear_items")
    _clear_table(conn, "rod_specs")
    _clear_table(conn, "reel_specs")
    _clear_table(conn, "line_specs")
    _clear_table(conn, "lure_specs")
    _clear_table(conn, "terminal_tackle_specs")
    _clear_table(conn, "gear_item_tags")
    _clear_table(conn, "gear_images")
    _clear_table(conn, "gear_maintenance")
    _clear_table(conn, "gear_usage")
    _clear_table(conn, "gear_setups")
    _clear_table(conn, "gear_setup_items")
    _clear_table(conn, "product_sources")

    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        row = rows[idx]
        _upsert_many(conn, "gear_items", [row], ("id",))
        _record_map(conn, domain="gear_inventory", source_path=source_path, source_key=row["id"], normalized_id=row["id"], payload=item)
        specs_json = item if isinstance(item, dict) else {}
        category = row["category"].lower()
        if category == "rod":
            conn.execute(
                """
                INSERT OR REPLACE INTO rod_specs(
                    gear_item_id, length_ft, length_label, power, action, pieces,
                    lure_weight_min_oz, lure_weight_max_oz, line_rating_min_lb, line_rating_max_lb,
                    technique_tags_json, species_tags_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    item.get("length_ft"),
                    _text(item.get("length_label"), ""),
                    _text(item.get("power"), ""),
                    _text(item.get("action"), ""),
                    item.get("pieces"),
                    item.get("lure_weight_min_oz"),
                    item.get("lure_weight_max_oz"),
                    item.get("line_rating_min_lb"),
                    item.get("line_rating_max_lb"),
                    canonical_dumps(item.get("technique_tags", [])),
                    canonical_dumps(item.get("species_tags", [])),
                ),
            )
        elif category == "reel":
            conn.execute(
                """
                INSERT OR REPLACE INTO reel_specs(
                    gear_item_id, reel_type, gear_ratio, max_drag_lb, line_capacity, weight_oz, handedness
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    _text(item.get("reel_type"), ""),
                    item.get("gear_ratio"),
                    item.get("max_drag_lb"),
                    _text(item.get("line_capacity"), ""),
                    item.get("weight_oz"),
                    _text(item.get("handedness"), ""),
                ),
            )
        elif category == "line":
            conn.execute(
                """
                INSERT OR REPLACE INTO line_specs(
                    gear_item_id, line_type, strength_lb, diameter_equivalent, color, length_yd
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    _text(item.get("line_type"), ""),
                    item.get("strength_lb"),
                    _text(item.get("diameter_equivalent"), ""),
                    _text(item.get("color"), ""),
                    item.get("length_yd"),
                ),
            )
        elif category == "lure":
            conn.execute(
                """
                INSERT OR REPLACE INTO lure_specs(
                    gear_item_id, lure_type, color, weight_oz, hook_size, depth_min_ft, depth_max_ft, quantity,
                    technique_tags_json, species_tags_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    _text(item.get("lure_type"), ""),
                    _text(item.get("color"), ""),
                    item.get("weight_oz"),
                    _text(item.get("hook_size"), ""),
                    item.get("depth_min_ft"),
                    item.get("depth_max_ft"),
                    item.get("quantity"),
                    canonical_dumps(item.get("technique_tags", [])),
                    canonical_dumps(item.get("species_tags", [])),
                ),
            )
        elif category == "terminal":
            conn.execute(
                """
                INSERT OR REPLACE INTO terminal_tackle_specs(
                    gear_item_id, subtype, size, weight_oz, hook_size, quantity
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    _text(item.get("subtype"), ""),
                    _text(item.get("size"), ""),
                    item.get("weight_oz"),
                    _text(item.get("hook_size"), ""),
                    item.get("quantity"),
                ),
            )
        tags = []
        for key in ("technique_tags", "species_tags"):
            tags.extend(item.get(key, []) if isinstance(item.get(key), list) else [])
        for tag in tags:
            conn.execute(
                "INSERT INTO gear_item_tags(gear_item_id, tag, source_path) VALUES(?, ?, ?)",
                (row["id"], _text(tag), _safe_rel(source_path)),
            )
        if _text(item.get("image"), "") or _text(item.get("image_url"), ""):
            conn.execute(
                "INSERT INTO gear_images(gear_item_id, image_path, image_url, image_source, locally_cached, retrieved_at) VALUES(?, ?, ?, ?, ?, ?)",
                (
                    row["id"],
                    _text(item.get("image_path"), _text(item.get("image"), "")),
                    _text(item.get("image_url"), _text(item.get("image"), "")),
                    _text(item.get("image_source"), ""),
                    1 if _text(item.get("image_path"), "") else 0,
                    _text(item.get("retrieved_at"), utc_now()),
                ),
            )
        if _text(item.get("notes"), ""):
            conn.execute(
                "INSERT INTO gear_maintenance(gear_item_id, maintenance_type, due_at, last_done_at, notes) VALUES(?, ?, ?, ?, ?)",
                (row["id"], "note", None, None, _text(item.get("notes"), "")),
            )
        if _text(item.get("provider"), "") or _text(item.get("source_url"), ""):
            conn.execute(
                """
                INSERT INTO product_sources(
                    gear_item_id, provider, source_name, source_url, provider_product_id, retrieved_at, confidence, price, availability, raw_provider_data_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    _text(item.get("provider"), ""),
                    _text(item.get("source_name"), ""),
                    _text(item.get("source_url"), ""),
                    _text(item.get("provider_product_id"), ""),
                    _text(item.get("retrieved_at"), utc_now()),
                    _text(item.get("confidence"), ""),
                    item.get("price"),
                    _text(item.get("availability"), ""),
                    canonical_dumps(item),
                ),
            )

    _write_source_file(conn, domain="gear_inventory", path=source_path, record_count=len(rows))
    _write_authority(conn, "gear_inventory", source_path, file_sha256(source_path))

    if settings_path and settings_path.exists():
        settings = _read_json(settings_path, {})
        _write_source_file(conn, domain="gear_settings", path=settings_path, record_count=1)
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)",
            ("gear_settings", canonical_dumps(settings), utc_now()),
        )
        _write_authority(conn, "gear_settings", settings_path, file_sha256(settings_path))

    if cache_path and cache_path.exists():
        cache = _read_json(cache_path, {})
        products = cache.get("products") if isinstance(cache, dict) and isinstance(cache.get("products"), list) else []
        _write_source_file(conn, domain="gear_catalog_cache", path=cache_path, record_count=len(products))
        _write_authority(conn, "gear_catalog_cache", cache_path, file_sha256(cache_path))

    conn.commit()
    return rows


def import_catches(conn, source_path: Path) -> list[dict[str, Any]]:
    payload = _read_json(source_path, [])
    records = _source_items(payload)
    rows: list[dict[str, Any]] = []
    gear_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    _clear_table(conn, "catches")
    _clear_table(conn, "catch_gear")
    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        cid = _slug(item.get("id") or item.get("timestamp") or f"catch-{idx}", f"catch-{idx}")
        gear_refs = item.get("gear_refs") if isinstance(item.get("gear_refs"), dict) else {}
        gear_labels = item.get("gear_labels") if isinstance(item.get("gear_labels"), dict) else {}
        row = {
            "id": cid,
            "timestamp": _text(item.get("timestamp"), ""),
            "species": _text(item.get("species"), ""),
            "waterbody": _text(item.get("waterbody"), ""),
            "lure": _text(item.get("lure"), ""),
            "rig": _text(item.get("rig"), ""),
            "notes": _text(item.get("notes"), ""),
            "zip": _text(item.get("zip"), ""),
            "gear_refs_json": canonical_dumps(gear_refs),
            "gear_labels_json": canonical_dumps(gear_labels),
            "legacy_payload_json": canonical_dumps(item),
            "source_path": _safe_rel(source_path),
            "source_hash": file_sha256(source_path),
            "source_key": _stable_key(item, ("id", "timestamp", "species"), cid),
            "created_at": _text(item.get("created_at"), utc_now()),
            "updated_at": _text(item.get("updated_at"), utc_now()),
        }
        rows.append(row)
        _record_map(conn, domain="catches", source_path=source_path, source_key=row["source_key"], normalized_id=cid, payload=item)
        for role, ref in gear_refs.items():
            gear_rows.append((cid, {"role": role, "ref": _text(ref, "")}, gear_labels))
    _upsert_many(conn, "catches", rows, ("id",))
    for cid, ref_info, gear_labels in gear_rows:
        gear_id = ref_info["ref"]
        if gear_id and not conn.execute("SELECT 1 FROM gear_items WHERE id = ?", (gear_id,)).fetchone():
            gear_id = ""
        conn.execute(
            "INSERT INTO catch_gear(catch_id, gear_item_id, gear_role, legacy_label) VALUES(?, ?, ?, ?)",
            (cid, gear_id or None, _text(ref_info["role"], ""), _text(gear_labels.get(ref_info["role"]), "")),
        )
    _write_source_file(conn, domain="catches", path=source_path, record_count=len(rows))
    _write_authority(conn, "catches", source_path, file_sha256(source_path))
    conn.commit()
    return rows


def import_reports(conn, reports_index_path: Path, reports_dir: Path | None = None) -> list[dict[str, Any]]:
    payload = _read_json(reports_index_path, [])
    records = _source_items(payload)
    rows: list[dict[str, Any]] = []
    _clear_table(conn, "trips")
    _clear_table(conn, "forecast_snapshots")
    _clear_table(conn, "forecast_days")
    _clear_table(conn, "trip_reports")
    _clear_table(conn, "trip_gear")
    _clear_table(conn, "trip_outcomes")
    _clear_table(conn, "intelligence_snapshots")
    _clear_table(conn, "recommendations")
    _clear_table(conn, "recommendation_explanations")
    _clear_table(conn, "recommendation_feedback")

    for idx, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        rid = _report_id(item, f"report-{idx}")
        meta = item
        report_json: dict[str, Any] = {}
        report_path = None
        if reports_dir:
            candidate = reports_dir / f"{rid}.json"
            if candidate.exists():
                report_path = candidate
                report_json = _read_json(candidate, {})
        payload_obj = report_json if isinstance(report_json, dict) and report_json else item
        payload_meta = payload_obj.get("meta", {}) if isinstance(payload_obj, dict) else {}
        payload_payload = payload_obj.get("payload", {}) if isinstance(payload_obj, dict) else {}
        payload_summary = payload_obj.get("summary", {}) if isinstance(payload_obj, dict) else {}
        selected_forecast_date = _text(item.get("selected_forecast_date") or payload_meta.get("selected_forecast_date") or payload_payload.get("selected_forecast_date"), "")
        selected_label = _text(item.get("selected_forecast_label") or payload_meta.get("selected_forecast_label") or payload_payload.get("selected_forecast_label"), "")
        forecast_index = item.get("forecast_day_index")
        title = _text(item.get("title") or payload_meta.get("title") or payload_payload.get("title"), "Trip Report")
        row = {
            "id": rid,
            "trip_id": rid,
            "report_title": title,
            "zip": _text(item.get("zip") or payload_summary.get("zip") or payload_payload.get("zip"), ""),
            "selected_forecast_date": selected_forecast_date,
            "selected_forecast_label": selected_label,
            "forecast_day_index": forecast_index if forecast_index is not None else None,
            "json_path": _safe_rel((reports_dir / f"{rid}.json") if reports_dir else None),
            "html_path": _safe_rel((reports_dir / f"{rid}.html") if reports_dir else None),
            "view_url": _text(item.get("view_url"), f"/api/reports/view/{rid}"),
            "legacy_payload_json": canonical_dumps(item),
            "created_at": _text(item.get("created") or payload_meta.get("created") or payload_payload.get("saved_at"), utc_now()),
            "updated_at": utc_now(),
        }
        rows.append(row)
        _record_map(conn, domain="reports", source_path=reports_index_path, source_key=rid, normalized_id=rid, payload=item)
        trip_row = {
            "id": rid,
            "title": title,
            "zip": row["zip"],
            "target_species": _text(item.get("target_species") or payload_summary.get("target_species") or payload_payload.get("target_species"), ""),
            "focus_waterbody_id": _text(item.get("focus_waterbody_id") or payload_summary.get("focus_waterbody_id") or payload_payload.get("focus_waterbody_id"), ""),
            "selected_forecast_date": selected_forecast_date,
            "selected_forecast_label": selected_label,
            "forecast_day_index": forecast_index if forecast_index is not None else None,
            "started_at": _text(item.get("created") or payload_meta.get("created") or payload_payload.get("saved_at"), utc_now()),
            "updated_at": utc_now(),
            "legacy_payload_json": canonical_dumps({"report": item, "payload": payload_obj}),
            "source_path": _safe_rel(reports_index_path),
            "source_hash": file_sha256(reports_index_path),
            "source_key": rid,
        }
        _upsert_many(conn, "trips", [trip_row], ("id",))
        _upsert_many(conn, "trip_reports", [row], ("id",))
        intel = payload_payload.get("intel") if isinstance(payload_payload.get("intel"), dict) else {}
        forecast = intel.get("forecast") if isinstance(intel, dict) and isinstance(intel.get("forecast"), list) else []
        if forecast:
            snapshot_id = f"{rid}-forecast"
            conn.execute(
                """
                INSERT INTO forecast_snapshots(id, trip_id, source_path, source_hash, forecast_date, pretty_date, summary_json, legacy_payload_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    rid,
                    _safe_rel(reports_index_path),
                    file_sha256(reports_index_path),
                    selected_forecast_date,
                    selected_label,
                    canonical_dumps(forecast),
                    canonical_dumps(forecast),
                    utc_now(),
                ),
            )
            for day in forecast:
                if not isinstance(day, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO forecast_days(
                        trip_id, forecast_snapshot_id, forecast_date, rating, score, high_temp, low_temp, wind_mph, cloud_cover, legacy_payload_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rid,
                        snapshot_id,
                        _text(day.get("date"), ""),
                        _text(day.get("rating"), _text(day.get("forecast_rating"), "")),
                        day.get("score"),
                        day.get("high_temp") or day.get("high"),
                        day.get("low_temp") or day.get("low"),
                        day.get("wind_mph") or day.get("wind"),
                        day.get("cloud_cover"),
                        canonical_dumps(day),
                    ),
                )
        intelligence_payload = intel if isinstance(intel, dict) and intel else {}
        snapshot_id = None
        if intelligence_payload:
            snapshot_id = f"{rid}-intel"
            conn.execute(
                """
                INSERT INTO intelligence_snapshots(
                    id, trip_id, report_id, zip, target_species, source_path, source_hash, summary_json, legacy_payload_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    rid,
                    rid,
                    row["zip"],
                    _text(item.get("target_species") or payload_summary.get("target_species") or payload_payload.get("target_species"), ""),
                    _safe_rel((reports_dir / f"{rid}.json") if reports_dir else reports_index_path),
                    file_sha256((reports_dir / f"{rid}.json") if reports_dir and (reports_dir / f"{rid}.json").exists() else reports_index_path),
                    canonical_dumps(intelligence_payload.get("summary") or intelligence_payload),
                    canonical_dumps(intelligence_payload),
                    utc_now(),
                ),
            )
        best_bet = payload_summary.get("best_bet") if isinstance(payload_summary.get("best_bet"), dict) else {}
        rec = intel.get("best_bet") if isinstance(intel, dict) and isinstance(intel.get("best_bet"), dict) else {}
        recommendation_source = best_bet or rec
        if recommendation_source:
            rec_id = f"{rid}-best-bet"
            conn.execute(
                """
                INSERT INTO recommendations(
                    id, intelligence_snapshot_id, target_species, lure_type, lure_label, fit_label, score, confidence, reasons_json, caution_json, legacy_payload_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    snapshot_id,
                    _text(recommendation_source.get("species"), ""),
                    _text(recommendation_source.get("lure_type"), ""),
                    _text(recommendation_source.get("lure_name"), ""),
                    _text(recommendation_source.get("fit_label"), ""),
                    recommendation_source.get("species_score"),
                    _text(recommendation_source.get("confidence"), ""),
                    canonical_dumps(recommendation_source.get("reasons", [])),
                    canonical_dumps(recommendation_source.get("caution", [])),
                    canonical_dumps(recommendation_source),
                    utc_now(),
                    utc_now(),
                ),
            )
            for reason in recommendation_source.get("reasons", []) if isinstance(recommendation_source.get("reasons"), list) else []:
                conn.execute(
                    "INSERT INTO recommendation_explanations(recommendation_id, explanation_type, body, source_path) VALUES(?, ?, ?, ?)",
                    (rec_id, "reason", _text(reason), _safe_rel((reports_dir / f"{rid}.json") if reports_dir else reports_index_path)),
                )

    _upsert_many(conn, "trip_reports", rows, ("id",))
    _write_source_file(conn, domain="reports_index", path=reports_index_path, record_count=len(rows))
    _write_authority(conn, "reports_index", reports_index_path, file_sha256(reports_index_path))
    if reports_dir and reports_dir.exists():
        _write_source_file(conn, domain="reports", path=reports_dir, record_count=len(list(reports_dir.glob("*.json"))), generated_only=True, source_of_truth="generated")
        _write_authority(conn, "reports", reports_index_path, file_sha256(reports_index_path))
        for path in sorted(reports_dir.glob("*.html")):
            _write_source_file(conn, domain="reports_html", path=path, record_count=1, generated_only=True, source_of_truth="generated")
    conn.commit()
    return rows


def import_domain(conn, domain: str) -> list[dict[str, Any]]:
    domain = _text(domain, "").lower()
    if domain == "species":
        return import_species(conn, DATA_DIR / "species_profiles_v43.json")
    if domain == "waters":
        rows = import_waters(conn, DATA_DIR / "illinois_waters.json", clear_existing=True)
        rows.extend(import_waters(conn, DATA_DIR / "manual_waters.json", clear_existing=False))
        return rows
    if domain == "manual_waters":
        return import_waters(conn, DATA_DIR / "manual_waters.json", clear_existing=False)
    if domain == "target_profile":
        return import_target_profile(conn, DATA_DIR / "target_profile.json")
    if domain == "favorites":
        return import_favorites(conn, DATA_DIR / "favorites.json")
    if domain == "gear_inventory":
        return import_gear_inventory(conn, DATA_DIR / "gear_inventory.json", DATA_DIR / "gear_settings.json", DATA_DIR / "gear_catalog_cache.json")
    if domain == "catches":
        return import_catches(conn, DATA_DIR / "catches.json")
    if domain == "reports":
        return import_reports(conn, DATA_DIR / "reports_index.json", REPORTS_DIR)
    if domain == "reports_index":
        return import_reports(conn, DATA_DIR / "reports_index.json", REPORTS_DIR)
    raise ValueError(f"Unknown domain: {domain}")


def import_all(conn) -> dict[str, int]:
    summary = {}
    for domain in ("species", "waters", "target_profile", "favorites", "gear_inventory", "catches", "reports"):
        try:
            rows = import_domain(conn, domain)
            summary[domain] = len(rows)
        except Exception:
            summary[domain] = -1
    return summary


def export_domain_rows(conn, domain: str) -> list[dict[str, Any]]:
    domain = _text(domain, "").lower()
    if domain == "species":
        return [dict(row) for row in conn.execute("SELECT * FROM species ORDER BY id")]
    if domain in {"waters", "manual_waters"}:
        return [dict(row) for row in conn.execute("SELECT * FROM waterbodies ORDER BY id")]
    if domain == "target_profile":
        return [dict(row) for row in conn.execute("SELECT * FROM target_profiles ORDER BY id")]
    if domain == "favorites":
        return [dict(row) for row in conn.execute("SELECT * FROM saved_locations ORDER BY id")]
    if domain == "gear_inventory":
        return [dict(row) for row in conn.execute("SELECT * FROM gear_items ORDER BY id")]
    if domain == "catches":
        return [dict(row) for row in conn.execute("SELECT * FROM catches ORDER BY id")]
    if domain in {"reports", "reports_index"}:
        return [dict(row) for row in conn.execute("SELECT * FROM trip_reports ORDER BY id")]
    raise ValueError(f"Unknown domain: {domain}")


def source_file_summaries() -> list[dict[str, Any]]:
    files = [
        ("species", DATA_DIR / "species_profiles_v43.json", False),
        ("species_settings", DATA_DIR / "species_settings_v431.json", False),
        ("waters", DATA_DIR / "illinois_waters.json", False),
        ("manual_waters", DATA_DIR / "manual_waters.json", False),
        ("favorites", DATA_DIR / "favorites.json", False),
        ("target_profile", DATA_DIR / "target_profile.json", False),
        ("gear_inventory", DATA_DIR / "gear_inventory.json", False),
        ("gear_settings", DATA_DIR / "gear_settings.json", False),
        ("gear_catalog_cache", DATA_DIR / "gear_catalog_cache.json", False),
        ("catches", DATA_DIR / "catches.json", False),
        ("reports_index", DATA_DIR / "reports_index.json", False),
    ]
    summaries = []
    for logical_name, path, generated_only in files:
        exists, payload, error = _read_json_status(path, [] if path.suffix == ".json" else {})
        summaries.append(
            {
                "domain": logical_name,
                "path": _safe_rel(path),
                "exists": exists,
                "valid_json": error in (None, "empty"),
                "error": error if error not in (None, "empty", "missing") else None,
                "generated_only": generated_only,
                "record_count": len(_source_items(payload)),
                "sha256": file_sha256(path),
            }
        )
    for path in sorted(REPORTS_DIR.glob("*.json")):
        summaries.append(
            {
                "domain": "reports",
                "path": _safe_rel(path),
                "exists": True,
                "generated_only": True,
                "record_count": 1,
                "sha256": file_sha256(path),
            }
        )
    for path in sorted(REPORTS_DIR.glob("*.html")):
        summaries.append(
            {
                "domain": "reports_html",
                "path": _safe_rel(path),
                "exists": True,
                "generated_only": True,
                "record_count": 1,
                "sha256": file_sha256(path),
            }
        )
    return summaries
