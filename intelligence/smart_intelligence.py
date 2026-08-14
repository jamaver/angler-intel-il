from __future__ import annotations

from datetime import datetime
from typing import Any

from intelligence.lure_assets import resolve_lure_asset
from intelligence.species_condition_scoring import explainable_components, species_condition_components, weather_trend_intelligence


TRANSITION_DIRECTION = {
    "stage": "v4.6.1-hardening",
    "role": "transitional-intelligence-layer",
    "map_dashboard_planned": True,
    "sqlite_authority_allowed_after_migration": True,
    "requires_rollback_tools_before_sqlite_authority": True,
}


def _safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


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


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        n = float(value)
        if n != n:
            return None
        return n
    except Exception:
        return None


def clarity_signal(wind_mph: float | None, cloud_cover: float | None, area_type: str) -> dict[str, Any]:
    if wind_mph is None or cloud_cover is None:
        return {
            "label": "clarity unknown",
            "basis": "Weather inputs are incomplete, so actual water clarity must be verified on site.",
            "inferred": False,
        }

    if wind_mph >= 18:
        return {
            "label": "stained or wind-broken water likely",
            "basis": "Wind can reduce visibility and push bait toward wind-blown banks.",
            "inferred": True,
        }

    if wind_mph <= 6 and cloud_cover < 35 and area_type in ("lake", "pond", "reservoir"):
        return {
            "label": "clearer, calmer presentation likely",
            "basis": "Low wind and bright skies usually call for cleaner profiles and longer casts.",
            "inferred": True,
        }

    return {
        "label": "mixed clarity signal",
        "basis": "No direct clarity reading is available, so lure color should be adjusted on site.",
        "inferred": True,
    }


def _catch_history_signal(catch_insights: dict[str, Any] | None, zip_code: str, species: str) -> dict[str, Any]:
    insights = _safe_mapping(catch_insights)
    total = max(_safe_int(insights.get("total")), 0)
    local_total = max(_safe_int(insights.get("local_total")), 0)
    top_species = _safe_sequence(insights.get("top_species"))
    top_waterbodies = _safe_sequence(insights.get("top_waterbodies"))
    known_species = [
        item.get("name")
        for item in top_species
        if isinstance(item, dict) and item.get("name") and str(item.get("name")).strip().lower() != "unknown"
    ]
    known_waterbodies = [
        item.get("name")
        for item in top_waterbodies
        if isinstance(item, dict) and item.get("name") and str(item.get("name")).strip().lower() != "unknown"
    ]

    if local_total >= 5:
        strength = "strong"
    elif local_total >= 2:
        strength = "moderate"
    elif local_total == 1:
        strength = "light"
    elif total >= 5:
        strength = "moderate"
    elif total > 0:
        strength = "light"
    else:
        strength = "none"

    if local_total > 0:
        summary = f"{local_total} catch log entry(s) already exist for ZIP {zip_code}."
        weight = "Use local catch history as a tie-breaker, but do not let a tiny sample overpower current conditions."
        level = "local"
    elif total > 0:
        summary = f"{total} total catch log entry(s) are available across saved trips."
        weight = "Use broader catch patterns as a weak signal and keep current water conditions in front."
        level = "personal"
    else:
        summary = f"No catch history yet for {species}."
        weight = "Current weather, season, water type, and species behavior carry the recommendation."
        level = "starter"

    if local_total > 0 and local_total < 3:
        weight = "There is some local history, but the sample is small enough that current conditions should dominate."
    elif total > 0 and local_total == 0 and total < 5:
        weight = "There is some catch history, but the sample is small enough that it should only nudge the decision."

    if known_waterbodies:
        summary = f"{summary} Most recent waterbody signal: {known_waterbodies[0]}."
    elif known_species:
        summary = f"{summary} Top catch species signal: {known_species[0]}."

    return {
        "level": level,
        "summary": summary,
        "weight": weight,
        "strength": strength,
        "sample_size": {
            "total": total,
            "local": local_total,
        },
        "known_species": known_species[:5],
        "known_waterbodies": known_waterbodies[:5],
        "sample_quality": insights.get("sample_quality"),
    }


def _condition_labels(
    temp_f: float | None,
    wind_mph: float | None,
    pressure_inhg: float | None,
    cloud_cover: float | None,
) -> list[str]:
    labels: list[str] = []

    if temp_f is None:
        labels.append("temperature unknown")
    elif temp_f < 50:
        labels.append("cold-water pattern")
    elif temp_f > 82:
        labels.append("warm-water pattern")
    else:
        labels.append("moderate temperature")

    if wind_mph is None:
        labels.append("wind unknown")
    elif 5 <= wind_mph <= 15:
        labels.append("productive wind")
    elif wind_mph > 20:
        labels.append("heavy wind")
    else:
        labels.append("light wind")

    if pressure_inhg is None:
        labels.append("pressure unknown")
    elif pressure_inhg < 29.9:
        labels.append("lower pressure")
    elif pressure_inhg > 30.25:
        labels.append("high pressure")
    else:
        labels.append("stable pressure")

    if cloud_cover is None:
        labels.append("cloud cover unknown")
    elif cloud_cover >= 60:
        labels.append("cloud cover")
    elif cloud_cover <= 25:
        labels.append("bright sky")

    return labels


def _input_quality(weather: dict[str, Any] | None, best_bet: dict[str, Any] | None, best_time: dict[str, Any] | None) -> dict[str, Any]:
    original_weather = weather if isinstance(weather, dict) else {}
    weather = _safe_mapping(weather)
    best_bet = _safe_mapping(best_bet)
    best_time = _safe_mapping(best_time)

    required_weather = ("temp", "wind", "pressure", "cloud")
    missing = [key for key in required_weather if _safe_float(weather.get(key)) is None]
    if not best_bet:
        missing.append("best_bet")
    if not best_time:
        missing.append("best_time")

    return {
        "ok": not missing,
        "missing": missing,
        "source": original_weather.get("source", "unknown") if original_weather else "unknown",
        "fallback": bool(original_weather.get("fallback")) if original_weather else True,
    }


def _confidence_summary(
    input_quality: dict[str, Any],
    catch_signal: dict[str, Any],
    clarity: dict[str, Any],
) -> dict[str, Any]:
    missing = list(input_quality.get("missing") or [])
    score = 54

    if missing:
        score -= min(15, 3 * len(missing))
    else:
        score += 12

    strength = str(catch_signal.get("strength") or "none")
    if strength == "strong":
        score += 10
    elif strength == "moderate":
        score += 6
    elif strength == "light":
        score += 3

    if clarity.get("inferred"):
        score += 4

    if input_quality.get("fallback"):
        score -= 2

    score = max(0, min(100, int(round(score))))
    if score >= 75:
        level = "high"
    elif score >= 55:
        level = "moderate"
    else:
        level = "low"

    if missing:
        basis = f"Missing {', '.join(missing[:3])} reduces certainty, so this stays conservative."
    elif strength in ("strong", "moderate"):
        basis = "Weather, timing, and catch history are aligned well enough for a confident read."
    else:
        basis = "Weather and seasonal signals are present, but catch history is still thin."

    return {
        "score": score,
        "level": level,
        "label": level.title(),
        "basis": basis,
        "missing_inputs": missing[:5],
    }


def _signal_lists(
    temp_f: float | None,
    wind_mph: float | None,
    pressure_inhg: float | None,
    cloud_cover: float | None,
    catch_signal: dict[str, Any],
) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    caution: list[str] = []

    if temp_f is None:
        caution.append("Water temperature is missing from the feed.")
    elif 55 <= temp_f <= 75:
        positive.append("Water temperature is in a productive range.")
    elif temp_f < 50:
        caution.append("Cold water usually slows bait and calls for a slower presentation.")
    else:
        caution.append("Warm water may push fish shallow or toward shade.")

    if wind_mph is None:
        caution.append("Wind is missing from the feed.")
    elif 5 <= wind_mph <= 15:
        positive.append("Wind is in the productive range.")
    elif wind_mph > 20:
        caution.append("Heavy wind may require protected banks and heavier baits.")
    else:
        positive.append("Light wind keeps presentation control simple.")

    if pressure_inhg is None:
        caution.append("Pressure is missing from the feed.")
    elif pressure_inhg < 29.9:
        positive.append("Lower pressure can keep fish moving.")
    elif pressure_inhg > 30.25:
        caution.append("High pressure may slow the bite.")
    else:
        positive.append("Stable pressure leaves the pattern flexible.")

    if cloud_cover is None:
        caution.append("Cloud cover is missing from the feed.")
    elif cloud_cover >= 60:
        positive.append("Cloud cover can extend shallow feeding windows.")
    elif cloud_cover <= 25:
        caution.append("Bright sky can reward natural colors and shade lines.")
    else:
        positive.append("Mixed cloud cover gives room for multiple presentations.")

    strength = str(catch_signal.get("strength") or "none")
    if strength in ("strong", "moderate"):
        positive.append("Catch history is strong enough to help break ties.")
    elif strength == "light":
        caution.append("Catch history exists, but the sample is small.")
    else:
        caution.append("No catch history yet; current conditions should drive the first pass.")

    return positive[:4], caution[:4]


def _build_explanation_lines(
    *,
    confidence: dict[str, Any],
    clarity: dict[str, Any],
    catch_signal: dict[str, Any],
    water_type: str,
    species: str,
) -> list[str]:
    lines = [
        confidence["basis"],
        clarity["basis"],
        catch_signal["weight"],
        f"Targeting {species} on {water_type} keeps the recommendation tied to water type and season.",
    ]
    return lines


def _compact_list(values: list[str], limit: int = 3) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe_text(value, "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _explanation_sections(
    *,
    confidence: dict[str, Any],
    clarity: dict[str, Any],
    catch_signal: dict[str, Any],
    water_type: str,
    species: str,
    lure: str,
    best_bet: dict[str, Any],
    season: str,
    time_label: str,
) -> list[dict[str, Any]]:
    best_bet = _safe_mapping(best_bet)
    reasons = _compact_list([
        best_bet.get("why"),
        *(_safe_sequence(best_bet.get("reasons")) if isinstance(best_bet.get("reasons"), list) else []),
    ], limit=3)

    return [
        {
            "label": "Confidence",
            "value": confidence["label"],
            "why": confidence["basis"],
            "details": _compact_list([
                f"Score {confidence['score']}/100",
                "Use this as a confidence guide, not a guarantee.",
            ], limit=2),
        },
        {
            "label": "Target fit",
            "value": species,
            "why": f"Top species score is {best_bet.get('species_score', 'unknown')} with {season} and {water_type} context.",
            "details": _compact_list([
                f"Best time: {time_label}",
                f"Lure plan: {lure}",
            ], limit=2),
        },
        {
            "label": "Water fit",
            "value": clarity["label"],
            "why": clarity["basis"],
            "details": _compact_list([
                f"Water type: {water_type}",
                "Adjust lure color on site if clarity looks different.",
            ], limit=2),
        },
        {
            "label": "Catch history",
            "value": catch_signal["level"],
            "why": catch_signal["weight"],
            "details": _compact_list([
                catch_signal["summary"],
                f"Sample size: {catch_signal.get('sample_size', {}).get('local', 0)} local / {catch_signal.get('sample_size', {}).get('total', 0)} total",
            ], limit=2),
        },
        {
            "label": "Presentation",
            "value": lure,
            "why": reasons[0] if reasons else "Chosen from the current lure plan.",
            "details": reasons[1:] if len(reasons) > 1 else [best_bet.get("speed") or "Presentation guidance"],
        },
    ]


def _base_payload(
    *,
    ok: bool,
    error: str | None,
    zip_code: str,
    location: dict[str, Any] | None,
    weather: dict[str, Any] | None,
    area_type: str,
    best_bet: dict[str, Any] | None,
    best_time: dict[str, Any] | None,
    catch_insights: dict[str, Any] | None,
) -> dict[str, Any]:
    safe_location = _safe_mapping(location)
    safe_weather = _safe_mapping(weather)
    safe_best_bet = _safe_mapping(best_bet)
    safe_best_time = _safe_mapping(best_time)
    safe_catch_insights = _safe_mapping(catch_insights)

    temp_f = _safe_float(safe_weather.get("temp"))
    wind_mph = _safe_float(safe_weather.get("wind"))
    pressure_inhg = _safe_float(safe_weather.get("pressure"))
    cloud_cover = _safe_float(safe_weather.get("cloud"))
    season = season_for_month()
    daypart = time_of_day_for_hour()
    species = _safe_text(safe_best_bet.get("species"), "Target species")
    lure = _safe_text(safe_best_bet.get("lure_name"), "general-purpose lure")
    lure_asset = resolve_lure_asset(
        recommendation_text=lure,
        lure_type=safe_best_bet.get("lure_type"),
        color=safe_best_bet.get("lure_color"),
    )
    water_type = _safe_text(area_type, "nearby water")
    best_time_label = _safe_text(safe_best_time.get("label"), daypart.title())
    catch_signal = _catch_history_signal(safe_catch_insights, zip_code, species)
    clarity = clarity_signal(wind_mph, cloud_cover, water_type)
    labels = _condition_labels(temp_f, wind_mph, pressure_inhg, cloud_cover)
    input_quality = _input_quality(safe_weather, safe_best_bet, safe_best_time)
    confidence = _confidence_summary(input_quality, catch_signal, clarity)
    species_conditions = species_condition_components(
        species, temp_f=temp_f, wind_mph=wind_mph, pressure_inhg=pressure_inhg,
        cloud_cover=cloud_cover, season=season, water_type=water_type,
    )
    component_scoring = explainable_components(
        species_conditions,
        water_fit=safe_best_bet.get("species_score"),
        timing_fit=safe_best_time.get("score"),
        presentation_fit=safe_best_bet.get("species_score"),
    )
    weather_trends = weather_trend_intelligence(safe_weather.get("hourly") or safe_weather.get("hourly_forecast"))
    positive_signals, caution_signals = _signal_lists(
        temp_f,
        wind_mph,
        pressure_inhg,
        cloud_cover,
        catch_signal,
    )

    if safe_location.get("city") or safe_location.get("state"):
        location_label = ", ".join(
            part
            for part in (safe_location.get("city"), safe_location.get("state"))
            if part
        )
    else:
        location_label = f"ZIP {zip_code}" if zip_code else "Unknown location"

    species_score_value = safe_best_bet.get("species_score")
    species_score_text = species_score_value if species_score_value not in (None, "") else "unknown"

    strategy = [
        f"Start with {species} during the {best_time_label.lower()} window.",
        f"Fish {water_type} edges first, then adjust based on water clarity and bait activity.",
    ]

    if input_quality["missing"]:
        strategy.append("Weather inputs are incomplete, so verify wind, pressure, and clarity on site before committing.")
    elif wind_mph is None:
        strategy.append("Weather feed is incomplete, so verify wind and water conditions before committing to a pattern.")
    elif wind_mph > 20:
        strategy.append("Use heavier or more compact presentations and favor protected banks.")
    elif 5 <= wind_mph <= 15:
        strategy.append("Check wind-blown banks, points, and current breaks before dead-calm areas.")

    if pressure_inhg is None:
        strategy.append("Pressure is unavailable, so let visible fish activity and recent local catches drive adjustments.")
    elif pressure_inhg > 30.25:
        strategy.append("Slow down after the first pass; high pressure often rewards finesse or precise casts.")
    elif pressure_inhg < 29.9:
        strategy.append("Cover water confidently while lower pressure keeps fish more willing to move.")

    if cloud_cover is None:
        strategy.append("Cloud cover is unavailable, so carry both natural and higher-contrast color options.")
    elif cloud_cover >= 60:
        strategy.append("Keep moving baits in play longer because cloud cover can extend shallow feeding.")
    elif cloud_cover <= 25:
        strategy.append("Use natural colors, shade, depth changes, and longer casts in bright conditions.")

    recommendations = [
        {
            "label": "Primary target",
            "value": species,
            "why": f"Top species score is {species_score_text} with {season} and {water_type} context.",
        },
        {
            "label": "Primary lure",
            "value": lure,
            "why": safe_best_bet.get("why") or "Chosen from the existing lure plan for the top species.",
        },
        {
            "label": "Water approach",
            "value": water_type,
            "why": clarity["basis"],
        },
        {
            "label": "Confidence",
            "value": confidence["label"],
            "why": confidence["basis"],
        },
        {
            "label": "Catch history",
            "value": catch_signal["level"],
            "why": catch_signal["weight"],
        },
    ]

    explanation = _build_explanation_lines(
        confidence=confidence,
        clarity=clarity,
        catch_signal=catch_signal,
        water_type=water_type,
        species=species,
    )

    explanation_sections = _explanation_sections(
        confidence=confidence,
        clarity=clarity,
        catch_signal=catch_signal,
        water_type=water_type,
        species=species,
        lure=lure,
        best_bet=safe_best_bet,
        season=season,
        time_label=best_time_label,
    )

    ranking_factors = [
        {
            "label": section["label"],
            "value": section["value"],
            "why": section["why"],
        }
        for section in explanation_sections
    ]

    decision_factors = [
        f"{section['label']}: {section['why']}"
        for section in explanation_sections
        if section.get("why")
    ]

    if positive_signals:
        explanation.insert(1, positive_signals[0])
    if caution_signals:
        explanation.append(caution_signals[0])

    payload: dict[str, Any] = {
        "ok": ok,
        "version": "v4.6-smart-intelligence",
        "hardened_version": "v4.6.1-smart-intelligence-hardening",
        "scope": "national-zip-weather-with-local-water-context",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "transition_direction": TRANSITION_DIRECTION,
        "input_quality": input_quality,
        "location_label": location_label,
        "season": season,
        "time_of_day": daypart,
        "condition_labels": labels,
        "clarity_signal": clarity,
        "headline": f"{season.title()} {water_type} pattern for {species}",
        "summary": (
            f"Target {species} with {lure}. The recommendation blends weather, wind, "
            f"pressure, cloud cover, season, water type, lure fit, confidence, and catch-history signal."
        ),
        "confidence": confidence,
        "species_condition_scoring": species_conditions,
        "component_scoring": component_scoring,
        "weather_trends": weather_trends,
        "ranking_factors": ranking_factors,
        "explanation_sections": explanation_sections,
        "decision_factors": decision_factors,
        "explanation": explanation,
        "positive_signals": positive_signals,
        "caution_signals": caution_signals,
        "strategy": strategy,
        "recommendations": recommendations,
        "catch_history": catch_signal,
        "lure_recommendation": lure_asset,
        "next_actions": [
            "Open Smart Picks for water and rig detail before leaving.",
            "Log catches after the trip so future intelligence can learn from results.",
            "Adjust lure color on site when actual water clarity differs from the inferred signal.",
        ],
    }

    if error:
        payload["errors"] = [error]
    return payload


def build_smart_intelligence(
    *,
    zip_code: str,
    location: dict[str, Any] | None,
    weather: dict[str, Any] | None,
    area_type: str,
    best_bet: dict[str, Any] | None,
    best_time: dict[str, Any] | None,
    catch_insights: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Deterministic fishing-intelligence summary for the dashboard.

    This is a recommendation layer built from existing JSON/API inputs. It does
    not write data, does not use SQLite as authority, and does not replace Smart
    Picks.
    """
    return _base_payload(
        ok=True,
        error=None,
        zip_code=zip_code,
        location=location,
        weather=weather,
        area_type=area_type,
        best_bet=best_bet,
        best_time=best_time,
        catch_insights=catch_insights,
    )


def build_smart_intelligence_fallback(
    *,
    zip_code: str,
    location: dict[str, Any] | None,
    weather: dict[str, Any] | None,
    area_type: str,
    best_bet: dict[str, Any] | None,
    best_time: dict[str, Any] | None,
    catch_insights: dict[str, Any] | None,
    error: str | None = None,
) -> dict[str, Any]:
    """Return a conservative payload when the main smart-intelligence build fails."""
    payload = _base_payload(
        ok=False,
        error=error or "Smart Intelligence fallback engaged after a build error.",
        zip_code=zip_code,
        location=location,
        weather=weather,
        area_type=area_type,
        best_bet=best_bet,
        best_time=best_time,
        catch_insights=catch_insights,
    )
    payload["confidence"] = {
        "score": 0,
        "level": "low",
        "label": "Low",
        "basis": "Fallback intelligence was used because the main builder hit an error.",
        "missing_inputs": payload.get("input_quality", {}).get("missing", []),
    }
    payload["summary"] = (
        "Smart Intelligence fallback is active. Use the rest of the dashboard and "
        "local conditions while the intelligence path is rechecked."
    )
    payload["headline"] = "Smart Intelligence fallback"
    payload["positive_signals"] = []
    payload["caution_signals"] = [
        "The intelligence build failed and the fallback payload is being used.",
    ]
    payload["explanation"] = [
        payload["confidence"]["basis"],
        "Refresh the search after the data path is verified.",
    ]
    payload["strategy"] = [
        "Use the rest of the dashboard and local conditions as the source of truth for now.",
        "Refresh weather and re-open the waterbody once the signal path is stable.",
    ]
    payload["next_actions"] = [
        "Check the service logs for the intelligence error.",
        "Retry the search after the data feed is restored.",
    ]
    return payload
