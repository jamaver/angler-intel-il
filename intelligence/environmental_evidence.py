"""Provider-neutral environmental evidence contracts for V7.9.

Values are observations or forecasts, never personal-data authority. This
module contains normalization only; provider adapters remain outside it.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

QUALITY = {"direct_user", "direct_same_water", "direct_nearby", "agency_recent", "forecast", "model_guidance", "estimated", "historical", "stale", "unknown"}


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(values: list[object], index: int, hours: int) -> float | None:
    if index < hours or index >= len(values):
        return None
    current, previous = _number(values[index]), _number(values[index - hours])
    return round(current - previous, 2) if current is not None and previous is not None else None


def _sum(values: list[object], start: int, end: int) -> float:
    return round(sum((_number(item) or 0) for item in values[start:end]), 2)


def _current_index(times: list[object], current_time: object) -> int | None:
    if not times:
        return None
    target = str(current_time or "")
    if target in times:
        return times.index(target)
    prefix = target[:13]
    for index, value in enumerate(times):
        if str(value)[:13] == prefix:
            return index
    return None


def _c_to_f(value: object) -> float | None:
    number = _number(value)
    return round(number * 9 / 5 + 32, 1) if number is not None else None


def _quality(provider: str, source: str = "") -> str:
    if source in QUALITY:
        return source
    return {"open-meteo": "forecast", "usgs": "direct_nearby", "noaa": "model_guidance", "user": "direct_user"}.get(provider, "unknown")


def _solar_daypart(timestamp: object, sunrise: object, sunset: object) -> dict[str, Any]:
    try:
        now = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")) if timestamp else datetime.now().astimezone()
        rise = datetime.fromisoformat(str(sunrise).replace("Z", "+00:00"))
        set_ = datetime.fromisoformat(str(sunset).replace("Z", "+00:00"))
        if now.tzinfo is None: now = now.replace(tzinfo=rise.tzinfo)
        if rise.tzinfo is None: rise = rise.replace(tzinfo=now.tzinfo)
        if set_.tzinfo is None: set_ = set_.replace(tzinfo=now.tzinfo)
        from_rise = (now - rise).total_seconds() / 60
        to_set = (set_ - now).total_seconds() / 60
        if from_rise < -45: label = "pre_dawn"
        elif from_rise < 45: label = "dawn"
        elif now < rise.replace(hour=11, minute=0): label = "morning"
        elif now < set_ - timedelta(hours=4, minutes=30): label = "midday"
        elif to_set > 45: label = "late_afternoon"
        elif to_set >= -45: label = "dusk"
        else: label = "night"
        return {"daypart": label, "sunrise": sunrise, "sunset": sunset, "minutes_from_sunrise": round(from_rise), "minutes_to_sunset": round(to_set), "source": "solar"}
    except (TypeError, ValueError, OverflowError):
        return {"daypart": "morning", "sunrise": sunrise, "sunset": sunset, "minutes_from_sunrise": None, "minutes_to_sunset": None, "source": "clock_fallback"}


def normalize_open_meteo(payload: object, *, timestamp: object = None, waterbody: dict[str, Any] | None = None, direct_observation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize Open-Meteo while explicitly treating temperature_2m as air."""
    payload = payload if isinstance(payload, dict) else {}
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    hourly = payload.get("hourly") if isinstance(payload.get("hourly"), dict) else {}
    times = hourly.get("time") if isinstance(hourly.get("time"), list) else []
    current_time = timestamp or current.get("time") or (times[0] if times else None)
    current_index = _current_index(times, current_time)
    air_temp = _c_to_f(current.get("temperature_2m"))
    wind = _number(current.get("wind_speed_10m"))
    pressure = _number(current.get("pressure_msl"))
    rain = hourly.get("rain") if isinstance(hourly.get("rain"), list) else hourly.get("precipitation", [])
    rain = rain if isinstance(rain, list) else []
    pressure_values = hourly.get("pressure_msl", []) if isinstance(hourly.get("pressure_msl"), list) else []
    temp_values = hourly.get("temperature_2m", []) if isinstance(hourly.get("temperature_2m"), list) else []
    water_temp = None
    water_source = "unknown"
    if isinstance(direct_observation, dict) and _number(direct_observation.get("water_temp_f")) is not None:
        water_temp = _number(direct_observation.get("water_temp_f")); water_source = "direct_user"
    daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
    sunrise = (daily.get("sunrise") or [None])[0] if isinstance(daily.get("sunrise"), list) else daily.get("sunrise")
    sunset = (daily.get("sunset") or [None])[0] if isinstance(daily.get("sunset"), list) else daily.get("sunset")
    observation = direct_observation if isinstance(direct_observation, dict) else {}
    clarity = observation.get("clarity") or "unknown"
    past_index = current_index if current_index is not None else 0
    result = {
        "air": {"temp_f": air_temp, "humidity_pct": _number(current.get("relative_humidity_2m")), "pressure_inhg": round(pressure * 0.02953, 2) if pressure is not None else None, "pressure_3h_delta": round((_delta(pressure_values, past_index, 3) or 0) * 0.02953, 3) if past_index >= 3 else None, "pressure_6h_delta": round((_delta(pressure_values, past_index, 6) or 0) * 0.02953, 3) if past_index >= 6 else None, "air_temp_3h_delta": round((_delta(temp_values, past_index, 3) or 0) * 9 / 5, 2) if past_index >= 3 else None, "air_temp_6h_delta": round((_delta(temp_values, past_index, 6) or 0) * 9 / 5, 2) if past_index >= 6 else None, "wind_mph": round((wind or 0) * 0.621371, 1) if wind is not None else None, "wind_gust_mph": round((_number(current.get("wind_gusts_10m")) or 0) * 0.621371, 1) if current.get("wind_gusts_10m") is not None else None, "wind_direction_deg": _number(current.get("wind_direction_10m")), "cloud_pct": _number(current.get("cloud_cover")), "rain_6h_in": round(_sum(rain, max(0, past_index - 6), past_index) * 0.0393701, 3) if past_index >= 1 else None, "rain_24h_in": round(_sum(rain, max(0, past_index - 24), past_index) * 0.0393701, 3) if past_index >= 1 else None, "rain_next_6h_in": round(_sum(rain, past_index, past_index + 6) * 0.0393701, 3), "rain_next_12h_in": round(_sum(rain, past_index, past_index + 12) * 0.0393701, 3)},
        "water": {"temp_f": water_temp, "temp_source": water_source, "flow_cfs": _number(observation.get("flow_cfs")), "gage_height_ft": _number(observation.get("gage_height_ft")), "turbidity": None, "dissolved_oxygen_mg_l": None},
        "solar": _solar_daypart(current_time, sunrise, sunset),
        "waterbody": {"id": (waterbody or {}).get("id"), "name": (waterbody or {}).get("name"), "type": (waterbody or {}).get("type"), "clarity": clarity, "clarity_source": "user" if observation.get("clarity") else "unknown"},
        "provenance": {"air": {"provider": "open-meteo", "quality": "forecast", "observed_at": current_time}, "water_temp": {"provider": "user" if water_temp is not None else "none", "quality": water_source, "observed_at": current_time}},
        "warnings": []
    }
    if air_temp is None: result["warnings"].append("Air temperature unavailable.")
    if water_temp is None: result["warnings"].append("Direct water temperature is unavailable; air temperature was not substituted.")
    if not times: result["warnings"].append("Hourly weather observations unavailable.")
    return result


def build_environmental_context(*, waterbody: dict[str, Any] | None = None, weather_payload: dict[str, Any] | None = None, usgs_payload: dict[str, Any] | None = None, noaa_payload: dict[str, Any] | None = None, direct_observation: dict[str, Any] | None = None, timestamp: object = None) -> dict[str, Any]:
    """Build one provider-neutral context from already-fetched provider data."""
    context = normalize_open_meteo(weather_payload or {}, timestamp=timestamp, waterbody=waterbody, direct_observation=direct_observation)
    usgs = usgs_payload if isinstance(usgs_payload, dict) else {}
    measurements = usgs.get("measurements") if isinstance(usgs.get("measurements"), dict) else {}
    for name, target, unit in (("water_temp", "temp_f", "F"), ("flow", "flow_cfs", "cfs"), ("gage_height", "gage_height_ft", "ft")):
        item = measurements.get(name) if isinstance(measurements.get(name), dict) else None
        if item and item.get("value") is not None:
            value = float(item["value"])
            if name == "water_temp" and str(item.get("unit", "")).lower() in {"deg c", "c", "celsius"}: value = value * 9 / 5 + 32
            context["water"][target] = round(value, 2)
            context["water"]["temp_source" if name == "water_temp" else target + "_source"] = "usgs"
            context["provenance"][target] = item.get("provenance", {"provider": "usgs", "quality": "direct_nearby"})
    if noaa_payload:
        context["water"]["noaa_forecast"] = noaa_payload
        context["provenance"]["noaa"] = {"provider": "noaa", "quality": "model_guidance"}
    return context
