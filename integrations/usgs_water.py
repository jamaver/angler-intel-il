"""Optional USGS modern Water Data API adapter.

This module uses the current OGC API family only. It returns observations and
provenance; it does not write application data or alter authority markers.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

import requests

BASE_URL = "https://api.waterdata.usgs.gov/ogcapi/v0"
PARAMETERS = {
    "water_temp": "00010",
    "flow": "00060",
    "gage_height": "00065",
}


def settings() -> dict[str, Any]:
    return {
        "enabled": os.environ.get("AI_USGS_ENABLED", "1").strip().lower() not in {"0", "false", "no"},
        "api_key_configured": bool(os.environ.get("AI_USGS_API_KEY", "").strip()),
        "cache_seconds": int(os.environ.get("AI_USGS_CACHE_SECONDS", "900") or 900),
        "max_station_distance_miles": float(os.environ.get("AI_USGS_MAX_STATION_DISTANCE_MILES", "15") or 15),
    }


def _headers() -> dict[str, str]:
    key = os.environ.get("AI_USGS_API_KEY", "").strip()
    return {"X-Api-Key": key} if key else {}


def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))


def _request(collection: str, params: dict[str, Any], timeout: tuple[float, float] = (3.0, 8.0)) -> dict[str, Any]:
    response = requests.get(f"{BASE_URL}/collections/{collection}/items", params={"f": "json", **params}, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def health() -> dict[str, Any]:
    config = settings()
    if not config["enabled"]:
        return {"enabled": False, "status": "disabled", "credential_status": "not used"}
    try:
        _request("latest-continuous", {"limit": 1}, timeout=(2.0, 5.0))
        return {"enabled": True, "status": "ok", "credential_status": "configured" if config["api_key_configured"] else "anonymous"}
    except requests.RequestException as exc:
        return {"enabled": True, "status": "unavailable", "credential_status": "configured" if config["api_key_configured"] else "anonymous", "error": exc.__class__.__name__}


def discover_stations(latitude: float, longitude: float, *, radius_miles: float | None = None, parameter_code: str | None = None) -> list[dict[str, Any]]:
    """Find nearby latest-continuous records, preferring requested parameters."""
    config = settings()
    if not config["enabled"]:
        return []
    radius = radius_miles if radius_miles is not None else config["max_station_distance_miles"]
    lat_delta, lon_delta = radius / 69.0, radius / max(20.0, 69.0 * math.cos(math.radians(latitude)))
    params: dict[str, Any] = {"bbox": f"{longitude - lon_delta},{latitude - lat_delta},{longitude + lon_delta},{latitude + lat_delta}", "limit": 100}
    if parameter_code:
        params["parameter_code"] = parameter_code
    payload = _request("latest-continuous", params)
    results = []
    for feature in payload.get("features", []) if isinstance(payload.get("features"), list) else []:
        props = feature.get("properties") if isinstance(feature, dict) else {}
        geometry = feature.get("geometry") if isinstance(feature, dict) else {}
        coords = geometry.get("coordinates") if isinstance(geometry, dict) else []
        if not isinstance(props, dict) or not isinstance(coords, list) or len(coords) < 2:
            continue
        try:
            station_lat, station_lon = float(coords[1]), float(coords[0])
            distance = _distance_miles(latitude, longitude, station_lat, station_lon)
        except (TypeError, ValueError):
            continue
        if distance <= radius:
            results.append({"station_id": props.get("monitoring_location_number") or props.get("monitoring_location_id"), "name": props.get("monitoring_location_name") or "USGS monitoring location", "lat": station_lat, "lon": station_lon, "distance_miles": round(distance, 1), "parameter_code": props.get("parameter_code"), "available_parameters": [props.get("parameter_code")] if props.get("parameter_code") else [], "connection_quality": "direct_nearby", "observed_at": props.get("time")})
    return sorted(results, key=lambda item: (item["distance_miles"], str(item.get("station_id"))))


def latest_measurements(latitude: float, longitude: float) -> dict[str, Any]:
    """Return the closest available temp/flow/stage records with provenance."""
    measurements: dict[str, Any] = {}
    stations: dict[str, dict[str, Any]] = {}
    for name, code in PARAMETERS.items():
        try:
            candidates = discover_stations(latitude, longitude, parameter_code=code)
            if not candidates:
                continue
            station = candidates[0]
            stations[str(station.get("station_id"))] = station
            payload = _request("latest-continuous", {"monitoring_location_number": station.get("station_id"), "parameter_code": code, "limit": 1})
            feature = (payload.get("features") or [None])[0]
            props = feature.get("properties") if isinstance(feature, dict) else {}
            value = props.get("value") if isinstance(props, dict) else None
            if value is not None:
                measurements[name] = {"value": float(value), "unit": props.get("unit_of_measure"), "observed_at": props.get("time"), "provenance": {"provider": "usgs", "station_id": station.get("station_id"), "distance_miles": station.get("distance_miles"), "quality": "direct_nearby"}}
        except (requests.RequestException, TypeError, ValueError):
            continue
    return {"provider": "usgs", "measurements": measurements, "stations": list(stations.values()), "warnings": [] if measurements else ["No nearby USGS continuous measurements were available."]}
