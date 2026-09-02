"""Explainable behavioral offering selection for V7.9.

This is reference-driven heuristic guidance, not a biological model or live
personalization layer. It deliberately keeps measured air temperature and
water temperature separate.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence.lure_assets import resolve_lure_asset

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "data" / "species_behavior_profiles.json"
OFFERING_PATH = ROOT / "data" / "fishing_offerings.json"


def _load(path: Path, default: Any) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


PROFILES = _load(PROFILE_PATH, {})
OFFERINGS = _load(OFFERING_PATH, [])
COMPATIBILITY = {
    "jig": {"species_ids": ["largemouth-bass", "smallmouth-bass", "crappie", "bluegill", "walleye", "sauger", "white-bass", "northern-pike", "rainbow-trout"], "avoid_species_ids": ["common-carp", "channel-catfish"]},
    "spinnerbait": {"species_ids": ["largemouth-bass", "smallmouth-bass", "white-bass", "northern-pike", "walleye"], "avoid_species_ids": ["common-carp", "channel-catfish", "bluegill"]},
    "soft-plastic-worm": {"species_ids": ["largemouth-bass", "smallmouth-bass", "crappie", "bluegill", "walleye", "sauger", "common-carp", "channel-catfish"], "avoid_species_ids": ["rainbow-trout"]},
    "crankbait": {"species_ids": ["largemouth-bass", "smallmouth-bass", "walleye", "white-bass", "northern-pike"], "avoid_species_ids": ["common-carp", "channel-catfish", "bluegill"]},
    "topwater-popper": {"species_ids": ["largemouth-bass", "smallmouth-bass", "bluegill", "northern-pike", "white-bass"], "avoid_species_ids": ["channel-catfish", "common-carp"]},
    "spoon": {"species_ids": ["smallmouth-bass", "walleye", "sauger", "white-bass", "northern-pike", "rainbow-trout"], "avoid_species_ids": ["common-carp", "channel-catfish"]},
    "minnow": {"species_ids": ["crappie", "walleye", "sauger", "white-bass", "smallmouth-bass", "rainbow-trout", "channel-catfish"], "avoid_species_ids": ["common-carp"]},
    "shiner": {"species_ids": ["walleye", "sauger", "white-bass", "crappie", "northern-pike", "smallmouth-bass"], "avoid_species_ids": ["common-carp"]},
    "sweet-corn": {"species_ids": ["common-carp", "channel-catfish", "bluegill"], "avoid_species_ids": ["walleye", "sauger", "northern-pike"]},
    "bread-ball": {"species_ids": ["common-carp", "bluegill", "channel-catfish"], "avoid_species_ids": ["walleye", "sauger", "northern-pike"]},
    "dough-ball": {"species_ids": ["common-carp", "channel-catfish"], "avoid_species_ids": ["walleye", "sauger", "northern-pike"]},
    "nightcrawler": {"species_ids": ["common-carp", "channel-catfish", "bluegill", "walleye", "sauger", "rainbow-trout"], "avoid_species_ids": []},
    "crayfish": {"species_ids": ["largemouth-bass", "smallmouth-bass", "walleye", "sauger", "channel-catfish"], "avoid_species_ids": ["common-carp"]},
    "cut-bait": {"species_ids": ["channel-catfish", "northern-pike", "walleye"], "avoid_species_ids": ["bluegill", "common-carp"]},
}
COMPATIBILITY.update({
    "bread": {"species_ids": ["common-carp", "bluegill", "channel-catfish"], "avoid_species_ids": ["walleye", "sauger", "northern-pike"]},
    "hot-dog": {"species_ids": ["channel-catfish", "common-carp"], "avoid_species_ids": ["walleye", "sauger"]},
    "chicken-liver": {"species_ids": ["channel-catfish"], "avoid_species_ids": ["walleye", "sauger", "northern-pike"]},
    "chicken-heart-gizzard": {"species_ids": ["channel-catfish"], "avoid_species_ids": ["walleye", "sauger"]},
    "shrimp": {"species_ids": ["channel-catfish", "bluegill", "crappie"], "avoid_species_ids": ["walleye", "sauger"]},
    "cheese": {"species_ids": ["common-carp", "channel-catfish"], "avoid_species_ids": ["walleye", "sauger"]},
    "luncheon-meat": {"species_ids": ["common-carp", "channel-catfish"], "avoid_species_ids": ["walleye", "sauger"]},
    "pack-bait": {"species_ids": ["common-carp", "channel-catfish"], "avoid_species_ids": ["walleye", "sauger"]},
    "red-worm": {"species_ids": ["common-carp", "channel-catfish", "bluegill", "crappie"], "avoid_species_ids": ["walleye", "sauger"]},
    "waxworm": {"species_ids": ["bluegill", "crappie", "rainbow-trout"], "avoid_species_ids": ["channel-catfish", "common-carp"]},
    "mealworm": {"species_ids": ["bluegill", "crappie", "rainbow-trout"], "avoid_species_ids": ["channel-catfish", "common-carp"]},
    "leech": {"species_ids": ["walleye", "sauger", "smallmouth-bass", "channel-catfish"], "avoid_species_ids": ["common-carp"]},
})
for _offering in OFFERINGS:
    _offering.update(COMPATIBILITY.get(_offering.get("id"), {"species_ids": [], "avoid_species_ids": []}))
ALIASES = {
    "largemouth bass": "largemouth-bass", "smallmouth bass": "smallmouth-bass",
    "crappie": "crappie", "black crappie": "crappie", "white crappie": "crappie",
    "bluegill": "bluegill", "channel catfish": "channel-catfish", "catfish": "channel-catfish",
    "walleye": "walleye", "sauger": "sauger", "white bass": "white-bass",
    "northern pike": "northern-pike", "pike": "northern-pike", "rainbow trout": "rainbow-trout",
    "trout": "rainbow-trout", "common carp": "common-carp", "carp": "common-carp",
}


def species_id(value: object) -> str:
    key = " ".join(str(value or "").casefold().replace("_", " ").split())
    return ALIASES.get(key, key.replace(" ", "-") or "unknown")


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_daypart(*, timestamp: object = None, sunrise: object = None, sunset: object = None, hour: object = None) -> dict[str, Any]:
    dt = timestamp if isinstance(timestamp, datetime) else None
    if dt is None and isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            dt = None
    hour_value = dt.hour + dt.minute / 60 if dt else _num(hour)
    if hour_value is None:
        return {"daypart": "morning", "sunrise": sunrise, "sunset": sunset, "minutes_from_sunset": None, "source": "clock_fallback"}
    try:
        rise = datetime.fromisoformat(str(sunrise)).hour + datetime.fromisoformat(str(sunrise)).minute / 60 if sunrise else None
        set_ = datetime.fromisoformat(str(sunset)).hour + datetime.fromisoformat(str(sunset)).minute / 60 if sunset else None
    except ValueError:
        rise = set_ = None
    if rise is not None and set_ is not None:
        before_sunrise = (hour_value - rise) * 60
        from_sunset = (hour_value - set_) * 60
        if before_sunrise < -45: label = "pre_dawn"
        elif before_sunrise < 45: label = "dawn"
        elif hour_value < 11: label = "morning"
        elif hour_value < 16: label = "midday"
        elif from_sunset < -45: label = "late_afternoon"
        elif from_sunset < 45: label = "dusk"
        else: label = "night"
        return {"daypart": label, "sunrise": sunrise, "sunset": sunset, "minutes_from_sunset": round(from_sunset), "source": "solar"}
    if hour_value < 5: label = "pre_dawn"
    elif hour_value < 7: label = "dawn"
    elif hour_value < 11: label = "morning"
    elif hour_value < 15: label = "midday"
    elif hour_value < 19: label = "late_afternoon"
    elif hour_value < 21: label = "dusk"
    else: label = "night"
    return {"daypart": label, "sunrise": sunrise, "sunset": sunset, "minutes_from_sunset": None, "source": "clock_fallback"}


def infer_seasonal_stage(species: object, *, date: object = None, air_temp_f: object = None, water_temp_f: object = None, air_temp_trend: object = None) -> dict[str, Any]:
    sid = species_id(species)
    profile = PROFILES.get(sid) or {}
    dt = date if isinstance(date, datetime) else None
    if dt is None and isinstance(date, str):
        try: dt = datetime.fromisoformat(date[:10])
        except ValueError: dt = None
    month = dt.month if dt else datetime.now().month
    stage = next((name for name, months in (profile.get("stages") or {}).items() if month in months), "seasonal_transition")
    confidence = "moderate" if profile else "low"
    evidence = [f"calendar month {month}"]
    if water_temp_f is not None: evidence.append("direct water-temperature input")
    elif air_temp_f is not None: evidence.append("air temperature only; water stage remains estimated")
    if air_temp_trend: evidence.append(f"{air_temp_trend} air-temperature trend")
    return {"stage": stage, "confidence": confidence, "evidence_basis": evidence, "estimated": water_temp_f is None}


def _context(species: object, *, air_temp_f=None, wind_mph=None, pressure_inhg=None, cloud_cover=None, precipitation=False, water_type="", habitat=None, date=None, timestamp=None, sunrise=None, sunset=None, water_temp_f=None, water_temp_source="unknown") -> dict[str, Any]:
    sid = species_id(species)
    profile = PROFILES.get(sid) or {}
    daypart = infer_daypart(timestamp=timestamp, sunrise=sunrise, sunset=sunset, hour=(timestamp.hour if isinstance(timestamp, datetime) else None))
    stage = infer_seasonal_stage(sid, date=date or timestamp, air_temp_f=air_temp_f, water_temp_f=water_temp_f)
    wind = _num(wind_mph) or 0
    cloud = _num(cloud_cover)
    pressure = _num(pressure_inhg)
    habitat_text = " ".join(str(habitat or "").casefold().replace("_", " ").split())
    return {"species_id": sid, "profile": profile, "daypart": daypart, "stage": stage, "air_temp_f": _num(air_temp_f), "water_temp_f": _num(water_temp_f), "water_temp_source": water_temp_source if water_temp_f is not None else "unknown", "wind_mph": wind, "cloud_cover": cloud, "pressure_inhg": pressure, "precipitation": bool(precipitation), "water_type": str(water_type or ""), "habitat": habitat_text}


def rank_forage(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    forage = list(ctx["profile"].get("forage") or ["baitfish", "invertebrates"])
    if ctx["daypart"]["daypart"] in {"dawn", "dusk", "night"} and "baitfish" in forage:
        forage = ["baitfish"] + [x for x in forage if x != "baitfish"]
    if "rock" in ctx["habitat"] and "crayfish" in forage:
        forage = ["crayfish"] + [x for x in forage if x != "crayfish"]
    result = []
    for index, item in enumerate(forage[:4]):
        fit = max(55, 84 - index * 9)
        why = f"The {ctx['stage']['stage'].replace('_', ' ')} stage and {ctx['daypart']['daypart'].replace('_', ' ')} window support a {item.replace('_', ' ')}-oriented hypothesis."
        result.append({"forage": item, "fit": fit, "confidence": "moderate" if index == 0 else "limited", "why": why})
    return result


def feeding_modes(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    modes = list(ctx["profile"].get("modes") or ["opportunistic"])
    wind, cloud = ctx["wind_mph"], ctx["cloud_cover"]
    if ctx["daypart"]["daypart"] in {"dawn", "dusk"} and "chasing" in modes: modes = ["chasing"] + [m for m in modes if m != "chasing"]
    if cloud is not None and cloud < 25 and wind < 5 and "ambushing" in modes: modes = ["ambushing"] + [m for m in modes if m != "ambushing"]
    if ctx["daypart"]["daypart"] == "night" and "bottom_feeding" in modes: modes = ["bottom_feeding"] + [m for m in modes if m != "bottom_feeding"]
    return [{"mode": mode, "score": max(54, 86 - i * 11), "why": f"{mode.replace('_', ' ').title()} fits the current daypart and available species context."} for i, mode in enumerate(modes[:3])]


def fish_position(ctx: dict[str, Any], modes: list[dict[str, Any]]) -> dict[str, Any]:
    positions = list(ctx["profile"].get("positions") or ["edge", "open_water"])
    if "vegetation" in ctx["habitat"] and "vegetation" in positions: positions.insert(0, positions.pop(positions.index("vegetation")))
    if modes and modes[0]["mode"] == "bottom_feeding" and "bottom" not in positions: positions.insert(0, "bottom")
    primary = positions[0] if positions else "edge"
    return {"vertical_zone": "bottom" if primary in {"bottom", "deep", "dropoff"} else "subsurface", "structural_position": primary, "alternate_position": positions[1] if len(positions) > 1 else "edge", "why": "Position is inferred from species profile and supplied habitat context; unknown structure is not fabricated.", "confidence": "moderate" if ctx["profile"] else "low"}


def presentation_strategy(ctx: dict[str, Any], modes: list[dict[str, Any]], position: dict[str, Any]) -> dict[str, Any]:
    mode = modes[0]["mode"] if modes else "opportunistic"
    moving = mode in {"chasing", "schooling", "current_oriented"} or (ctx["wind_mph"] >= 6 and (ctx["cloud_cover"] or 0) >= 35)
    return {"pace": "medium" if moving else "slow", "coverage": "search" if moving else "targeted", "depth_zone": position["vertical_zone"], "cover_contact": "high" if position["structural_position"] not in {"open_water", "mid_column"} else "low", "profile": "compact" if not moving else "baitfish", "action": "subtle" if not moving else "active", "color_strategy": "contrast" if (ctx["cloud_cover"] or 0) >= 60 else "natural", "scent_value": "useful" if mode in {"bottom_feeding", "opportunistic"} else "neutral"}


def rank_offerings(ctx: dict[str, Any], forage: list[dict[str, Any]], modes: list[dict[str, Any]], position: dict[str, Any], presentation: dict[str, Any]) -> list[dict[str, Any]]:
    forage_ids = {x["forage"] for x in forage[:2]}
    mode_ids = {x["mode"] for x in modes[:2]}
    results = []
    for offering in OFFERINGS:
        score = 42
        compatible = ctx["species_id"] in offering.get("species_ids", [])
        avoided = ctx["species_id"] in offering.get("avoid_species_ids", [])
        if offering.get("species_ids") and not compatible:
            continue
        if avoided:
            continue
        species_fit = 24 if compatible else 0
        score += species_fit
        if forage_ids.intersection(offering.get("forage_classes") or []): score += 22
        if mode_ids.intersection(offering.get("feeding_modes") or []): score += 16
        if presentation["depth_zone"] in offering.get("vertical_zones", []): score += 8
        if presentation["pace"] == "slow" and offering.get("mobility") in {"stationary", "natural", "slow"}: score += 8
        if presentation["pace"] != "slow" and offering.get("mobility") == "moving": score += 7
        if ctx["species_id"] == "channel-catfish" and offering["id"] in {"cut-bait", "chicken-liver", "nightcrawler"}: score += 12
        if ctx["species_id"] in {"largemouth-bass", "northern-pike"} and offering["id"] in {"spinnerbait", "jig", "topwater-popper"}: score += 7
        if ctx["species_id"] in {"common-carp"} and offering["id"] in {"sweet-corn", "bread-ball", "dough-ball", "nightcrawler"}: score += 18
        stage = ctx["stage"]["stage"]
        if stage == "winter" and offering.get("mobility") in {"stationary", "natural", "slow"}: score += 10
        if stage in {"fall_feed", "fall", "fall_cooling"} and offering.get("mobility") == "moving": score += 7
        if stage in {"summer", "post_spawn"} and offering["id"] in {"spinnerbait", "crankbait", "topwater-popper"}: score += 5
        item = {"id": offering["id"], "name": offering["name"], "category": offering["category"], "score": min(100, score), "species_fit": species_fit, "why": f"Species compatibility and {presentation['pace']} {presentation['coverage']} presentation fit the {position['structural_position'].replace('_', ' ')} position.", "presentation": presentation, "regulation_check": offering.get("regulation_check", "check_local_rules"), "live_personal_evidence": {"live_applied": False, "status": "shadow_only"}}
        if offering["category"] == "artificial_lure":
            lure_type = {"jig": "jig", "spinnerbait": "spinnerbait", "crankbait": "crankbait", "topwater-popper": "topwater_popper", "spoon": "spoon"}.get(offering["id"], "soft_plastic_worm")
            item["image"] = resolve_lure_asset(lure_type=lure_type, recommendation_text=offering["name"]) ["path"]
        results.append(item)
    return sorted(results, key=lambda x: (-x["score"], x["id"]))[:8]


def _time_block_recommendations(ctx: dict[str, Any], forage: list[dict[str, Any]], position: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose practical windows while keeping each choice on the same pipeline."""
    blocks = [("dawn", "First light", "moving"), ("morning", "Morning", "adaptive"), ("midday", "Bright midday", "slow"), ("late_afternoon", "Late afternoon", "moving"), ("dusk", "Dusk", "moving"), ("night", "Night", "slow")]
    output = []
    for label, display, pace in blocks:
        local = dict(ctx)
        local["daypart"] = dict(ctx["daypart"], daypart=label)
        local["wind_mph"] = ctx["wind_mph"] if pace != "slow" else min(ctx["wind_mph"], 5)
        modes = feeding_modes(local)
        local_position = fish_position(local, modes)
        strategy = presentation_strategy(local, modes, local_position)
        ranked = rank_offerings(local, forage, modes, local_position, strategy)
        output.append({"daypart": label, "label": display, "best_offering": ranked[0] if ranked else None, "presentation": strategy, "why": ranked[0]["why"] if ranked else "No offering matched this window."})
    return output


def build_offering_intelligence(species: object, *, air_temp_f=None, water_temp_f=None, water_temp_source="unknown", wind_mph=None, pressure_inhg=None, cloud_cover=None, precipitation=False, water_type="", habitat=None, date=None, timestamp=None, sunrise=None, sunset=None) -> dict[str, Any]:
    ctx = _context(species, air_temp_f=air_temp_f, water_temp_f=water_temp_f, water_temp_source=water_temp_source, wind_mph=wind_mph, pressure_inhg=pressure_inhg, cloud_cover=cloud_cover, precipitation=precipitation, water_type=water_type, habitat=habitat, date=date, timestamp=timestamp, sunrise=sunrise, sunset=sunset)
    forage = rank_forage(ctx)
    modes = feeding_modes(ctx)
    position = fish_position(ctx, modes)
    presentation = presentation_strategy(ctx, modes, position)
    offerings = rank_offerings(ctx, forage, modes, position, presentation)
    return {"species_id": ctx["species_id"], "air_temp_f": ctx["air_temp_f"], "water_temp_f": ctx["water_temp_f"], "water_temp_source": ctx["water_temp_source"], "seasonal_stage": ctx["stage"], "daypart": ctx["daypart"], "forage_hypotheses": forage, "feeding_modes": modes, "fish_position": position, "presentation": presentation, "offerings": offerings, "time_block_recommendations": _time_block_recommendations(ctx, forage, position), "live_personal_evidence_applied": False, "note": "Heuristic offering guidance; direct water temperature and local structure were not assumed when unavailable."}
