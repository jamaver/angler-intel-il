"""Read-only, bounded personal fishing analytics queries for V7.4.0."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connection import DEFAULT_DB, connect

MAX_ANALYTICS_ROWS = 5000


class AnalyticsInputError(ValueError):
    """Raised when an analytics filter cannot be safely interpreted."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _date_filter(value: object, label: str) -> str | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10]).date().isoformat()
    except ValueError as exc:
        raise AnalyticsInputError(f"{label} must use YYYY-MM-DD format") from exc


def _parse_timestamp(value: object) -> datetime | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sample_quality(total: int) -> tuple[str, str]:
    if total <= 0:
        return "none", "No recorded catches match these filters."
    if total < 3:
        return "thin", "Very small sample; treat frequency patterns as exploratory."
    if total < 8:
        return "useful", "Limited sample; patterns are directional rather than conclusive."
    return "solid", "Useful personal sample; continue recording trips and no-catch outcomes."


def _confidence_label(quality: str) -> str:
    return {"none": "none", "thin": "low", "useful": "medium", "solid": "high"}[quality]


def _ranked(counter: Counter[str], total: int, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))[:limit]:
        rows.append({
            "label": label,
            "count": count,
            "share_percent": round((count / total) * 100, 1) if total else 0.0,
        })
    return rows


def _daypart(moment: datetime) -> str:
    hour = moment.hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "midday"
    if 16 <= hour < 22:
        return "evening"
    return "night"


def _season(moment: datetime) -> str:
    month = moment.month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def build_personal_analytics(
    db_path: str | Path = DEFAULT_DB,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    species: str | None = None,
    waterbody: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Return explainable frequency summaries from SQLite-authoritative catches.

    This intentionally reports catch frequency only. Catch-rate, trip outcome, and
    no-catch analysis need complete trip records and belong to later V7.4 work.
    """
    start = _date_filter(date_from, "date_from")
    end = _date_filter(date_to, "date_to")
    if start and end and start > end:
        raise AnalyticsInputError("date_from cannot be later than date_to")
    try:
        requested_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise AnalyticsInputError("limit must be a number between 1 and 20") from exc
    if not 1 <= requested_limit <= 20:
        raise AnalyticsInputError("limit must be between 1 and 20")

    clauses: list[str] = []
    params: list[str | int] = []
    if start:
        clauses.append("substr(COALESCE(timestamp, ''), 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(COALESCE(timestamp, ''), 1, 10) <= ?")
        params.append(end)
    clean_species = _clean_text(species)
    if clean_species:
        clauses.append("lower(trim(COALESCE(species, ''))) = lower(?)")
        params.append(clean_species)
    clean_waterbody = _clean_text(waterbody)
    if clean_waterbody:
        clauses.append("lower(trim(COALESCE(waterbody, ''))) = lower(?)")
        params.append(clean_waterbody)
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        "SELECT id, timestamp, species, waterbody, lure, rig, zip "
        f"FROM catches{where_sql} ORDER BY timestamp DESC, id DESC LIMIT ?"
    )
    params.append(MAX_ANALYTICS_ROWS + 1)
    with connect(db_path, read_only=True) as conn:
        rows = [dict(row) for row in conn.execute(query, params)]

    truncated = len(rows) > MAX_ANALYTICS_ROWS
    rows = rows[:MAX_ANALYTICS_ROWS]
    species_counts: Counter[str] = Counter()
    water_counts: Counter[str] = Counter()
    lure_counts: Counter[str] = Counter()
    daypart_counts: Counter[str] = Counter()
    dated_moments: list[datetime] = []
    missing = Counter()
    for row in rows:
        fish = _clean_text(row["species"])
        water = _clean_text(row["waterbody"])
        lure = _clean_text(row["lure"])
        if fish:
            species_counts[fish] += 1
        else:
            missing["species"] += 1
        if water:
            water_counts[water] += 1
        else:
            missing["waterbody"] += 1
        if lure:
            lure_counts[lure] += 1
        else:
            missing["lure"] += 1
        moment = _parse_timestamp(row["timestamp"])
        if moment:
            dated_moments.append(moment)
            daypart_counts[_daypart(moment)] += 1
        else:
            missing["timestamp"] += 1

    total = len(rows)
    quality, quality_note = _sample_quality(total)
    notes = [quality_note, "Frequency summaries do not claim catch rate; no-catch trip outcomes are not yet complete enough."]
    for field in ("species", "waterbody", "lure", "timestamp"):
        if missing[field]:
            notes.append(f"{missing[field]} catch record(s) lack {field} data.")
    if truncated:
        notes.append(f"Results are limited to the newest {MAX_ANALYTICS_ROWS} matching catches.")
    dayparts = [
        {"label": label, "count": daypart_counts.get(label, 0), "share_percent": round((daypart_counts.get(label, 0) / total) * 100, 1) if total else 0.0}
        for label in ("morning", "midday", "evening", "night")
    ]
    return {
        "ok": True,
        "source": "sqlite",
        "generated_at": _utc_now(),
        "query": {"date_from": start, "date_to": end, "species": clean_species or None, "waterbody": clean_waterbody or None, "limit": requested_limit},
        "sample": {
            "catch_count": total,
            "quality": quality,
            "confidence": _confidence_label(quality),
            "date_range": {
                "first": min(dated_moments).date().isoformat() if dated_moments else None,
                "last": max(dated_moments).date().isoformat() if dated_moments else None,
            },
            "truncated": truncated,
        },
        "top_species": _ranked(species_counts, total, requested_limit),
        "top_waterbodies": _ranked(water_counts, total, requested_limit),
        "top_lures": _ranked(lure_counts, total, requested_limit),
        "dayparts": dayparts,
        "missing_data": dict(missing),
        "notes": notes,
    }


def build_catch_water_analytics(
    db_path: str | Path = DEFAULT_DB,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    species: str | None = None,
    waterbody: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Build V7.4.1 catch and water frequency analytics without rate claims."""
    baseline = build_personal_analytics(
        db_path,
        date_from=date_from,
        date_to=date_to,
        species=species,
        waterbody=waterbody,
        limit=limit,
    )
    start = baseline["query"]["date_from"]
    end = baseline["query"]["date_to"]
    clean_species = baseline["query"]["species"]
    clean_waterbody = baseline["query"]["waterbody"]
    clauses: list[str] = []
    params: list[str | int] = []
    if start:
        clauses.append("substr(COALESCE(timestamp, ''), 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(COALESCE(timestamp, ''), 1, 10) <= ?")
        params.append(end)
    if clean_species:
        clauses.append("lower(trim(COALESCE(species, ''))) = lower(?)")
        params.append(clean_species)
    if clean_waterbody:
        clauses.append("lower(trim(COALESCE(waterbody, ''))) = lower(?)")
        params.append(clean_waterbody)
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT timestamp, species, waterbody, lure FROM catches{where_sql} ORDER BY timestamp DESC, id DESC LIMIT ?"
    params.append(MAX_ANALYTICS_ROWS + 1)
    with connect(db_path, read_only=True) as conn:
        rows = [dict(row) for row in conn.execute(query, params)][:MAX_ANALYTICS_ROWS]

    total = len(rows)
    seasonal_counts: Counter[str] = Counter()
    dated_count = 0
    for row in rows:
        moment = _parse_timestamp(row["timestamp"])
        if moment:
            seasonal_counts[_season(moment)] += 1
            dated_count += 1
    quality = baseline["sample"]["quality"]
    water_note = "Waterbody frequency only; trip count and no-catch outcomes are not deterministically linked to historical catches."
    season_rows = [
        {
            "label": label,
            "count": seasonal_counts.get(label, 0),
            "share_percent": round((seasonal_counts.get(label, 0) / dated_count) * 100, 1) if dated_count else 0.0,
        }
        for label in ("spring", "summer", "fall", "winter")
    ]
    return {
        "ok": True,
        "source": "sqlite",
        "generated_at": _utc_now(),
        "query": baseline["query"],
        "sample": baseline["sample"],
        "catch_frequency": {
            "by_species": baseline["top_species"],
            "by_waterbody": baseline["top_waterbodies"],
            "by_lure": baseline["top_lures"],
        },
        "waterbody_frequency": {
            "available": total > 0,
            "rows": baseline["top_waterbodies"],
            "label": "Recorded catch frequency by waterbody",
            "note": water_note,
        },
        "time_of_day": {
            "available": dated_count > 0,
            "rows": baseline["dayparts"],
            "label": "Recorded catches by daypart",
            "note": "Daypart patterns use catch timestamps and do not yet include total effort or no-catch trips.",
        },
        "seasonal_frequency": {
            "available": dated_count > 0,
            "rows": season_rows,
            "label": "Recorded catches by season",
            "note": "Seasonal frequency uses recorded catch timestamps, not fishing effort.",
        },
        "catch_rate_by_trip": {
            "available": False,
            "label": "Catch rate by trip",
            "reason": "Historical catches do not yet carry deterministic trip IDs, so a reliable trip denominator is unavailable.",
        },
        "no_catch_trip_frequency": {
            "available": False,
            "label": "No-catch trip frequency",
            "reason": "Trip-completion outcomes are not yet complete enough to measure no-catch frequency.",
        },
        "sample_quality": {
            "label": quality,
            "confidence": baseline["sample"]["confidence"],
            "note": next((note for note in baseline["notes"] if "sample" in note.lower()), "Sample quality is based on recorded catch count."),
        },
        "missing_data": baseline["missing_data"],
        "notes": baseline["notes"] + [water_note],
    }


def build_lure_presentation_analytics(
    db_path: str | Path = DEFAULT_DB,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    species: str | None = None,
    waterbody: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Build V7.4.2 lure and rig frequency summaries from stored catch fields."""
    baseline = build_personal_analytics(
        db_path,
        date_from=date_from,
        date_to=date_to,
        species=species,
        waterbody=waterbody,
        limit=limit,
    )
    start = baseline["query"]["date_from"]
    end = baseline["query"]["date_to"]
    clean_species = baseline["query"]["species"]
    clean_waterbody = baseline["query"]["waterbody"]
    clauses: list[str] = []
    params: list[str | int] = []
    if start:
        clauses.append("substr(COALESCE(timestamp, ''), 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(COALESCE(timestamp, ''), 1, 10) <= ?")
        params.append(end)
    if clean_species:
        clauses.append("lower(trim(COALESCE(species, ''))) = lower(?)")
        params.append(clean_species)
    if clean_waterbody:
        clauses.append("lower(trim(COALESCE(waterbody, ''))) = lower(?)")
        params.append(clean_waterbody)
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT species, waterbody, lure, rig FROM catches{where_sql} ORDER BY timestamp DESC, id DESC LIMIT ?"
    params.append(MAX_ANALYTICS_ROWS + 1)
    with connect(db_path, read_only=True) as conn:
        rows = [dict(row) for row in conn.execute(query, params)][:MAX_ANALYTICS_ROWS]

    total = len(rows)
    rig_counts: Counter[str] = Counter()
    species_lures: dict[str, Counter[str]] = {}
    water_lures: dict[str, Counter[str]] = {}
    missing_rig = 0
    for row in rows:
        lure = _clean_text(row["lure"])
        rig = _clean_text(row["rig"])
        fish = _clean_text(row["species"])
        water = _clean_text(row["waterbody"])
        if rig:
            rig_counts[rig] += 1
        else:
            missing_rig += 1
        if lure and fish:
            species_lures.setdefault(fish, Counter())[lure] += 1
        if lure and water:
            water_lures.setdefault(water, Counter())[lure] += 1

    def grouped_rows(groups: dict[str, Counter[str]]) -> list[dict[str, Any]]:
        ordered = sorted(groups.items(), key=lambda item: (-sum(item[1].values()), item[0].lower()))[:baseline["query"]["limit"]]
        return [
            {
                "label": label,
                "catch_count": sum(counter.values()),
                "top_lures": _ranked(counter, sum(counter.values()), baseline["query"]["limit"]),
            }
            for label, counter in ordered
        ]

    notes = list(baseline["notes"])
    notes.append("Lure and rig values are saved catch-log text; this release does not infer colors, weights, or retrieves from wording.")
    if missing_rig:
        notes.append(f"{missing_rig} catch record(s) lack rig or presentation data.")
    return {
        "ok": True,
        "source": "sqlite",
        "generated_at": _utc_now(),
        "query": baseline["query"],
        "sample": baseline["sample"],
        "lure_frequency": {
            "available": total > 0,
            "rows": baseline["top_lures"],
            "label": "Recorded lure frequency",
            "note": "Frequency reflects logged catches, not total fishing effort or lure effectiveness.",
        },
        "presentation_frequency": {
            "available": bool(rig_counts),
            "rows": _ranked(rig_counts, total, baseline["query"]["limit"]),
            "label": "Recorded rig or presentation frequency",
            "note": "Rig and presentation details are user-entered catch-log text.",
        },
        "lures_by_species": grouped_rows(species_lures),
        "lures_by_waterbody": grouped_rows(water_lures),
        "lure_color_performance": {
            "available": False,
            "label": "Lure color performance",
            "reason": "Catch records do not yet store lure color as a normalized field.",
        },
        "lure_weight_performance": {
            "available": False,
            "label": "Lure weight performance",
            "reason": "Catch records do not yet store lure weight as a normalized field.",
        },
        "sample_quality": {
            "label": baseline["sample"]["quality"],
            "confidence": baseline["sample"]["confidence"],
        },
        "missing_data": {**baseline["missing_data"], "rig": missing_rig},
        "notes": notes,
    }


def build_gear_analytics(
    db_path: str | Path = DEFAULT_DB,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """Build V7.4.3 read-only ownership, usage, catch-link, and maintenance summaries."""
    try:
        requested_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise AnalyticsInputError("limit must be a number between 1 and 20") from exc
    if not 1 <= requested_limit <= 20:
        raise AnalyticsInputError("limit must be between 1 and 20")
    with connect(db_path, read_only=True) as conn:
        gear_rows = [dict(row) for row in conn.execute(
            """SELECT id, category, display_name, brand, model, status, favorite, quantity
               FROM gear_items ORDER BY display_name COLLATE NOCASE, id"""
        )]
        usage_rows = [dict(row) for row in conn.execute(
            "SELECT gear_item_id, count(*) AS usage_events, max(used_at) AS last_used FROM gear_usage GROUP BY gear_item_id"
        )]
        linked_rows = [dict(row) for row in conn.execute(
            """SELECT cg.gear_item_id, cg.gear_role, c.species, c.waterbody, c.timestamp
               FROM catch_gear cg JOIN catches c ON c.id = cg.catch_id
               WHERE cg.gear_item_id IS NOT NULL"""
        )]
        maintenance_rows = [dict(row) for row in conn.execute(
            "SELECT gear_item_id, maintenance_type, due_at, last_done_at FROM gear_maintenance"
        )]

    usage_by_id = {row["gear_item_id"]: row for row in usage_rows}
    linked_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in linked_rows:
        linked_by_id.setdefault(str(row["gear_item_id"]), []).append(row)
    maintenance_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in maintenance_rows:
        maintenance_by_id.setdefault(str(row["gear_item_id"]), []).append(row)
    today = datetime.now(timezone.utc).date().isoformat()

    items: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    underused: list[dict[str, Any]] = []
    due_maintenance: list[dict[str, Any]] = []
    for gear in gear_rows:
        item_id = str(gear["id"])
        usage = usage_by_id.get(item_id, {})
        linked = linked_by_id.get(item_id, [])
        species_counts = Counter(_clean_text(row["species"]) for row in linked if _clean_text(row["species"]))
        water_counts = Counter(_clean_text(row["waterbody"]) for row in linked if _clean_text(row["waterbody"]))
        label = _clean_text(gear["display_name"]) or " ".join(part for part in (_clean_text(gear["brand"]), _clean_text(gear["model"])) if part) or item_id
        item = {
            "id": item_id,
            "label": label,
            "category": _clean_text(gear["category"]) or "other",
            "status": _clean_text(gear["status"]) or "owned",
            "favorite": bool(gear["favorite"]),
            "quantity": int(gear["quantity"] or 0),
            "usage_events": int(usage.get("usage_events") or 0),
            "last_used": usage.get("last_used"),
            "linked_catches": len(linked),
            "top_species": _ranked(species_counts, len(linked), requested_limit),
            "top_waterbodies": _ranked(water_counts, len(linked), requested_limit),
        }
        items.append(item)
        category_counts[item["category"]] += 1
        if item["status"] == "owned" and not item["usage_events"] and not item["linked_catches"]:
            underused.append(item)
        for record in maintenance_by_id.get(item_id, []):
            due_at = _clean_text(record["due_at"])
            if due_at and due_at[:10] <= today:
                due_maintenance.append({"id": item_id, "label": label, "maintenance_type": _clean_text(record["maintenance_type"]) or "maintenance", "due_at": due_at[:10]})

    active = [item for item in items if item["status"] == "owned"]
    most_linked = sorted(items, key=lambda item: (-item["linked_catches"], -item["usage_events"], item["label"].lower()))[:requested_limit]
    most_used = sorted(items, key=lambda item: (-item["usage_events"], -item["linked_catches"], item["label"].lower()))[:requested_limit]
    linked_count = sum(item["linked_catches"] for item in items)
    quality, quality_note = _sample_quality(linked_count)
    return {
        "ok": True,
        "source": "sqlite",
        "generated_at": _utc_now(),
        "sample": {
            "gear_items": len(items),
            "owned_items": len(active),
            "catch_gear_links": linked_count,
            "quality": quality,
            "confidence": _confidence_label(quality),
        },
        "inventory": {
            "by_category": _ranked(category_counts, len(items), requested_limit),
            "favorites": sum(1 for item in items if item["favorite"]),
            "retired": sum(1 for item in items if item["status"] in {"retired", "archived"}),
        },
        "most_used": most_used,
        "most_catch_linked": most_linked,
        "underused": underused[:requested_limit],
        "maintenance": {
            "tracked_records": len(maintenance_rows),
            "due": sorted(due_maintenance, key=lambda item: (item["due_at"], item["label"].lower()))[:requested_limit],
            "note": "Maintenance is shown only for records with an explicit due date.",
        },
        "setup_outcomes": {
            "available": False,
            "label": "Catch outcomes by saved setup",
            "reason": "Historical catches do not yet store deterministic gear setup IDs.",
        },
        "notes": [
            quality_note,
            "Catch-linked gear counts reflect logged catches, not total fishing effort or gear effectiveness.",
            "Underused means no recorded usage event or catch link; it does not mean unsuitable gear.",
        ],
    }
