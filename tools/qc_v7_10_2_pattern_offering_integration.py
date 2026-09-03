#!/usr/bin/env python3
"""QC for bounded Pattern Object to offering integration."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from intelligence.offering_intelligence import build_offering_intelligence  # noqa: E402


def test_env(daypart="midday", *, air=72, cloud=40, wind=8, pressure=-.05, water=68, water_source="usgs", flow=None, kind="lake"):
    return {"air": {"temp_f": air, "cloud_pct": cloud, "wind_mph": wind, "pressure_6h_delta": pressure, "rain_24h_in": .2}, "water": {"temp_f": water, "temp_source": water_source, "flow_6h_delta_pct": flow}, "solar": {"daypart": daypart}, "waterbody": {"type": kind}, "provenance": {}}


def run():
    from intelligence.pattern_intelligence import build_pattern
    dawn_env = test_env("dawn", cloud=75, wind=10)
    pattern = build_pattern("Largemouth Bass", dawn_env, water_context={"type": "lake", "habitat": "vegetation"})
    baseline = build_offering_intelligence("Largemouth Bass", air_temp_f=72, water_temp_f=68, water_temp_source="usgs", wind_mph=10, cloud_cover=75)
    integrated = build_offering_intelligence("Largemouth Bass", air_temp_f=72, water_temp_f=68, water_temp_source="usgs", wind_mph=10, cloud_cover=75, pattern=pattern)
    assert integrated["pattern_integration"]["enabled"] is True
    assert len(integrated["plan_variants"]) == 3
    assert integrated["switch_triggers"]
    assert all(-5 <= item["pattern_adjustment"] <= 5 for item in integrated["offerings"])
    assert [x["id"] for x in baseline["offerings"]] == [x["id"] for x in build_offering_intelligence("Largemouth Bass", air_temp_f=72, water_temp_f=68, water_temp_source="usgs", wind_mph=10, cloud_cover=75)["offerings"]]
    assert all(item["live_personal_evidence"]["live_applied"] is False for item in integrated["offerings"])
    river = build_pattern("Smallmouth Bass", test_env("morning", flow=20, kind="river"), water_context={"type": "river", "habitat": "rock current_seam"})
    assert river["feeding_mode"]["primary"] == "current_oriented"
    assert ast.parse((ROOT / "app.py").read_text())
    print("PASS: V7.10.2 Pattern-aware offering integration QC")


if __name__ == "__main__":
    run()
