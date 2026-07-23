from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence.species import SPECIES
from persistence.target_profile_mirror import mirror_target_profile
from persistence.repositories import (
    JsonTargetProfileRepository,
    SQLiteTargetProfileRepository,
    read_domain,
)

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
TARGET_PROFILE_PATH = DATA_DIR / "target_profile.json"
_READ_DIAGNOSTICS: dict[str, Any] = {
    "selected_source": "compare_json",
    "effective_source": "json",
    "comparison_status": "not_run",
    "fallback_used": False,
    "error": None,
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else default
    except Exception:
        return default


def _read_source_mode() -> str:
    """Resolve a guarded V7.2 target-profile read mode.

    Comparison mode returns JSON and is the safe default. A real SQLite read
    requires an explicit operator environment flag; no web UI can enable it.
    """
    requested = str(os.environ.get("AI_TARGET_PROFILE_READ_SOURCE", "compare_json")).strip().lower()
    if requested not in {"json", "sqlite", "sqlite_with_json_fallback", "compare_json"}:
        requested = "compare_json"
    if requested in {"sqlite", "sqlite_with_json_fallback"} and os.environ.get("AI_ENABLE_V7_STAGED_READS") != "1":
        return "compare_json"
    return requested


def get_target_profile_read_diagnostics() -> dict[str, Any]:
    """Read-only diagnostics for App Health and V7.2 comparison monitoring."""
    return dict(_READ_DIAGNOSTICS)


def _read_profile_document() -> dict[str, Any]:
    global _READ_DIAGNOSTICS
    source = _read_source_mode()
    db_path = Path(os.environ.get("AI_SQLITE_DB_PATH", str(DATA_DIR / "angler_intel.sqlite3")))
    result = read_domain(
        "target_profile",
        json_repository=JsonTargetProfileRepository(TARGET_PROFILE_PATH),
        sqlite_repository=SQLiteTargetProfileRepository(db_path),
        source=source,  # type: ignore[arg-type]
    )
    _READ_DIAGNOSTICS = {
        "selected_source": result.selected_source,
        "effective_source": result.effective_source,
        "comparison_status": result.comparison_status,
        "comparison_differences": list(result.comparison_differences),
        "fallback_used": result.fallback_used,
        "timing_ms": dict(result.timing_ms),
        "error": result.error,
    }
    return dict(result.value) if isinstance(result.value, dict) else {}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def available_target_species() -> list[str]:
    return [str(species.get("name") or "").strip() for species in SPECIES if str(species.get("name") or "").strip()]


def _canonical_species_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    slug = _slugify(text)
    for species in SPECIES:
        name = str(species.get("name") or "").strip()
        if not name:
            continue
        if _slugify(name) == slug:
            return name
    return text.title()


def _normalize_species_list(values: Any) -> list[str]:
    if isinstance(values, list):
        items = values
    elif values:
        items = [values]
    else:
        items = []

    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        name = _canonical_species_name(item)
        if name and name not in seen:
            seen.add(name)
            output.append(name)
    return output


def default_target_profile() -> dict[str, Any]:
    species = available_target_species()
    default = species[0] if species else ""
    return {
        "default_target_species": default,
        "current_trip_target": "",
        "favorite_species": [default] if default else [],
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def load_target_profile() -> dict[str, Any]:
    profile = default_target_profile()
    stored = _read_profile_document()
    if isinstance(stored, dict):
        profile["default_target_species"] = _canonical_species_name(stored.get("default_target_species") or profile["default_target_species"])
        profile["current_trip_target"] = _canonical_species_name(stored.get("current_trip_target") or profile["current_trip_target"])
        profile["favorite_species"] = _normalize_species_list(stored.get("favorite_species") or profile["favorite_species"])
        if not profile["favorite_species"] and profile["default_target_species"]:
            profile["favorite_species"] = [profile["default_target_species"]]
        if stored.get("updated_at"):
            profile["updated_at"] = str(stored.get("updated_at"))
    return profile


def save_target_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = load_target_profile()
    if "default_target_species" in payload:
        profile["default_target_species"] = _canonical_species_name(payload.get("default_target_species"))
    if "current_trip_target" in payload:
        profile["current_trip_target"] = _canonical_species_name(payload.get("current_trip_target"))
    if "favorite_species" in payload:
        profile["favorite_species"] = _normalize_species_list(payload.get("favorite_species"))
    if "favorite_species_add" in payload:
        name = _canonical_species_name(payload.get("favorite_species_add"))
        if name and name not in profile["favorite_species"]:
            profile["favorite_species"].append(name)
    if "favorite_species_remove" in payload:
        name = _canonical_species_name(payload.get("favorite_species_remove"))
        profile["favorite_species"] = [item for item in profile["favorite_species"] if item != name]

    profile["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_json(TARGET_PROFILE_PATH, profile)
    # JSON is authoritative. Mirror failure is intentionally non-fatal and is
    # recorded by the V7.1 diagnostics framework for later reconciliation.
    mirror_target_profile(profile, TARGET_PROFILE_PATH)
    return profile


def resolve_target_species(requested: Any = "", profile: dict[str, Any] | None = None) -> tuple[str, str]:
    profile = profile or load_target_profile()
    requested_name = _canonical_species_name(requested)
    if requested_name:
        return requested_name, "request"

    current = _canonical_species_name(profile.get("current_trip_target"))
    if current:
        return current, "current_trip_target"

    default = _canonical_species_name(profile.get("default_target_species"))
    if default:
        return default, "default_target_species"

    favorites = _normalize_species_list(profile.get("favorite_species"))
    if favorites:
        return favorites[0], "favorite_species"

    return "", "auto"


def species_fit_bonus(water: dict[str, Any] | None, target_species: str) -> dict[str, Any]:
    water = water if isinstance(water, dict) else {}
    target = _canonical_species_name(target_species)
    if not target:
        return {
            "species": "",
            "score": 0,
            "label": "Auto",
            "reason": "No target species selected yet.",
            "match_type": "auto",
        }

    species = [str(item).strip() for item in (water.get("species") or []) if str(item).strip()]
    species_keys = {_slugify(item) for item in species}
    target_key = _slugify(target)
    water_type = str(water.get("type") or "").lower()
    stocked_trout = bool(water.get("stocked_trout"))
    catch_history = max(int(water.get("catch_history_count") or 0), 0)
    favorite = bool(water.get("favorite"))
    manual = bool(water.get("manual") or str(water.get("source") or "").lower() == "manual")

    score = 18
    reasons: list[str] = []
    match_type = "pattern"

    if target_key in species_keys:
        score += 50
        match_type = "species"
        reasons.append("Target species is listed for this waterbody.")
    elif target_key in {"rainbow-trout", "brown-trout", "brook-trout", "lake-trout"} and stocked_trout:
        score += 42
        match_type = "stocked"
        reasons.append("Stocked trout waters are a strong match for trout targets.")
    elif target_key in {"largemouth-bass", "smallmouth-bass", "crappie", "bluegill", "common-carp", "channel-catfish", "flathead-catfish", "walleye", "sauger", "northern-pike", "muskie", "white-bass", "yellow-perch"}:
        preferred_types = {
            "largemouth-bass": {"lake", "pond", "reservoir"},
            "smallmouth-bass": {"river", "lake", "reservoir"},
            "crappie": {"lake", "pond", "reservoir"},
            "bluegill": {"lake", "pond"},
            "common-carp": {"lake", "pond", "river"},
            "channel-catfish": {"lake", "pond", "river"},
            "flathead-catfish": {"river", "lake"},
            "walleye": {"river", "lake", "reservoir"},
            "sauger": {"river"},
            "northern-pike": {"lake", "river", "reservoir"},
            "muskie": {"lake", "river", "reservoir"},
            "white-bass": {"river", "lake", "reservoir"},
            "yellow-perch": {"lake", "reservoir"},
        }
        if water_type and water_type in preferred_types.get(target_key, set()):
            score += 24
            reasons.append("Waterbody type matches the target species pattern.")
        else:
            score += 8
            reasons.append("Waterbody type is a partial fit for the target species.")
    else:
        score += 10
        reasons.append("No direct species match, so the ranking stays conservative.")

    if catch_history >= 5:
        score += 10
        reasons.append("Catch history provides a stronger local signal.")
    elif catch_history > 0:
        score += 5
        reasons.append("Catch history provides a small local signal.")

    if favorite:
        score += 4
        reasons.append("Favorite waters get a small nudge.")

    if manual:
        score += 2
        reasons.append("Manual waters can be useful once you have verified them on site.")

    score = max(0, min(100, score))
    if score >= 80:
        label = "Excellent"
    elif score >= 60:
        label = "Good"
    elif score >= 40:
        label = "Fair"
    else:
        label = "Low"

    return {
        "species": target,
        "score": score,
        "label": label,
        "reason": " ".join(reasons),
        "match_type": match_type,
    }
