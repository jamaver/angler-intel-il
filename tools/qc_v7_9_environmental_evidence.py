#!/usr/bin/env python3
"""Offline QC for the V7.9 environmental evidence contract."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from intelligence.environmental_evidence import build_environmental_context, normalize_open_meteo  # noqa: E402
from intelligence.offering_intelligence import build_offering_intelligence  # noqa: E402


def check(value, message):
    if not value:
        raise AssertionError(message)


def fixture():
    return {
        "current": {"time": "2026-09-02T18:00:00-05:00", "temperature_2m": 25, "relative_humidity_2m": 62, "dew_point_2m": 17, "wind_speed_10m": 14, "wind_gusts_10m": 24, "wind_direction_10m": 225, "pressure_msl": 1012, "cloud_cover": 58, "rain": 0.2, "weather_code": 2},
        "hourly": {"time": [f"2026-09-02T{h:02d}:00-05:00" for h in range(24)], "temperature_2m": [22 + h * .2 for h in range(24)], "pressure_msl": [1015 - h * .4 for h in range(24)], "rain": [0.1] * 24, "precipitation": [0.1] * 24},
        "daily": {"sunrise": ["2026-09-02T06:20:00-05:00"], "sunset": ["2026-09-02T19:20:00-05:00"]},
    }


def run():
    payload = fixture()
    result = normalize_open_meteo(payload, waterbody={"id": "river-1", "name": "Example River", "type": "river"})
    check(result["air"]["temp_f"] == 77.0, "air temperature was not converted to Fahrenheit")
    check(result["water"]["temp_f"] is None, "air temperature was substituted as water temperature")
    check(result["water"]["temp_source"] == "unknown", "missing water temperature lacks unknown source")
    check(result["provenance"]["air"]["provider"] == "open-meteo", "air provenance missing")
    check(result["solar"]["daypart"] == "late_afternoon", "solar daypart calculation failed")
    check(result["air"]["pressure_6h_delta"] is not None, "pressure trend missing")
    check(result["air"]["rain_6h_in"] < result["air"]["rain_24h_in"], "rain windows are not anchored to current hour")
    direct = normalize_open_meteo(payload, direct_observation={"water_temp_f": 68.4, "clarity": "stained"})
    check(direct["water"]["temp_f"] == 68.4 and direct["water"]["temp_source"] == "direct_user", "direct observation did not take precedence")
    check(direct["waterbody"]["clarity"] == "stained" and direct["waterbody"]["clarity_source"] == "user", "direct clarity was not preserved")
    empty = build_environmental_context(weather_payload={})
    check(empty["warnings"] and empty["water"]["temp_f"] is None, "empty provider payload did not degrade safely")
    walleye = build_offering_intelligence("Walleye", air_temp_f=68, wind_mph=5, pressure_inhg=30, cloud_cover=10, date="2026-07-15")
    check("sweet-corn" not in {item["id"] for item in walleye["offerings"]}, "species-incompatible corn ranked for walleye")
    check(ast.parse((ROOT / "app.py").read_text()), "app.py does not parse")
    check("AI_USGS_API_KEY" not in json.dumps(result), "credential material leaked into evidence")
    print("PASS: V7.9 environmental evidence QC")


if __name__ == "__main__":
    run()
