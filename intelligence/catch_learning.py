from __future__ import annotations

from collections import Counter
from typing import Any


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _pick_waterbody(catch: dict[str, Any]) -> str:
    for key in ("waterbody", "water", "location", "spot", "lake", "river"):
        text = _safe_text(catch.get(key))
        if text:
            return text
    return ""


def _sample_strength(total: int, local_total: int) -> str:
    if local_total >= 8 or total >= 25:
        return "strong"
    if local_total >= 3 or total >= 10:
        return "moderate"
    if local_total > 0 or total > 0:
        return "light"
    return "none"


def _sample_quality_label(total: int, local_total: int) -> str:
    strength = _sample_strength(total, local_total)
    if strength == "strong":
        return "solid"
    if strength == "moderate":
        return "useful"
    if strength == "light":
        return "thin"
    return "none"


def build_catch_learning_summary(
    catches: list[dict[str, Any]] | None,
    *,
    zip_code: str = "",
    target_species: str = "",
    target_waterbody: str = "",
) -> dict[str, Any]:
    records = [c for c in catches or [] if isinstance(c, dict)]
    local_records = [c for c in records if _safe_text(c.get("zip")) == _safe_text(zip_code)]
    species_key = _safe_text(target_species).lower()
    waterbody_key = _safe_text(target_waterbody).lower()

    species_counts = Counter(_safe_text(c.get("species")) or "Unknown" for c in records)
    lure_counts = Counter(_safe_text(c.get("lure")) or "Unknown" for c in records)
    waterbody_counts = Counter(_pick_waterbody(c) or "Unknown" for c in records)

    local_species_counts = Counter(_safe_text(c.get("species")) or "Unknown" for c in local_records)
    local_lure_counts = Counter(_safe_text(c.get("lure")) or "Unknown" for c in local_records)
    local_waterbody_counts = Counter(_pick_waterbody(c) or "Unknown" for c in local_records)

    if species_key:
        species_target_records = [c for c in records if _safe_text(c.get("species")).lower() == species_key]
        local_species_target_records = [c for c in local_records if _safe_text(c.get("species")).lower() == species_key]
    else:
        species_target_records = []
        local_species_target_records = []

    if waterbody_key:
        waterbody_target_records = [c for c in records if _pick_waterbody(c).lower() == waterbody_key]
        local_waterbody_target_records = [c for c in local_records if _pick_waterbody(c).lower() == waterbody_key]
    else:
        waterbody_target_records = []
        local_waterbody_target_records = []

    total = len(records)
    local_total = len(local_records)
    strength = _sample_strength(total, local_total)

    if local_total > 0:
        summary = f"{local_total} catch log entry(s) already exist for ZIP {zip_code}."
        weight = "Use local catch history as a tie-breaker, but do not let a tiny sample overpower current conditions."
        level = "local"
    elif total > 0:
        summary = f"{total} total catch log entry(s) are available across saved trips."
        weight = "Use broader catch patterns as a weak signal and keep current water conditions in front."
        level = "personal"
    else:
        summary = f"No catch history yet for {target_species or 'this search'}."
        weight = "Current weather, season, water type, and species behavior carry the recommendation."
        level = "starter"

    if local_total > 0 and local_total < 3:
        weight = "There is some local history, but the sample is small enough that current conditions should dominate."
    elif total > 0 and local_total == 0 and total < 5:
        weight = "There is some catch history, but the sample is small enough that it should only nudge the decision."

    target_species_summary = None
    if species_key:
        target_species_summary = {
            "species": target_species,
            "total": len(species_target_records),
            "local_total": len(local_species_target_records),
            "top_lures": [
                {"name": name, "count": count}
                for name, count in Counter(_safe_text(c.get("lure")) or "Unknown" for c in species_target_records).most_common(3)
            ],
            "top_waterbodies": [
                {"name": name, "count": count}
                for name, count in Counter(_pick_waterbody(c) or "Unknown" for c in species_target_records).most_common(3)
            ],
        }

    target_waterbody_summary = None
    if waterbody_key:
        target_waterbody_summary = {
            "waterbody": target_waterbody,
            "total": len(waterbody_target_records),
            "local_total": len(local_waterbody_target_records),
            "top_species": [
                {"name": name, "count": count}
                for name, count in Counter(_safe_text(c.get("species")) or "Unknown" for c in waterbody_target_records).most_common(3)
            ],
            "top_lures": [
                {"name": name, "count": count}
                for name, count in Counter(_safe_text(c.get("lure")) or "Unknown" for c in waterbody_target_records).most_common(3)
            ],
        }

    return {
        "total": total,
        "local_total": local_total,
        "top_species": [
            {"name": name, "count": count}
            for name, count in species_counts.most_common(5)
        ],
        "top_lures": [
            {"name": name, "count": count}
            for name, count in lure_counts.most_common(5)
        ],
        "top_waterbodies": [
            {"name": name, "count": count}
            for name, count in waterbody_counts.most_common(5)
        ],
        "local_top_species": [
            {"name": name, "count": count}
            for name, count in local_species_counts.most_common(3)
        ],
        "local_top_lures": [
            {"name": name, "count": count}
            for name, count in local_lure_counts.most_common(3)
        ],
        "local_top_waterbodies": [
            {"name": name, "count": count}
            for name, count in local_waterbody_counts.most_common(3)
        ],
        "sample_size": {
            "total": total,
            "local": local_total,
            "species_total": len(species_target_records),
            "species_local": len(local_species_target_records),
            "waterbody_total": len(waterbody_target_records),
            "waterbody_local": len(local_waterbody_target_records),
        },
        "sample_quality": _sample_quality_label(total, local_total),
        "strength": strength,
        "summary": summary,
        "weight": weight,
        "level": level,
        "target_species": target_species_summary,
        "target_waterbody": target_waterbody_summary,
        "message": "Personal catch history is active." if total else "No catches logged yet. Once you log catches, Angler Intel will start showing your personal patterns.",
    }
