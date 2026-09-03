#!/usr/bin/env python3
"""Focused QC for the V7.10 adaptive pattern refinement."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from intelligence.pattern_intelligence import build_pattern  # noqa: E402


def env(daypart="midday", *, air=72, cloud=45, wind=8, pressure=-0.02, water=None, water_source="unknown", water_delta=None, flow=None, rain=0, water_type="lake"):
    return {
        "air": {"temp_f": air, "cloud_pct": cloud, "wind_mph": wind, "pressure_6h_delta": pressure, "air_temp_6h_delta": 2, "rain_24h_in": rain},
        "water": {"temp_f": water, "temp_source": water_source, "temp_6h_delta_f": water_delta, "flow_6h_delta_pct": flow},
        "solar": {"daypart": daypart}, "waterbody": {"type": water_type, "clarity": "unknown"}, "provenance": {},
    }


def run():
    cold = build_pattern("Largemouth Bass", env("midday", water=48, water_source="usgs"), behavioral_context={"date": "2026-05-15"})
    warm = build_pattern("Largemouth Bass", env("midday", water=74, water_source="direct_user", water_delta=2.0), behavioral_context={"date": "2026-05-15"})
    assert cold["seasonal_state"]["stage"] == "pre_spawn"
    assert warm["seasonal_state"]["stage"] == "post_spawn"
    assert warm["seasonal_state"]["estimated"] is False
    no_water = build_pattern("Largemouth Bass", env("midday", air=82))
    assert no_water["environment"]["water_temp_f"] is None
    assert no_water["seasonal_state"]["estimated"] is True
    river = build_pattern("Smallmouth Bass", env("morning", water=61, water_source="usgs", flow=18, rain=.4, water_type="river"), water_context={"type": "river", "habitat": "rock current_seam"})
    assert river["environment"]["flow_state"] == "rapidly_rising"
    assert river["feeding_mode"]["primary"] == "current_oriented"
    assert any("rain" in reason.lower() or "flow" in reason.lower() for reason in river["activity"]["why"])
    unknown = build_pattern("Largemouth Bass", env())
    assert unknown["position"]["structure"] == []
    source = (ROOT / "intelligence/pattern_intelligence.py").read_text()
    assert "requests" not in source and "rank_offerings" not in source
    assert ast.parse((ROOT / "app.py").read_text())
    print("PASS: V7.10.1 adaptive pattern refinement QC")


if __name__ == "__main__":
    run()
