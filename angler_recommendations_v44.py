from __future__ import annotations

import html
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import jsonify, render_template, request
from persistence.authority_resolution import AuthorityWriteError, require_write_authority, resolve_authority
from persistence.recommendation_history import json_recommendation_history
from persistence.recommendations_authority import list_authoritative_recommendation_history, record_recommendation_feedback


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

WATERS_PATH = DATA_DIR / "illinois_waters.json"
SPECIES_PATH = DATA_DIR / "species_profiles_v43.json"
RIGS_PATH = DATA_DIR / "lure_rig_setups_v43.json"
SETTINGS_PATH = DATA_DIR / "species_settings_v431.json"
RULES_PATH = DATA_DIR / "recommendation_rules_v44.json"
REPORTS_DIR = BASE_DIR / "reports"

VERSION = "v4.4"


def _recommendations_db_path() -> Path:
    return Path(os.environ.get("AI_SQLITE_DB_PATH", str(DATA_DIR / "angler_intel.sqlite3")))


def _recommendations_authority():
    return resolve_authority("recommendations", _recommendations_db_path())


ALIASES = {
    "bass": "largemouth-bass",
    "largemouth": "largemouth-bass",
    "largemouth bass": "largemouth-bass",
    "smallmouth": "smallmouth-bass",
    "smallmouth bass": "smallmouth-bass",
    "bluegill": "bluegill",
    "panfish": "bluegill",
    "crappie": "crappie",
    "catfish": "channel-catfish",
    "channel catfish": "channel-catfish",
    "flathead": "flathead-catfish",
    "flathead catfish": "flathead-catfish",
    "walleye": "walleye",
    "sauger": "sauger",
    "pike": "northern-pike",
    "northern pike": "northern-pike",
    "muskie": "muskie",
    "musky": "muskie",
    "trout": "rainbow-trout",
    "rainbow trout": "rainbow-trout",
    "brown trout": "brown-trout",
    "perch": "yellow-perch",
    "yellow perch": "yellow-perch",
    "white bass": "white-bass",
    "carp": "common-carp",
    "common carp": "common-carp",
    "salmon": "coho-salmon",
    "coho": "coho-salmon",
    "chinook": "chinook-salmon",
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _slug(value: Any) -> str:
    value = str(value or "").strip().lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _species_id(value: Any) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return ""
    return ALIASES.get(key) or _slug(key)


def _species_profiles() -> list[dict[str, Any]]:
    data = _read_json(SPECIES_PATH, [])
    return data if isinstance(data, list) else []


def _species_by_id() -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for item in _species_profiles()
        if isinstance(item, dict) and item.get("id")
    }


def _rigs() -> list[dict[str, Any]]:
    data = _read_json(RIGS_PATH, [])
    return data if isinstance(data, list) else []


def _waters() -> list[dict[str, Any]]:
    data = _read_json(WATERS_PATH, [])
    return data if isinstance(data, list) else []


def _rules() -> dict[str, Any]:
    data = _read_json(RULES_PATH, {})
    return data if isinstance(data, dict) else {}


def _settings() -> dict[str, Any]:
    data = _read_json(SETTINGS_PATH, {})
    species_ids = set(_species_by_id())

    if not isinstance(data, dict):
        data = {}

    active = data.get("active_species", [])
    if not isinstance(active, list):
        active = []

    active = [sid for sid in active if sid in species_ids]

    if not active:
        active = [
            "largemouth-bass",
            "smallmouth-bass",
            "bluegill",
            "crappie",
            "channel-catfish",
            "walleye",
            "northern-pike",
            "rainbow-trout",
            "brown-trout",
            "yellow-perch",
            "white-bass",
            "common-carp",
        ]
        active = [sid for sid in active if sid in species_ids]

    return {
        "active_species": active,
        "raw": data,
    }


def _season_for_month(month: int | None = None) -> str:
    month = month or datetime.now().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _get_coords(zip_code: str) -> tuple[float, float] | None:
    zip_code = str(zip_code or "").strip()

    try:
        from intelligence.location import get_coords  # type: ignore

        result = get_coords(zip_code)

        if isinstance(result, dict):
            lat = _safe_float(result.get("lat") or result.get("latitude"))
            lon = _safe_float(result.get("lon") or result.get("lng") or result.get("longitude"))
            if lat is not None and lon is not None:
                return lat, lon

        if isinstance(result, (tuple, list)) and len(result) >= 2:
            lat = _safe_float(result[0])
            lon = _safe_float(result[1])
            if lat is not None and lon is not None:
                return lat, lon
    except Exception:
        pass

    # Small fallback so Oswego-area testing keeps working even if location helper changes.
    fallback = {
        "60543": (41.6828, -88.3515),
        "60504": (41.7614, -88.2381),
        "60505": (41.7606, -88.3201),
        "60506": (41.7606, -88.3201),
        "60510": (41.8500, -88.3126),
    }

    return fallback.get(zip_code)


def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _water_species_ids(water: dict[str, Any]) -> list[str]:
    ids = water.get("species_ids")
    if isinstance(ids, list) and ids:
        return [_species_id(x) for x in ids if _species_id(x)]

    species = water.get("species", [])
    if isinstance(species, list):
        return [_species_id(x) for x in species if _species_id(x)]

    return []


def _choose_species(query_value: str, active_species: list[str]) -> list[str]:
    query_value = str(query_value or "").strip()

    if not query_value:
        return active_species[:]

    raw = re.split(r"[,;/|]+", query_value)
    selected = []

    for value in raw:
        sid = _species_id(value)
        if sid and sid not in selected:
            selected.append(sid)

    return selected or active_species[:]


def _display_species(sid: str, by_id: dict[str, dict[str, Any]]) -> str:
    item = by_id.get(sid)
    if item:
        return str(item.get("name") or sid.replace("-", " ").title())
    return sid.replace("-", " ").title()


def _score_water(
    water: dict[str, Any],
    selected_species: list[str],
    active_species: list[str],
    user_coords: tuple[float, float] | None,
    radius: float,
    season: str,
    rules: dict[str, Any],
) -> dict[str, Any] | None:
    lat = _safe_float(water.get("lat"))
    lon = _safe_float(water.get("lon"))

    distance = None
    if user_coords and lat is not None and lon is not None:
      distance = _distance_miles(user_coords[0], user_coords[1], lat, lon)
      if distance > radius:
          return None

    water_species = set(_water_species_ids(water))
    selected_set = set(selected_species)
    active_set = set(active_species)

    target_matches = sorted(water_species & selected_set)
    active_matches = sorted(water_species & active_set)

    seasonal_species = set((rules.get("seasonal_species_boosts") or {}).get(season, []))
    seasonal_matches = sorted(water_species & seasonal_species)

    score = 0.0
    reasons = []

    if distance is not None:
        distance_score = max(0.0, 35.0 - min(distance, 35.0))
        score += distance_score
        reasons.append(f"{distance:.1f} miles away")
    else:
        score += 8
        reasons.append("distance unavailable, kept as local database option")

    if target_matches:
        score += 28 * len(target_matches)
        reasons.append("matches selected species: " + ", ".join(target_matches))
    elif active_matches:
        score += 12 * len(active_matches)
        reasons.append("matches active species list")

    if seasonal_matches:
        score += 8 * min(len(seasonal_matches), 3)
        reasons.append(f"good {season} species overlap")

    water_type = str(water.get("type") or "").lower()
    if any(x in water_type for x in ["river", "creek"]):
        score += 4
        reasons.append("moving-water option")
    if any(x in water_type for x in ["lake", "pond", "reservoir"]):
        score += 4
        reasons.append("still-water option")

    local_score = _safe_float(water.get("local_score"))
    if local_score is not None:
        score += min(local_score, 20)

    out = dict(water)
    out["distance_miles"] = round(distance, 1) if distance is not None else None
    out["recommendation_score"] = round(score, 1)
    out["recommendation_reasons"] = reasons
    out["matched_species_ids"] = target_matches or active_matches
    out["seasonal_matches"] = seasonal_matches

    return out


def _score_rig(
    rig: dict[str, Any],
    selected_species: list[str],
    season: str,
    conditions: list[str],
    rules: dict[str, Any],
) -> dict[str, Any] | None:
    species_ids = rig.get("species_ids")
    if not isinstance(species_ids, list) or not species_ids:
        best_for = rig.get("best_for", [])
        if isinstance(best_for, list):
            species_ids = [_species_id(x) for x in best_for if _species_id(x)]
        else:
            species_ids = []

    selected_set = set(selected_species)
    matches = sorted(set(species_ids) & selected_set)

    score = 0.0
    reasons = []

    if matches:
        score += 30 * len(matches)
        reasons.append("fits selected species: " + ", ".join(matches))
    else:
        # Keep a few broad rigs alive, but score them lower.
        broad = {"worm", "minnow", "jig", "micro-jig", "spoon"}
        lure_id = str(rig.get("lure_id") or rig.get("id") or "")
        if lure_id in broad:
            score += 8
            reasons.append("broad utility rig")
        else:
            return None

    lure_id = str(rig.get("lure_id") or rig.get("id") or "")
    condition_boosts = rules.get("condition_lure_boosts") or {}

    for condition in conditions:
        boosted = set(condition_boosts.get(condition, []))
        if lure_id in boosted:
            score += 8
            reasons.append(f"works well for {condition}")

    rig_seasons = rig.get("season")
    if isinstance(rig_seasons, list) and season in rig_seasons:
        score += 5
        reasons.append(f"good {season} option")

    difficulty = str(rig.get("difficulty") or "").lower()
    if difficulty == "easy":
        score += 3
        reasons.append("easy setup")

    out = dict(rig)
    out["recommendation_score"] = round(score, 1)
    out["recommendation_reasons"] = reasons
    out["matched_species_ids"] = matches
    return out


def build_recommendations(
    zip_code: str = "60543",
    species_query: str = "",
    radius: float = 35.0,
    limit: int = 5,
    conditions: list[str] | None = None,
) -> dict[str, Any]:
    rules = _rules()
    by_id = _species_by_id()
    settings = _settings()
    active_species = settings["active_species"]
    selected_species = _choose_species(species_query, active_species)
    selected_species = [sid for sid in selected_species if sid in by_id or sid]
    season = _season_for_month()
    conditions = conditions or []

    user_coords = _get_coords(zip_code)

    scored_waters = []
    for water in _waters():
        if not isinstance(water, dict):
            continue
        scored = _score_water(
            water=water,
            selected_species=selected_species,
            active_species=active_species,
            user_coords=user_coords,
            radius=radius,
            season=season,
            rules=rules,
        )
        if scored:
            scored_waters.append(scored)

    scored_waters.sort(
        key=lambda w: (
            w.get("recommendation_score", 0),
            -1 * (w.get("distance_miles") if w.get("distance_miles") is not None else 9999),
        ),
        reverse=True,
    )

    scored_rigs = []
    for rig in _rigs():
        if not isinstance(rig, dict):
            continue
        scored = _score_rig(
            rig=rig,
            selected_species=selected_species,
            season=season,
            conditions=conditions,
            rules=rules,
        )
        if scored:
            scored_rigs.append(scored)

    scored_rigs.sort(key=lambda r: r.get("recommendation_score", 0), reverse=True)

    top_waters = scored_waters[:limit]
    top_rigs = scored_rigs[:limit]

    best_water = top_waters[0] if top_waters else None
    best_rig = top_rigs[0] if top_rigs else None

    selected_names = [_display_species(sid, by_id) for sid in selected_species]

    if best_water and best_rig:
        summary = f"Best bet near {zip_code}: {best_water.get('name')} with {best_rig.get('name')}."
    elif best_water:
        summary = f"Best water near {zip_code}: {best_water.get('name')}."
    elif best_rig:
        summary = f"Best rig option: {best_rig.get('name')}."
    else:
        summary = "No strong recommendation found yet. Try a larger radius or enable more species."

    next_actions = []
    if best_water:
        next_actions.append(f"Start with {best_water.get('name')} and check the detail page before leaving.")
    if best_rig:
        next_actions.append(f"Rig up: {best_rig.get('name')}.")
    if selected_names:
        next_actions.append("Target species: " + ", ".join(selected_names[:4]) + ("..." if len(selected_names) > 4 else ""))
    next_actions.append("Use your catch log after the trip so future versions can learn from your results.")

    return {
        "ok": True,
        "version": VERSION,
        "zip": zip_code,
        "radius_miles": radius,
        "limit": limit,
        "season": season,
        "conditions": conditions,
        "user_coords": {"lat": user_coords[0], "lon": user_coords[1]} if user_coords else None,
        "selected_species": selected_species,
        "selected_species_names": selected_names,
        "active_species": active_species,
        "summary": summary,
        "best_bet": {
            "water": best_water,
            "rig": best_rig,
        },
        "waters": top_waters,
        "rigs": top_rigs,
        "counts": {
            "waters_considered": len(scored_waters),
            "rigs_considered": len(scored_rigs),
            "species_profiles": len(by_id),
        },
        "next_actions": next_actions,
        "notes": [
            "v4.4 scores local waters, active species, seasonal patterns, distance, and rig compatibility.",
            "This is a recommendation layer, not a fishing guarantee.",
            "Future versions can improve this with catch-log learning and weather-specific scoring.",
        ],
    }


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _recommendations_page() -> str:
    return render_template("recommendations.html")


def register_recommendation_routes_v44(app):
    @app.route("/recommendations")
    def recommendations_page_v44():
        return _recommendations_page()

    @app.route("/api/recommendations")
    def recommendations_api_v44():
        zip_code = request.args.get("zip", "60543")
        species_query = request.args.get("species", "")
        radius = _safe_float(request.args.get("radius")) or 35.0

        try:
            limit = int(request.args.get("limit", "5"))
        except Exception:
            limit = 5

        limit = max(1, min(limit, 12))

        conditions_raw = request.args.get("conditions", "")
        conditions = [
            _slug(x)
            for x in re.split(r"[,;/|]+", conditions_raw)
            if _slug(x)
        ]

        data = build_recommendations(
            zip_code=zip_code,
            species_query=species_query,
            radius=radius,
            limit=limit,
            conditions=conditions,
        )
        return jsonify(data)

    @app.route("/api/recommendations/status")
    def recommendations_status_v44():
        return jsonify({
            "ok": True,
            "version": VERSION,
            "routes": [
                "/recommendations",
                "/api/recommendations",
                "/api/recommendations/status",
                "/api/recommendations/history",
                "/api/recommendations/feedback",
            ],
            "data": {
                "waters": len(_waters()),
                "species": len(_species_profiles()),
                "rigs": len(_rigs()),
                "rules_file": str(RULES_PATH),
            },
        })

    @app.route("/api/recommendations/history")
    def recommendations_history_api_v44():
        """Return persisted history only; live advice remains computed above."""
        authority = _recommendations_authority()
        if authority.effective_authority == "sqlite":
            try:
                rows = list_authoritative_recommendation_history(_recommendations_db_path())
                return jsonify({"ok": True, "authority": "sqlite", "records": rows, "count": len(rows)})
            except Exception as exc:
                return jsonify({"ok": False, "error": f"SQLite recommendation history read failed: {exc}"}), 500

        # A transition outage may use the historical report snapshots for a
        # visibly labelled emergency read only. It never permits JSON writes.
        rows = json_recommendation_history(REPORTS_DIR)
        source = "json" if authority.effective_authority == "json" else "json_emergency_read_fallback"
        return jsonify({
            "ok": True,
            "authority": authority.effective_authority,
            "source": source,
            "warning": authority.error,
            "records": rows,
            "count": len(rows),
        })

    @app.route("/api/recommendations/feedback", methods=["POST"])
    def recommendations_feedback_api_v44():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "POST a JSON object."}), 400
        try:
            authority = require_write_authority("recommendations", _recommendations_db_path())
            if authority != "sqlite":
                return jsonify({"ok": False, "error": "Recommendation feedback is available only after SQLite authority is enabled."}), 409
            raw_rating = payload.get("rating")
            rating = int(raw_rating) if raw_rating not in (None, "") else None
            feedback = record_recommendation_feedback(
                str(payload.get("recommendation_id") or payload.get("id") or ""),
                feedback_type=str(payload.get("feedback_type") or payload.get("type") or ""),
                rating=rating,
                notes=str(payload.get("notes") or ""),
                db_path=_recommendations_db_path(),
            )
            return jsonify({"ok": True, "authority": "sqlite", "feedback": feedback}), 201
        except AuthorityWriteError as exc:
            return jsonify({"ok": False, "error": str(exc), "authority": exc.resolution.effective_authority}), exc.http_status
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
