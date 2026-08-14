"""Broad, explainable species-condition scoring used by V7.7 intelligence.

Ranges are deliberately conservative guidance, not claims of biological precision.
"""
from __future__ import annotations

from typing import Any

PROFILES = {
    "largemouth bass": {"temp": (60, 78, 52, 84), "wind": (5, 15, 22), "cloud": (35, 90), "pressure": (29.9, 30.25)},
    "smallmouth bass": {"temp": (55, 72, 45, 78), "wind": (6, 18, 25), "cloud": (25, 85), "pressure": (29.85, 30.3)},
    "crappie": {"temp": (58, 75, 48, 82), "wind": (3, 12, 20), "cloud": (30, 90), "pressure": (29.85, 30.3)},
    "bluegill": {"temp": (62, 82, 52, 88), "wind": (2, 12, 20), "cloud": (20, 85), "pressure": (29.85, 30.35)},
    "channel catfish": {"temp": (70, 88, 55, 94), "wind": (2, 15, 25), "cloud": (20, 100), "pressure": (29.75, 30.35)},
    "walleye": {"temp": (50, 68, 40, 76), "wind": (5, 18, 28), "cloud": (45, 100), "pressure": (29.8, 30.2)},
    "northern pike": {"temp": (48, 68, 38, 76), "wind": (4, 16, 25), "cloud": (35, 95), "pressure": (29.8, 30.25)},
    "rainbow trout": {"temp": (45, 60, 35, 65), "wind": (1, 12, 20), "cloud": (30, 100), "pressure": (29.8, 30.3)},
    "white bass": {"temp": (55, 75, 45, 82), "wind": (4, 16, 25), "cloud": (30, 95), "pressure": (29.8, 30.3)},
    "sauger": {"temp": (45, 65, 35, 72), "wind": (4, 16, 25), "cloud": (35, 100), "pressure": (29.8, 30.25)},
}
DEFAULT = {"temp": (55, 75, 45, 85), "wind": (4, 14, 24), "cloud": (25, 90), "pressure": (29.85, 30.3)}


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _range_score(value: float | None, optimal: tuple[float, float], productive: tuple[float, float]) -> tuple[int, str]:
    if value is None:
        return 50, "Input unavailable; a neutral score is used."
    if optimal[0] <= value <= optimal[1]:
        return 85, "Inside the broad preferred range."
    if productive[0] <= value <= productive[1]:
        return 65, "Within a workable but less ideal range."
    return 35, "Outside the broad productive range."


def species_condition_components(species: object, *, temp_f: object = None, wind_mph: object = None,
                                 pressure_inhg: object = None, cloud_cover: object = None,
                                 season: object = None, water_type: object = None) -> dict[str, Any]:
    """Return bounded condition components without changing water or personal ranking."""
    label = str(species or "Target species").strip()
    profile = PROFILES.get(label.casefold(), DEFAULT)
    temp, wind, pressure, cloud = (_number(temp_f), _number(wind_mph), _number(pressure_inhg), _number(cloud_cover))
    temperature, temp_why = _range_score(temp, profile["temp"][:2], profile["temp"][2:])
    wind_score, wind_why = _range_score(wind, profile["wind"][:2], (0, profile["wind"][2]))
    cloud_score, cloud_why = _range_score(cloud, profile["cloud"], (0, 100))
    low_pressure, high_pressure = profile["pressure"]
    if pressure is None:
        pressure_score, pressure_why = 50, "Pressure unavailable; a neutral score is used."
    elif pressure < low_pressure:
        pressure_score, pressure_why = 78, "Below the cautious high-pressure range."
    elif pressure > high_pressure:
        pressure_score, pressure_why = 48, "Higher pressure can make the pattern more selective."
    else:
        pressure_score, pressure_why = 70, "Within a flexible pressure range."
    season_score = 75 if str(season or "").lower() in {"spring", "summer", "fall"} else 55
    water_score = 70 if str(water_type or "").strip() else 50
    components = {
        "temperature_fit": {"score": temperature, "why": f"{temp_f}F: {temp_why}" if temp is not None else temp_why},
        "wind_fit": {"score": wind_score, "why": f"{wind_mph} mph: {wind_why}" if wind is not None else wind_why},
        "pressure_fit": {"score": pressure_score, "why": pressure_why},
        "cloud_fit": {"score": cloud_score, "why": cloud_why},
        "season_fit": {"score": season_score, "why": "Season is a broad contextual fit, not a guarantee."},
        "water_type_fit": {"score": water_score, "why": "Water type is included as context; habitat detail remains in Water Intel."},
    }
    return {"species": label, "profile": "species-specific" if profile is not DEFAULT else "safe default",
            "components": components, "score": round(sum(item["score"] for item in components.values()) / len(components))}


def weather_trend_intelligence(hourly: object) -> dict[str, Any]:
    """Derive conservative movement labels from ordered hourly observations."""
    rows = hourly if isinstance(hourly, list) else []
    observations = [row for row in rows if isinstance(row, dict)]
    def delta(key: str, hours: int) -> float | None:
        if len(observations) < 2:
            return None
        recent = _number(observations[-1].get(key))
        prior = _number(observations[max(0, len(observations) - 1 - hours)].get(key))
        return round(recent - prior, 2) if recent is not None and prior is not None else None
    pressure_delta = delta("pressure", 6)
    temp_delta = delta("temp", 6)
    labels: list[str] = []
    if pressure_delta is not None:
        labels.append("falling-pressure pattern" if pressure_delta <= -0.05 else "rising-pressure/post-front pattern" if pressure_delta >= 0.05 else "stable pressure")
    if temp_delta is not None and abs(temp_delta) >= 2:
        labels.append("warming trend" if temp_delta > 0 else "cooling trend")
    return {"available": bool(labels), "pressure_6h_delta": pressure_delta, "temperature_6h_delta": temp_delta,
            "signals": labels, "confidence": "moderate" if labels else "low",
            "note": "Trend labels use measured forecast observations and are not a precise front diagnosis."}


def explainable_components(species_conditions: dict[str, Any], *, water_fit: object = None,
                           timing_fit: object = None, presentation_fit: object = None,
                           gear_fit: object = None) -> dict[str, Any]:
    """Provide a bounded weighted explanation while retaining independent confidence."""
    weather = float(species_conditions.get("score") or 50)
    components = {
        "species_activity": {"score": weather, "weight": 0.25},
        "water_fit": {"score": _number(water_fit) or 50, "weight": 0.20},
        "timing_fit": {"score": _number(timing_fit) or 50, "weight": 0.15},
        "weather_fit": {"score": weather, "weight": 0.20},
        "presentation_fit": {"score": _number(presentation_fit) or 50, "weight": 0.12},
        "gear_fit": {"score": _number(gear_fit) or 50, "weight": 0.08},
    }
    score = round(sum(item["score"] * item["weight"] for item in components.values()))
    return {"score": max(0, min(100, score)), "components": components,
            "live_personal_evidence_applied": False,
            "note": "Data confidence remains separate from this fishing-score explanation."}
