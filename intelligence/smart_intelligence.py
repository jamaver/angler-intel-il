from __future__ import annotations

from datetime import datetime
from typing import Any


def season_for_month(month: int | None = None) -> str:
    month = month or datetime.now().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def time_of_day_for_hour(hour: int | None = None) -> str:
    hour = datetime.now().hour if hour is None else hour
    if 5 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 16:
        return "midday"
    if 17 <= hour <= 21:
        return "evening"
    return "night"


def clarity_signal(wind_mph: float, cloud_cover: float, area_type: str) -> dict[str, str]:
    if wind_mph >= 18:
        return {
            "label": "stained or wind-broken water likely",
            "basis": "Wind can reduce visibility and push bait toward wind-blown banks.",
        }
    if wind_mph <= 6 and cloud_cover < 35 and area_type in ("lake", "pond", "reservoir"):
        return {
            "label": "clearer, calmer presentation likely",
            "basis": "Low wind and bright skies usually call for cleaner profiles and longer casts.",
        }
    return {
        "label": "mixed clarity signal",
        "basis": "No direct clarity reading is available, so lure color should be adjusted on site.",
    }


def _catch_history_signal(catch_insights: dict[str, Any], zip_code: str, species: str) -> dict[str, Any]:
    total = int(catch_insights.get("total") or 0)
    local_total = int(catch_insights.get("local_total") or 0)
    top_species = catch_insights.get("top_species") or []
    known_species = [
        item.get("name")
        for item in top_species
        if isinstance(item, dict) and item.get("name")
    ]

    if local_total > 0:
        return {
            "level": "local",
            "summary": f"{local_total} catch log entry(s) already exist for ZIP {zip_code}.",
            "weight": "Use local catch history as a tie-breaker when choosing species and lure.",
        }
    if total > 0:
        return {
            "level": "personal",
            "summary": f"{total} total catch log entry(s) are available across saved trips.",
            "weight": "Use your broader catch patterns, but verify them against current water type.",
        }
    return {
        "level": "starter",
        "summary": f"No catch history yet for {species}.",
        "weight": "Current weather, season, water type, and species behavior carry the recommendation.",
    }


def _condition_labels(temp_f: float, wind_mph: float, pressure_inhg: float, cloud_cover: float) -> list[str]:
    labels: list[str] = []

    if temp_f < 50:
        labels.append("cold-water pattern")
    elif temp_f > 82:
        labels.append("warm-water pattern")
    else:
        labels.append("moderate temperature")

    if 5 <= wind_mph <= 15:
        labels.append("productive wind")
    elif wind_mph > 20:
        labels.append("heavy wind")
    else:
        labels.append("light wind")

    if pressure_inhg < 29.9:
        labels.append("lower pressure")
    elif pressure_inhg > 30.25:
        labels.append("high pressure")
    else:
        labels.append("stable pressure")

    if cloud_cover >= 60:
        labels.append("cloud cover")
    elif cloud_cover <= 25:
        labels.append("bright sky")

    return labels


def build_smart_intelligence(
    *,
    zip_code: str,
    location: dict[str, Any],
    weather: dict[str, Any],
    area_type: str,
    best_bet: dict[str, Any],
    best_time: dict[str, Any],
    catch_insights: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic fishing-intelligence summary for the dashboard.

    This is a recommendation layer built from existing JSON/API inputs. It does
    not write data, does not use SQLite as authority, and does not replace Smart
    Picks.
    """
    temp_f = float(weather.get("temp") or 0)
    wind_mph = float(weather.get("wind") or 0)
    pressure_inhg = float(weather.get("pressure") or 0)
    cloud_cover = float(weather.get("cloud") or 0)
    season = season_for_month()
    daypart = time_of_day_for_hour()
    species = str(best_bet.get("species") or "target species")
    lure = str(best_bet.get("lure_name") or "confidence lure")
    water_type = area_type or "nearby water"
    clarity = clarity_signal(wind_mph, cloud_cover, water_type)
    catch_signal = _catch_history_signal(catch_insights, zip_code, species)
    labels = _condition_labels(temp_f, wind_mph, pressure_inhg, cloud_cover)

    strategy = []
    strategy.append(f"Start with {species} during the {best_time.get('label', daypart).lower()} window.")
    strategy.append(f"Fish {water_type} edges first, then adjust based on water clarity and bait activity.")

    if wind_mph > 20:
        strategy.append("Use heavier or more compact presentations and favor protected banks.")
    elif 5 <= wind_mph <= 15:
        strategy.append("Check wind-blown banks, points, and current breaks before dead-calm areas.")

    if pressure_inhg > 30.25:
        strategy.append("Slow down after the first pass; high pressure often rewards finesse or precise casts.")
    elif pressure_inhg < 29.9:
        strategy.append("Cover water confidently while lower pressure keeps fish more willing to move.")

    if cloud_cover >= 60:
        strategy.append("Keep moving baits in play longer because cloud cover can extend shallow feeding.")
    elif cloud_cover <= 25:
        strategy.append("Use natural colors, shade, depth changes, and longer casts in bright conditions.")

    recommendations = [
        {
            "label": "Primary target",
            "value": species,
            "why": f"Top species score is {best_bet.get('species_score')} with {season} and {water_type} context.",
        },
        {
            "label": "Primary lure",
            "value": lure,
            "why": best_bet.get("why") or "Chosen from the existing lure plan for the top species.",
        },
        {
            "label": "Water approach",
            "value": water_type,
            "why": clarity["basis"],
        },
        {
            "label": "Catch history",
            "value": catch_signal["level"],
            "why": catch_signal["weight"],
        },
    ]

    return {
        "ok": True,
        "version": "v4.6-smart-intelligence",
        "scope": "national-zip-weather-with-local-water-context",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "location_label": ", ".join(
            part for part in (location.get("city"), location.get("state")) if part
        ),
        "season": season,
        "time_of_day": daypart,
        "condition_labels": labels,
        "clarity_signal": clarity,
        "headline": f"{season.title()} {water_type} pattern for {species}",
        "summary": (
            f"Target {species} with {lure}. The recommendation blends weather, wind, "
            f"pressure, cloud cover, season, water type, lure fit, and catch-history signal."
        ),
        "strategy": strategy,
        "recommendations": recommendations,
        "catch_history": catch_signal,
        "next_actions": [
            "Open Smart Picks for water and rig detail before leaving.",
            "Log catches after the trip so future intelligence can learn from results.",
            "Adjust lure color on site when actual water clarity differs from the inferred signal.",
        ],
    }
