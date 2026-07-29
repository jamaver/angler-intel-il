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
