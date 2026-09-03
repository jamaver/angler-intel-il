"""Canonical, explainable fishing-pattern object for V7.10.

This module consumes normalized evidence only. It performs no network access,
does not apply personal ranking, and does not choose or reorder offerings.
"""
from __future__ import annotations

from typing import Any

from intelligence.offering_intelligence import PROFILES, infer_seasonal_stage, species_id

VALID_CONFIDENCE = {"high", "moderate", "limited", "exploratory", "unknown"}


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flow_state(water: dict[str, Any]) -> str | None:
    existing = str(water.get("flow_state") or "").strip().lower()
    if existing in {"falling", "stable", "rising", "rapidly_rising"}:
        return existing
    delta = _num(water.get("flow_6h_delta_pct"))
    if delta is None:
        delta = _num(water.get("flow_24h_delta_pct"))
    if delta is None:
        return None
    if delta >= 15:
        return "rapidly_rising"
    if delta >= 5:
        return "rising"
    if delta <= -5:
        return "falling"
    return "stable"


def _label(value: object, default: str = "unknown") -> str:
    return str(value or default).replace("_", " ").strip()


def _confidence(*, direct: bool = False, available: bool = False, inferred: bool = False) -> str:
    if direct:
        return "high"
    if available and not inferred:
        return "moderate"
    if inferred:
        return "limited"
    return "unknown"


def _activity(species: str, env: dict[str, Any], stage: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    air = env.get("air") or {}
    score = 52
    reasons = []
    cloud, wind = _num(air.get("cloud_pct")), _num(air.get("wind_mph"))
    pressure_delta = _num(air.get("pressure_6h_delta"))
    rain = _num(air.get("rain_24h_in"))
    flow = env.get("water") or {}
    flow_state = _flow_state(flow)
    if cloud is not None and cloud >= 45:
        score += 10; reasons.append("Cloud cover provides more opportunity for roaming or low-light activity.")
    elif cloud is not None and cloud <= 20:
        score -= 8; reasons.append("Bright conditions can reduce open-water roaming and favor tighter positions.")
    if wind is not None and 5 <= wind <= 15:
        score += 8; reasons.append("Moderate wind adds movement and can improve feeding opportunity.")
    elif wind is not None and wind < 3:
        score -= 5; reasons.append("Light wind provides less stimulus for a wide-area search pattern.")
    if pressure_delta is not None and pressure_delta <= -0.05:
        score += 8; reasons.append("Falling pressure supports a more active transition than a stable high-pressure pattern.")
    if rain is not None and rain >= 0.25:
        score += 4; reasons.append("Recent rain adds a meaningful environmental change to the feeding pattern.")
    if flow_state in {"rising", "rapidly_rising"}:
        score += 4; reasons.append("Rising flow can increase current-oriented and opportunistic feeding opportunities.")
    daypart = (env.get("solar") or {}).get("daypart")
    if daypart in {"dawn", "dusk"}:
        score += 7; reasons.append(f"The {daypart.replace('_', ' ')} window increases low-light feeding opportunity.")
    if daypart == "midday" and cloud is not None and cloud <= 25 and wind is not None and wind < 5:
        score -= 8; reasons.append("Bright, calm midday conditions reduce the case for extended roaming.")
    score = max(0, min(100, round(score)))
    state = "highly_active" if score >= 82 else "active" if score >= 70 else "moderate" if score >= 50 else "low" if score >= 30 else "inactive"
    return {"state": state, "score": score, "confidence": "moderate" if reasons else "limited", "why": reasons[:4]}


def _feeding(species: str, profile: dict[str, Any], activity: dict[str, Any], env: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    modes = list(profile.get("modes") or ["opportunistic"])
    daypart = (env.get("solar") or {}).get("daypart")
    water = env.get("water") or {}
    waterbody_type = str((env.get("waterbody") or {}).get("type") or "").lower()
    if _flow_state(water) in {"rising", "rapidly_rising"} and waterbody_type in {"river", "stream", "creek", "tailwater"} and "current_oriented" in modes and activity["score"] >= 45:
        primary = "current_oriented"
        alternates = [mode for mode in modes if mode != primary][:2]
        return {"primary": primary, "alternates": alternates, "confidence": "moderate" if profile else "limited", "why": ["Rising flow and the river context favor current-oriented holding and feeding."]}
    if activity["score"] < 40:
        primary = "ambushing" if "ambushing" in modes else "negative"
    elif daypart in {"dawn", "dusk"} and "chasing" in modes:
        primary = "chasing"
    elif daypart == "night" and "bottom_feeding" in modes:
        primary = "bottom_feeding"
    else:
        primary = modes[0]
    alternates = [mode for mode in modes if mode != primary][:2]
    why = [f"{_label(primary).title()} is the clearest interpretation of the current activity and daypart."]
    return {"primary": primary, "alternates": alternates, "confidence": "moderate" if profile else "limited", "why": why}


def _forage(species: str, profile: dict[str, Any], stage: dict[str, Any], env: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    direct = observed.get("forage") or observed.get("observed_forage")
    if isinstance(direct, list) and direct:
        values = [str(item).strip() for item in direct if str(item).strip()]
    elif isinstance(direct, str) and direct.strip():
        values = [direct.strip()]
    else:
        values = list(profile.get("forage") or ["baitfish", "invertebrates"])
    return {"primary": values[0], "alternates": values[1:3], "confidence": "high" if direct else "limited", "observed": bool(direct), "source": "direct_user" if direct else "species_stage_hypothesis"}


def _position(species: str, profile: dict[str, Any], activity: dict[str, Any], env: dict[str, Any], water: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    structures = observed.get("structure") or water.get("structure") or water.get("habitat")
    if isinstance(structures, str):
        structures = [part.strip().replace(" ", "_") for part in structures.replace(",", " ").split() if part.strip()]
    structures = [str(item).strip().replace(" ", "_") for item in structures] if isinstance(structures, list) else []
    direct_structure = bool(observed.get("structure"))
    preferred = [item for item in structures if item]
    daypart = (env.get("solar") or {}).get("daypart")
    if "open_water" in preferred or "mid_column" in preferred:
        horizontal, vertical = "open_water", "mid_column"
    elif activity["state"] in {"active", "highly_active"} and preferred:
        horizontal, vertical = "edge", "subsurface"
    elif preferred:
        horizontal, vertical = "edge", "subsurface"
    else:
        horizontal, vertical = "unknown", "unknown"
    if observed.get("vertical") in {"surface", "subsurface", "mid_column", "bottom", "suspended"}:
        vertical = observed["vertical"]
    elif species in {"crappie", "white-bass"} and not preferred and daypart in {"morning", "midday"}:
        vertical = "suspended"
    depth = "unknown" if not preferred else "shallow" if horizontal in {"shallow", "edge"} else "mid_to_bottom"
    return {"horizontal": horizontal, "vertical": vertical, "structure": preferred[:5], "depth_tendency": depth, "confidence": "high" if direct_structure else "moderate" if preferred else "limited", "fabricated_structure": False, "why": "Known water or angler structure was used." if preferred else "Structure context unavailable; no site structure was fabricated."}


def _presentation(activity: dict[str, Any], feeding: dict[str, Any], position: dict[str, Any], env: dict[str, Any]) -> dict[str, Any]:
    moving = feeding["primary"] in {"chasing", "schooling", "current_oriented"} or activity["state"] in {"active", "highly_active"}
    return {"pace": "medium" if moving else "slow", "coverage": "search" if moving else "targeted", "profile": "baitfish" if moving else "compact", "action": "active" if moving else "subtle", "cover_contact": "high" if position["structure"] else "low", "depth_zone": position["vertical"] if position["vertical"] != "unknown" else "unknown", "color_strategy": "contrast" if (_num((env.get("air") or {}).get("cloud_pct")) or 0) >= 60 else "natural", "scent_value": "useful" if feeding["primary"] in {"bottom_feeding", "opportunistic"} else "neutral"}


def build_pattern(species: object, environmental_context: dict[str, Any] | None, *, water_context: dict[str, Any] | None = None, behavioral_context: dict[str, Any] | None = None, observed_context: dict[str, Any] | None = None) -> dict[str, Any]:
    sid = species_id(species)
    profile = PROFILES.get(sid) or {}
    env = environmental_context if isinstance(environmental_context, dict) else {}
    water = water_context if isinstance(water_context, dict) else {}
    observed = observed_context if isinstance(observed_context, dict) else {}
    air = env.get("air") or {}
    water_data = env.get("water") or {}
    stage = infer_seasonal_stage(sid, date=(behavioral_context or {}).get("date"), air_temp_f=air.get("temp_f"), water_temp_f=water_data.get("temp_f"), air_temp_trend=air.get("air_temp_6h_delta"), water_temp_trend_f=water_data.get("temp_6h_delta_f"))
    flow_state = _flow_state(water_data)
    if flow_state:
        water_data = {**water_data, "flow_state": flow_state}
        env = {**env, "water": water_data}
    activity = _activity(sid, env, stage, observed)
    feeding = _feeding(sid, profile, activity, env, observed)
    forage = _forage(sid, profile, stage, env, observed)
    position = _position(sid, profile, activity, env, water, observed)
    presentation = _presentation(activity, feeding, position, env)
    direct_water = water_data.get("temp_f") is not None and water_data.get("temp_source") not in {None, "unknown"}
    direct_clarity = bool(observed.get("clarity"))
    direct_flow = water_data.get("flow_cfs") is not None
    dimensions = {"species_presence": "high" if water.get("species") else "moderate", "environment": "moderate" if air else "unknown", "seasonal_state": stage.get("confidence", "limited"), "feeding_mode": feeding["confidence"], "forage": forage["confidence"], "position": position["confidence"], "presentation": "moderate", "personal_evidence": "exploratory"}
    overall = "high" if sum(value == "high" for value in dimensions.values()) >= 3 else "moderate" if sum(value in {"high", "moderate"} for value in dimensions.values()) >= 4 else "limited"
    explanation = [f"{_label(stage.get('stage')).title()} {str(species or 'target fish')} conditions are the current best estimate.", *activity["why"][:2], f"Forage is {'directly observed' if forage['observed'] else 'inferred from species and seasonal behavior'}; the pattern favors a {_label(presentation['pace'])}, {_label(presentation['coverage'])} presentation."]
    fallbacks = []
    if not direct_water: fallbacks.append("water_temperature_unknown")
    if not position["structure"]: fallbacks.append("structure_unknown")
    if not air: fallbacks.append("environment_missing")
    return {"version": "v7.10-pattern-v1", "species": {"id": sid, "name": str(species or "Target species")}, "seasonal_state": {"stage": stage.get("stage"), "calendar_stage": stage.get("calendar_stage"), "confidence": stage.get("confidence"), "estimated": bool(stage.get("estimated", True)), "thermal_signal": stage.get("thermal_signal"), "water_temp_f": stage.get("water_temp_f"), "water_temp_trend_f": stage.get("water_temp_trend_f"), "evidence": stage.get("evidence_basis", [])}, "activity": activity, "feeding_mode": feeding, "forage": forage, "position": position, "presentation": presentation, "environment": {"daypart": (env.get("solar") or {}).get("daypart", "unknown"), "air_temp_f": air.get("temp_f"), "water_temp_f": water_data.get("temp_f"), "water_temp_source": water_data.get("temp_source", "unknown"), "wind_mph": air.get("wind_mph"), "wind_direction_deg": air.get("wind_direction_deg"), "cloud_pct": air.get("cloud_pct"), "pressure_trend": "falling" if (_num(air.get("pressure_6h_delta")) or 0) <= -0.05 else "rising" if (_num(air.get("pressure_6h_delta")) or 0) >= 0.05 else "stable_or_unknown", "rain_24h_in": air.get("rain_24h_in"), "flow_state": flow_state, "flow_6h_delta_pct": water_data.get("flow_6h_delta_pct"), "clarity": (env.get("waterbody") or {}).get("clarity")}, "confidence": {"overall": overall, "score": round(activity["score"] * 0.55 + (70 if direct_water else 45) * 0.2 + (70 if position["structure"] else 40) * 0.25), "dimensions": dimensions}, "explanation": explanation[:5], "data_quality": {"direct_water_temp": direct_water, "direct_clarity": direct_clarity, "direct_forage": forage["observed"], "direct_structure": bool(observed.get("structure")), "direct_flow": direct_flow, "usgs_used": any(item.get("provider") == "usgs" for item in (env.get("provenance") or {}).values() if isinstance(item, dict)), "noaa_used": "noaa" in (env.get("provenance") or {}), "fallbacks_used": fallbacks}, "personal_evidence": {"live_applied": False, "status": "shadow_only"}}
