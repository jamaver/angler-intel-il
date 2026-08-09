from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .connection import connect

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"


@dataclass(slots=True)
class ValidationSummary:
    ok: bool
    status: str
    db_path: str
    source_manifest_hash: str | None
    counts: dict[str, int]
    totals: dict[str, int]
    integrity_check: str | None
    foreign_key_check: list[dict[str, Any]]
    quick_check: str | None
    diffs: list[dict[str, Any]]
    warnings: list[str]


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


def _slug(value: Any, fallback: str = "item") -> str:
    text = " ".join(str(value or "").split()).strip().lower()
    text = "".join(ch if ch.isalnum() else "-" for ch in text)
    text = "-".join(part for part in text.split("-") if part)
    return text or fallback


def _text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _source_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _hash_payload(value: Any) -> str:
    return record_hash(value)


def _source_map(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in records:
        key = _text(item.get("id"), "")
        if not key:
            key = _slug(item.get("name") or item.get("title") or item.get("zip") or item.get("timestamp"), "item")
        mapping[key] = item
    return mapping


def _sqlite_map(rows: list[sqlite3.Row | dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        key = _text(item.get("id"), "")
        if not key:
            continue
        payload = item.get("legacy_payload_json") or item.get("payload_json") or item.get("summary_json")
        mapping[key] = {
            "row": item,
            "payload_hash": _hash_payload(json.loads(payload)) if isinstance(payload, str) and payload.strip() else "",
        }
    return mapping


def _source_payload_hash(item: dict[str, Any]) -> str:
    payload = item.get("legacy_payload_json")
    if isinstance(payload, str) and payload.strip():
        try:
            return _hash_payload(json.loads(payload))
        except Exception:
            return _hash_payload(item)
    return _hash_payload(item)


def _compare_records(domain: str, source_rows: list[dict[str, Any]], sqlite_rows: list[sqlite3.Row | dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    diffs: list[dict[str, Any]] = []
    counts = {
        "source": len(source_rows),
        "sqlite": len(sqlite_rows),
        "exact": 0,
        "missing_in_sqlite": 0,
        "extra_in_sqlite": 0,
        "changed": 0,
        "invalid_source": 0,
        "duplicate_source": 0,
        "unmapped_reference": 0,
        "orphan_reference": 0,
        "generated_only": 0,
    }

    source_keys: dict[str, int] = {}
    for item in source_rows:
        key = _text(item.get("id"), "")
        # Legacy favorites are intentionally small location records and predate
        # stable IDs.  Their normalized SQLite ID is derived from name/ZIP, so
        # validate them using the same deterministic key without altering the
        # authoritative JSON payload.
        if not key and domain == "favorites":
            key = _slug(item.get("name") or item.get("zip"), "location")
        if not key:
            counts["invalid_source"] += 1
            diffs.append({"domain": domain, "status": "invalid_source", "record_key": "", "detail": "missing id"})
            continue
        source_keys[key] = source_keys.get(key, 0) + 1
    for key, count in source_keys.items():
        if count > 1:
            counts["duplicate_source"] += count - 1
            diffs.append({"domain": domain, "status": "duplicate_source", "record_key": key, "detail": f"{count} source rows"})

    source_map = {key: item for key, item in _source_map(source_rows).items()}
    sqlite_map = _sqlite_map(sqlite_rows)

    for key, source_item in source_map.items():
        sqlite_item = sqlite_map.get(key)
        if not sqlite_item:
            counts["missing_in_sqlite"] += 1
            diffs.append({"domain": domain, "status": "missing_in_sqlite", "record_key": key, "detail": source_item})
            continue
        source_payload_hash = _source_payload_hash(source_item)
        if source_payload_hash == sqlite_item["payload_hash"]:
            counts["exact"] += 1
        else:
            counts["changed"] += 1
            diffs.append(
                {
                    "domain": domain,
                    "status": "changed",
                    "record_key": key,
                    "detail": {
                        "source_hash": source_payload_hash,
                        "sqlite_hash": sqlite_item["payload_hash"],
                    },
                }
            )

    for key, sqlite_item in sqlite_map.items():
        if key not in source_map:
            counts["extra_in_sqlite"] += 1
            diffs.append({"domain": domain, "status": "extra_in_sqlite", "record_key": key, "detail": sqlite_item["row"]})

    return diffs, counts


def _validate_links(
    conn: sqlite3.Connection,
    diffs: list[dict[str, Any]],
    totals: dict[str, int],
    *,
    reports_root: Path,
    source_root: Path,
) -> None:
    from .legacy_references import reviewed_decision

    species_ids = {row["id"] for row in conn.execute("SELECT id FROM species")}
    gear_ids = {row["id"] for row in conn.execute("SELECT id FROM gear_items")}
    water_ids = {row["id"] for row in conn.execute("SELECT id FROM waterbodies")}

    for row in conn.execute("SELECT id, species_ids_json, legacy_payload_json FROM waterbodies"):
        water_id = row["id"]
        try:
            species_ids_json = json.loads(row["species_ids_json"] or "[]")
        except Exception:
            species_ids_json = []
        for species_id in species_ids_json:
            if _slug(species_id) not in species_ids and _text(species_id) not in species_ids:
                totals["unmapped_reference"] += 1
                diffs.append({"domain": "waters", "status": "unmapped_reference", "record_key": water_id, "detail": species_id})

    for row in conn.execute("SELECT id, gear_refs_json, legacy_payload_json FROM catches"):
        catch_id = row["id"]
        try:
            gear_refs = json.loads(row["gear_refs_json"] or "{}")
        except Exception:
            gear_refs = {}
        try:
            payload_hash = _hash_payload(json.loads(row["legacy_payload_json"] or "{}"))
        except Exception:
            payload_hash = ""
        if isinstance(gear_refs, dict):
            for role, gear_id in gear_refs.items():
                if _text(gear_id) and _text(gear_id) not in gear_ids:
                    decision = reviewed_decision(
                        conn, catch_id=catch_id, relationship="gear", role=_text(role),
                        original_reference=_text(gear_id), payload_hash=payload_hash,
                    )
                    if decision and (
                        decision["decision"] == "accepted_legacy"
                        or (decision["decision"] == "linked" and decision.get("target_id") in gear_ids)
                    ):
                        continue
                    totals["unmapped_reference"] += 1
                    diffs.append({"domain": "catches", "status": "unmapped_reference", "record_key": catch_id, "detail": {"role": role, "gear_id": gear_id}})

    for row in conn.execute("SELECT id, species, waterbody, legacy_payload_json FROM catches"):
        catch_id = row["id"]
        species_key = _slug(row["species"], "")
        water_key = _slug(row["waterbody"], "")
        if species_key and species_key not in species_ids:
            totals["unmapped_reference"] += 1
            diffs.append({"domain": "catches", "status": "unmapped_reference", "record_key": catch_id, "detail": {"field": "species", "value": row["species"]}})
        if water_key and water_key not in water_ids:
            try:
                payload_hash = _hash_payload(json.loads(row["legacy_payload_json"] or "{}"))
            except Exception:
                payload_hash = ""
            decision = reviewed_decision(
                conn, catch_id=catch_id, relationship="waterbody", original_reference=_text(row["waterbody"]), payload_hash=payload_hash,
            )
            if decision and (
                decision["decision"] == "accepted_legacy"
                or (decision["decision"] == "linked" and decision.get("target_id") in water_ids)
            ):
                continue
            totals["unmapped_reference"] += 1
            diffs.append({"domain": "catches", "status": "unmapped_reference", "record_key": catch_id, "detail": {"field": "waterbody", "value": row["waterbody"]}})

    for row in conn.execute("SELECT id, favorite_species_json FROM target_profiles"):
        profile_id = row["id"]
        try:
            favorite_species = json.loads(row["favorite_species_json"] or "[]")
        except Exception:
            favorite_species = []
        for species_name in favorite_species:
            sid = _slug(species_name)
            if sid not in species_ids:
                totals["unmapped_reference"] += 1
                diffs.append({"domain": "target_profile", "status": "unmapped_reference", "record_key": profile_id, "detail": species_name})

    index_path = source_root / "reports_index.json"
    if index_path.exists() and reports_root.exists():
        index_rows = _source_items(_read_json(index_path, []))
        indexed_ids = { _text(item.get("id"), "") for item in index_rows if isinstance(item, dict) }
        file_ids = {path.stem for path in sorted(reports_root.glob("*.json"))}
        missing_files = sorted(indexed_ids - file_ids)
        orphan_files = sorted(file_ids - indexed_ids)
        for item in missing_files:
            totals["orphan_reference"] += 1
            diffs.append({"domain": "reports", "status": "orphan_reference", "record_key": item, "detail": "missing report JSON file"})
        for item in orphan_files:
            totals["generated_only"] += 1
            diffs.append({"domain": "reports", "status": "generated_only", "record_key": item, "detail": "orphan report JSON file"})


def validate_database(
    db_path: str | Path,
    *,
    source_manifest_hash: str | None = None,
    source_root: str | Path | None = None,
    reports_root: str | Path | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    source_root = Path(source_root) if source_root is not None else DATA_DIR
    reports_root = Path(reports_root) if reports_root is not None else REPORTS_DIR
    summary: dict[str, Any] = {
        "ok": False,
        "status": "unknown",
        "db_path": str(db_path),
        "source_manifest_hash": source_manifest_hash,
        "domains": {},
        "totals": {
            "source": 0,
            "sqlite": 0,
            "exact": 0,
            "missing_in_sqlite": 0,
            "extra_in_sqlite": 0,
            "changed": 0,
            "invalid_source": 0,
            "duplicate_source": 0,
            "unmapped_reference": 0,
            "orphan_reference": 0,
            "generated_only": 0,
        },
        "integrity_check": None,
        "foreign_key_check": [],
        "quick_check": None,
        "warnings": [],
        "diffs": [],
    }

    if not db_path.exists():
        summary["status"] = "missing_db"
        summary["warnings"].append("Database file does not exist.")
        return summary

    with connect(db_path, read_only=True) as conn:
        try:
            summary["quick_check"] = conn.execute("PRAGMA quick_check").fetchone()[0]
        except Exception as exc:
            summary["warnings"].append(f"quick_check failed: {exc}")

        try:
            summary["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        except Exception as exc:
            summary["warnings"].append(f"integrity_check failed: {exc}")

        try:
            summary["foreign_key_check"] = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
        except Exception as exc:
            summary["warnings"].append(f"foreign_key_check failed: {exc}")

        domains = {
            "species": {
                "source_path": source_root / "species_profiles_v43.json",
                "table_name": "species",
            },
            "waters": {
                "source_path": source_root / "illinois_waters.json",
                "manual_source_path": source_root / "manual_waters.json",
                "table_name": "waterbodies",
            },
            "target_profile": {
                "source_path": source_root / "target_profile.json",
                "table_name": "target_profiles",
            },
            "favorites": {
                "source_path": source_root / "favorites.json",
                "table_name": "saved_locations",
            },
            "gear_inventory": {
                "source_path": source_root / "gear_inventory.json",
                "table_name": "gear_items",
            },
            "catches": {
                "source_path": source_root / "catches.json",
                "table_name": "catches",
            },
            "reports": {
                "source_path": source_root / "reports_index.json",
                "table_name": "trip_reports",
            },
        }

        for domain, spec in domains.items():
            if domain == "waters":
                exists, starter_payload, starter_error = _read_json_status(spec["source_path"], [])
                exists_manual, manual_payload, manual_error = _read_json_status(spec["manual_source_path"], [])
                if starter_error not in (None, "empty", "missing"):
                    summary["totals"]["invalid_source"] += 1
                    summary["diffs"].append(
                        {
                            "domain": "waters",
                            "status": "invalid_source",
                            "record_key": "illinois_waters",
                            "detail": starter_error,
                        }
                    )
                if manual_error not in (None, "empty", "missing"):
                    summary["totals"]["invalid_source"] += 1
                    summary["diffs"].append(
                        {
                            "domain": "waters",
                            "status": "invalid_source",
                            "record_key": "manual_waters",
                            "detail": manual_error,
                        }
                    )
                source_rows = _source_items(starter_payload) + _source_items(manual_payload)
            else:
                exists, payload, error = _read_json_status(spec["source_path"], {} if domain == "target_profile" else [])
                if error not in (None, "empty", "missing"):
                    summary["totals"]["invalid_source"] += 1
                    summary["diffs"].append(
                        {
                            "domain": domain,
                            "status": "invalid_source",
                            "record_key": spec["source_path"].name,
                            "detail": error,
                        }
                    )
                if domain == "target_profile" and isinstance(payload, dict):
                    source_rows = [{
                        **payload,
                        "id": _slug(payload.get("id") or "current", "current"),
                        "legacy_payload_json": canonical_dumps(payload),
                    }]
                else:
                    source_rows = _source_items(payload)
            source_rows = [item for item in source_rows if isinstance(item, dict)]
            table_name = spec["table_name"]
            if domain == "waters":
                for item in source_rows:
                    if item.get("manual") and (
                        item.get("lat") is None
                        or item.get("lon") is None
                        or not isinstance(item.get("lat"), (int, float))
                        or not isinstance(item.get("lon"), (int, float))
                        or not (-90 <= float(item["lat"]) <= 90)
                        or not (-180 <= float(item["lon"]) <= 180)
                    ):
                        summary["totals"]["invalid_source"] += 1
                        summary["diffs"].append(
                            {
                                "domain": "waters",
                                "status": "invalid_source",
                                "record_key": _text(item.get("id"), _slug(item.get("name"), "water")),
                                "detail": "manual water requires valid latitude and longitude",
                            }
                        )

            query = f"SELECT id, legacy_payload_json FROM {table_name}"
            # Report deletion is intentionally soft: historical rows remain in
            # SQLite while compatibility JSON contains only active reports.
            if domain == "reports":
                query += " WHERE COALESCE(status, 'active') = 'active'"
            sqlite_rows = [dict(row) for row in conn.execute(query)]

            diffs, counts = _compare_records(domain, [item for item in source_rows if isinstance(item, dict)], sqlite_rows)
            summary["domains"][domain] = counts
            for key, value in counts.items():
                summary["totals"][key] = summary["totals"].get(key, 0) + int(value or 0)
            summary["diffs"].extend(diffs)

        _validate_links(conn, summary["diffs"], summary["totals"], reports_root=reports_root, source_root=source_root)

        summary["ok"] = (
            summary["integrity_check"] == "ok"
            and not summary["foreign_key_check"]
            and summary["totals"]["changed"] == 0
            and summary["totals"]["missing_in_sqlite"] == 0
            and summary["totals"]["extra_in_sqlite"] == 0
            and summary["totals"]["duplicate_source"] == 0
        )
        summary["status"] = "ok" if summary["ok"] and summary["totals"]["invalid_source"] == 0 and summary["totals"]["unmapped_reference"] == 0 and summary["totals"]["orphan_reference"] == 0 else "warning"

    return summary


def record_validation_results(db_path: str | Path, summary: dict[str, Any]) -> None:
    db_path = Path(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO validation_runs(run_at, db_path, mode, status, source_manifest_hash, summary_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                summary.get("generated_at") or summary.get("run_at") or "",
                str(db_path),
                "validate",
                summary.get("status") or ("ok" if summary.get("ok") else "warning"),
                summary.get("source_manifest_hash"),
                canonical_dumps(summary),
            ),
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for diff in summary.get("diffs", []):
            if not isinstance(diff, dict):
                continue
            conn.execute(
                """
                INSERT INTO validation_diffs(validation_run_id, domain, source_path, record_key, status, detail_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    _text(diff.get("domain"), ""),
                    _text(diff.get("source_path"), ""),
                    _text(diff.get("record_key"), ""),
                    _text(diff.get("status"), ""),
                    canonical_dumps(diff.get("detail", {})),
                    _text(summary.get("generated_at") or summary.get("run_at"), ""),
                ),
            )
