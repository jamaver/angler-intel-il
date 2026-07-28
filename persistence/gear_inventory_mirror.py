"""JSON-first normalized SQLite mirroring for My Tackle Locker."""
from __future__ import annotations

import re
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
SPEC_TABLES = ("rod_specs", "reel_specs", "line_specs", "lure_specs", "terminal_tackle_specs")
INVENTORY_ENVELOPE_KEY = "v7.gear_inventory.envelope"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, fallback: str = "") -> str:
    value = " ".join(str(value or "").split()).strip()
    return value or fallback


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _text(value).lower()).strip("-") or "gear"


def _source_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _items(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    values = inventory.get("items") if isinstance(inventory, dict) else []
    if not isinstance(values, list):
        raise ValueError("Gear inventory items must be a list")
    items = [dict(item) for item in values if isinstance(item, dict)]
    ids = [_text(item.get("id")) for item in items]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Gear inventory contains missing or duplicate item IDs")
    return items


def gear_inventory_operation_id(inventory: dict[str, Any], usage_event: dict[str, Any] | None = None) -> str:
    return f"gear-inventory-{record_hash({'inventory': inventory, 'usage_event': usage_event or {}})}"


def _write_gear_item(conn: sqlite3.Connection, item: dict[str, Any], source_label: str) -> None:
    item_id = _text(item.get("id"))
    category = _text(item.get("category"), "misc").lower()
    conn.execute(
        """
        INSERT INTO gear_items(
            id, category, subtype, brand, model, display_name, status, favorite,
            retired_at, notes, source_kind, source_name, source_url, provider,
            provider_product_id, confidence, quantity, legacy_payload_json,
            field_sources_json, specifications_json, identifiers_json, image_path,
            image_url, image_source, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            category=excluded.category, subtype=excluded.subtype, brand=excluded.brand,
            model=excluded.model, display_name=excluded.display_name, status=excluded.status,
            favorite=excluded.favorite, retired_at=excluded.retired_at, notes=excluded.notes,
            source_kind=excluded.source_kind, source_name=excluded.source_name,
            source_url=excluded.source_url, provider=excluded.provider,
            provider_product_id=excluded.provider_product_id, confidence=excluded.confidence,
            quantity=excluded.quantity, legacy_payload_json=excluded.legacy_payload_json,
            field_sources_json=excluded.field_sources_json, specifications_json=excluded.specifications_json,
            identifiers_json=excluded.identifiers_json, image_path=excluded.image_path,
            image_url=excluded.image_url, image_source=excluded.image_source,
            updated_at=excluded.updated_at
        """,
        (
            item_id, category, _text(item.get("subtype")), _text(item.get("brand")),
            _text(item.get("model")), _text(item.get("display_name")),
            _text(item.get("status"), "owned"), 1 if item.get("favorite") else 0,
            _text(item.get("retired_at")), _text(item.get("notes")),
            _text(item.get("source"), "manual"), _text(item.get("source_name")),
            _text(item.get("source_url")), _text(item.get("provider")),
            _text(item.get("provider_product_id")), _text(item.get("confidence")),
            int(item.get("quantity") or 1), canonical_dumps(item),
            canonical_dumps(item.get("field_sources", {})), canonical_dumps(item.get("specifications", {})),
            canonical_dumps(item.get("identifiers", {})), _text(item.get("image_path"), _text(item.get("image"))),
            _text(item.get("image_url"), _text(item.get("image"))), _text(item.get("image_source")),
            _text(item.get("created_at"), _utc_now()), _text(item.get("updated_at"), _utc_now()),
        ),
    )

    if category == "rod":
        conn.execute(
            "INSERT INTO rod_specs VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, item.get("length_ft"), _text(item.get("length_label")), _text(item.get("power")),
             _text(item.get("action")), item.get("pieces"), item.get("lure_weight_min_oz"),
             item.get("lure_weight_max_oz"), item.get("line_rating_min_lb"), item.get("line_rating_max_lb"),
             canonical_dumps(item.get("technique_tags", [])), canonical_dumps(item.get("species_tags", []))),
        )
    elif category == "reel":
        conn.execute(
            "INSERT INTO reel_specs VALUES(?, ?, ?, ?, ?, ?, ?)",
            (item_id, _text(item.get("reel_type")), item.get("gear_ratio"), item.get("max_drag_lb"),
             _text(item.get("line_capacity")), item.get("weight_oz"), _text(item.get("handedness"))),
        )
    elif category == "line":
        conn.execute(
            "INSERT INTO line_specs VALUES(?, ?, ?, ?, ?, ?)",
            (item_id, _text(item.get("line_type")), item.get("strength_lb"),
             _text(item.get("diameter_equivalent")), _text(item.get("color")), item.get("length_yd")),
        )
    elif category == "lure":
        conn.execute(
            "INSERT INTO lure_specs VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, _text(item.get("lure_type")), _text(item.get("color")), item.get("weight_oz"),
             _text(item.get("hook_size")), item.get("depth_min_ft"), item.get("depth_max_ft"),
             item.get("quantity"), canonical_dumps(item.get("technique_tags", [])),
             canonical_dumps(item.get("species_tags", []))),
        )
    elif category == "terminal":
        conn.execute(
            "INSERT INTO terminal_tackle_specs VALUES(?, ?, ?, ?, ?, ?)",
            (item_id, _text(item.get("subtype")), _text(item.get("size")), item.get("weight_oz"),
             _text(item.get("hook_size")), item.get("quantity")),
        )

    for tag_key in ("technique_tags", "species_tags"):
        tags = item.get(tag_key) if isinstance(item.get(tag_key), list) else []
        for tag in tags:
            if _text(tag):
                conn.execute("INSERT INTO gear_item_tags(gear_item_id, tag, source_path) VALUES(?, ?, ?)", (item_id, _text(tag), source_label))

    if _text(item.get("image")) or _text(item.get("image_url")):
        image_path = _text(item.get("image_path"), _text(item.get("image")))
        conn.execute(
            "INSERT INTO gear_images(gear_item_id, image_path, image_url, image_source, locally_cached, retrieved_at) VALUES(?, ?, ?, ?, ?, ?)",
            (item_id, image_path, _text(item.get("image_url"), _text(item.get("image"))),
             _text(item.get("image_source")), 1 if image_path and not image_path.startswith("http") else 0,
             _text(item.get("retrieved_at"))),
        )

    maintenance = {
        "maintenance_interval_days": item.get("maintenance_interval_days") or 0,
        "maintenance_notes": _text(item.get("maintenance_notes")),
        "retired_reason": _text(item.get("retired_reason")),
    }
    if any(maintenance.values()) or _text(item.get("last_cleaned")):
        conn.execute(
            "INSERT INTO gear_maintenance(gear_item_id, maintenance_type, due_at, last_done_at, notes) VALUES(?, 'inventory_state', NULL, ?, ?)",
            (item_id, _text(item.get("last_cleaned")), canonical_dumps(maintenance)),
        )

    if _text(item.get("provider")) or _text(item.get("source_url")):
        conn.execute(
            """
            INSERT INTO product_sources(
                gear_item_id, provider, source_name, source_url, provider_product_id,
                retrieved_at, confidence, price, availability, raw_provider_data_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (item_id, _text(item.get("provider")), _text(item.get("source_name")),
             _text(item.get("source_url")), _text(item.get("provider_product_id")),
             _text(item.get("retrieved_at")), _text(item.get("confidence")), item.get("price"),
             _text(item.get("availability")), canonical_dumps(item)),
        )


def _write_inventory(
    conn: sqlite3.Connection,
    inventory: dict[str, Any],
    source_path: Path,
    usage_event: dict[str, Any] | None,
    *,
    authority: str = "json",
) -> None:
    authority_row = conn.execute(
        "SELECT authority FROM data_authority WHERE domain = 'gear_inventory'"
    ).fetchone()
    if authority_row and authority_row["authority"] == "sqlite" and authority != "sqlite":
        raise RuntimeError(
            "gear_inventory is SQLite-authoritative; JSON-to-SQLite mirroring is disabled."
        )
    items = _items(inventory)
    source_hash = record_hash(inventory) if authority == "sqlite" else file_sha256(source_path)
    source_label = _source_label(source_path)
    item_ids = {_text(item.get("id")) for item in items}

    if item_ids:
        placeholders = ", ".join("?" for _ in item_ids)
        conn.execute(f"DELETE FROM gear_items WHERE id NOT IN ({placeholders})", tuple(sorted(item_ids)))
        conn.execute(
            f"DELETE FROM legacy_record_map WHERE domain = 'gear_inventory' AND source_path = ? AND source_key NOT IN ({placeholders})",
            (source_label, *sorted(item_ids)),
        )
    else:
        conn.execute("DELETE FROM gear_items")
        conn.execute("DELETE FROM legacy_record_map WHERE domain = 'gear_inventory' AND source_path = ?", (source_label,))
    for table in SPEC_TABLES + ("gear_item_tags", "gear_images", "gear_maintenance", "product_sources"):
        conn.execute(f"DELETE FROM {table}")

    for item in items:
        _write_gear_item(conn, item, source_label)
        item_id = _text(item.get("id"))
        conn.execute(
            """
            INSERT INTO legacy_record_map(
                domain, source_path, source_key, normalized_id, payload_hash, source_hash,
                status, notes, created_at
            ) VALUES('gear_inventory', ?, ?, ?, ?, ?, 'mapped', NULL, ?)
            ON CONFLICT(domain, source_path, source_key) DO UPDATE SET
                normalized_id=excluded.normalized_id, payload_hash=excluded.payload_hash,
                source_hash=excluded.source_hash, status='mapped', notes=NULL
            """,
            (source_label, item_id, item_id, record_hash(item), source_hash, _utc_now()),
        )

    if usage_event:
        gear_item_id = _text(usage_event.get("gear_item_id"))
        if gear_item_id in item_ids:
            conn.execute(
                "INSERT INTO gear_usage(gear_item_id, trip_id, catch_id, used_at, notes) VALUES(?, NULL, NULL, ?, ?)",
                (gear_item_id, _text(usage_event.get("used_at"), _utc_now()), canonical_dumps(usage_event)),
            )

    now = _utc_now()
    conn.execute(
        """
        INSERT INTO source_files(domain, logical_name, path, file_hash, record_count, source_of_truth, generated_only, last_seen_at, last_imported_at)
        VALUES('gear_inventory', 'gear_inventory', ?, ?, ?, 'json', 0, ?, ?)
        ON CONFLICT(domain, path) DO UPDATE SET
            file_hash=excluded.file_hash, record_count=excluded.record_count, source_of_truth='json',
            generated_only=0, last_seen_at=excluded.last_seen_at, last_imported_at=excluded.last_imported_at
        """,
        (source_label, source_hash, len(items), now, now),
    )
    conn.execute(
        """
        INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
        VALUES('gear_inventory', ?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            authority=excluded.authority, source_path=excluded.source_path, source_hash=excluded.source_hash,
            note=excluded.note, updated_at=excluded.updated_at
        """,
        (
            authority,
            source_label,
            source_hash,
            "SQLite is authoritative; JSON is a compatibility export."
            if authority == "sqlite"
            else "JSON remains authoritative during V7.1 gear mirroring.",
            now,
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)",
        (INVENTORY_ENVELOPE_KEY, canonical_dumps(inventory), now),
    )


def mirror_gear_inventory(
    inventory: dict[str, Any],
    source_path: str | Path,
    *,
    usage_event: dict[str, Any] | None = None,
    db_path: str | Path = DEFAULT_DB,
    force: bool = False,
) -> MirrorResult:
    """Mirror an already-saved JSON inventory without changing its authority."""
    path = Path(source_path)
    inventory_copy = dict(inventory)
    event_copy = dict(usage_event) if isinstance(usage_event, dict) else None
    base_operation_id = gear_inventory_operation_id(inventory_copy, event_copy)
    return mirror_after_json_write(
        "gear_inventory",
        lambda conn: _write_inventory(conn, inventory_copy, path, event_copy),
        operation_id=f"{base_operation_id}-reconcile-{uuid.uuid4().hex}" if force else base_operation_id,
        db_path=db_path,
        details={
            "source_path": _source_label(path),
            "inventory_hash": record_hash(inventory_copy),
            "item_count": len(_items(inventory_copy)),
            "usage_event": bool(event_copy),
        },
    )


def compare_gear_inventory(inventory: dict[str, Any], *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Read-only full-document drift comparison for authoritative gear items."""
    expected_items = _items(inventory)
    expected = {_text(item.get("id")): record_hash(item) for item in expected_items}
    result: dict[str, Any] = {"status": "missing_in_sqlite", "differences": []}
    database = Path(db_path)
    if not database.exists():
        result["differences"].append("SQLite database is unavailable.")
        return result
    try:
        with connect(database, read_only=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT id, legacy_payload_json FROM gear_items")]
            actual = {str(row["id"]): record_hash(json.loads(row["legacy_payload_json"])) for row in rows}
            if set(expected) != set(actual):
                result["differences"].append("item_ids")
            for item_id in sorted(set(expected).intersection(actual)):
                if expected[item_id] != actual[item_id]:
                    result["differences"].append(f"item:{item_id}")
            result["status"] = "exact" if not result["differences"] else "changed"
            return result
    except Exception as exc:
        result["status"] = "invalid_source"
        result["differences"].append(str(exc))
        return result
