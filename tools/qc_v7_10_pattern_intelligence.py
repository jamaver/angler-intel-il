#!/usr/bin/env python3
"""Deterministic QC for the V7.10 Pattern Object foundation."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from intelligence.pattern_intelligence import build_pattern  # noqa: E402


def env(daypart="midday", *, air=72, cloud=45, wind=8, pressure_delta=0, water=None, clarity="unknown", rain=0):
    return {
        "air": {"temp_f": air, "cloud_pct": cloud, "wind_mph": wind, "pressure_6h_delta": pressure_delta, "rain_24h_in": rain},
        "water": {"temp_f": water, "temp_source": "manual" if water is not None else "unknown", "flow_cfs": None},
        "solar": {"daypart": daypart},
        "waterbody": {"clarity": clarity},
        "provenance": {},
    }


def run():
    dawn = build_pattern("Largemouth Bass", env("dawn", cloud=75, wind=10, pressure_delta=-0.1), water_context={"species": ["Largemouth Bass"], "habitat": "weeds dock"})
    midday = build_pattern("Largemouth Bass", env("midday", cloud=10, wind=2, pressure_delta=0.01), water_context={"species": ["Largemouth Bass"], "habitat": "weeds dock"})
    assert dawn["activity"]["score"] > midday["activity"]["score"]
    assert dawn["feeding_mode"]["primary"] == "chasing"
    assert midday["feeding_mode"]["primary"] == "ambushing"
    smallmouth = build_pattern("Smallmouth Bass", env("morning", wind=9, water=61), water_context={"species": ["Smallmouth Bass"], "habitat": "rock current_seam river"})
    assert smallmouth["feeding_mode"]["primary"] == "current_oriented"
    assert "rock" in smallmouth["position"]["structure"]
    crappie = build_pattern("Crappie", env("midday", cloud=40), water_context={}, observed_context={"structure": ["brush"], "vertical": "suspended", "forage": ["minnow"]})
    assert crappie["position"]["vertical"] == "suspended"
    assert crappie["forage"]["primary"] == "minnow" and crappie["forage"]["observed"]
    assert build_pattern("Walleye", env("dusk", cloud=60))["activity"]["score"] >= build_pattern("Walleye", env("midday", cloud=10, wind=1))["activity"]["score"]
    catfish = build_pattern("Channel Catfish", env("night", air=78), water_context={"habitat": "deep channel"})
    assert catfish["feeding_mode"]["primary"] == "bottom_feeding" and catfish["presentation"]["scent_value"] == "useful"
    carp = build_pattern("Common Carp", env("midday", air=80), water_context={"habitat": "flat shallow"})
    assert carp["feeding_mode"]["primary"] in {"bottom_feeding", "opportunistic"}
    trout = build_pattern("Rainbow Trout", env("morning", air=52), water_context={"habitat": "current"}, behavioral_context={"date": "2026-04-15"})
    assert trout["seasonal_state"]["stage"] == "cool_spring"
    missing = build_pattern("Largemouth Bass", {})
    assert missing["confidence"]["overall"] in {"limited", "moderate"} and "environment_missing" in missing["data_quality"]["fallbacks_used"]
    no_water = build_pattern("Largemouth Bass", env("midday", air=82), water_context={"habitat": "vegetation"})
    assert no_water["environment"]["water_temp_f"] is None and no_water["environment"]["water_temp_source"] == "unknown"
    unknown = build_pattern("Largemouth Bass", env("midday"), water_context={})
    assert unknown["position"]["structure"] == [] and unknown["position"]["fabricated_structure"] is False
    source = (ROOT / "intelligence/pattern_intelligence.py").read_text()
    assert "requests" not in source and "live_applied" in source
    payload = json.loads((ROOT / "data/version_v7_10_0_pattern_foundation.json").read_text())
    assert payload["live_offering_ranking_changed"] is False and payload["sqlite_authority_changed"] is False
    assert ast.parse((ROOT / "app.py").read_text())
    print("PASS: V7.10 Pattern Object QC (12 scenarios)")


if __name__ == "__main__":
    run()
