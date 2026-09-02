#!/usr/bin/env python3
"""Focused, offline QC for the V7.9 behavioral offering pipeline."""
from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.offering_intelligence import build_offering_intelligence  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    profiles = json.loads((ROOT / "data/species_behavior_profiles.json").read_text())
    offerings = json.loads((ROOT / "data/fishing_offerings.json").read_text())
    required = {"largemouth-bass", "smallmouth-bass", "crappie", "bluegill", "channel-catfish", "walleye", "sauger", "white-bass", "northern-pike", "rainbow-trout"}
    check(required <= profiles.keys(), "required behavioral profiles are missing")
    check({"sweet-corn", "bread", "dough-ball", "hot-dog", "chicken-liver", "nightcrawler", "minnow", "shiner", "leech", "crayfish", "cut-bait"} <= {o["id"] for o in offerings}, "starter offerings are missing")

    common = dict(air_temp_f=72, wind_mph=8, pressure_inhg=29.95, cloud_cover=55, water_type="lake", habitat="weeds dock", sunrise="2026-07-15T05:30:00", sunset="2026-07-15T20:30:00")
    cases = [
        ("Largemouth Bass", "2026-07-15T05:45:00", "dawn"),
        ("Largemouth Bass", "2026-07-15T13:00:00", "midday"),
        ("Largemouth Bass", "2026-07-15T16:30:00", "late_afternoon"),
        ("Largemouth Bass", "2026-10-15T13:00:00", "midday"),
        ("Crappie", "2026-04-15T07:00:00", "morning"),
        ("Crappie", "2026-07-15T13:00:00", "midday"),
        ("Walleye", "2026-07-15T05:45:00", "dawn"),
        ("Walleye", "2026-07-15T13:00:00", "midday"),
        ("Channel Catfish", "2026-07-15T22:00:00", "night"),
        ("Common Carp", "2026-07-15T11:00:00", "midday"),
        ("Rainbow Trout", "2026-04-15T08:00:00", "morning"),
        ("Northern Pike", "2026-10-15T16:30:00", "late_afternoon"),
    ]
    for species, timestamp, expected_daypart in cases:
        result = build_offering_intelligence(species, timestamp=timestamp, **common)
        check(result["daypart"]["daypart"] == expected_daypart, f"daypart failed for {species}: {result['daypart']}")
        for key in ("seasonal_stage", "forage_hypotheses", "feeding_modes", "fish_position", "presentation", "offerings"):
            check(result.get(key), f"{key} missing for {species}")
        check(result["water_temp_f"] is None and result["water_temp_source"] == "unknown", "air feed was treated as water temperature")
        check(all("why" in item for item in result["offerings"]), f"offering explanation missing for {species}")
        check(result["live_personal_evidence_applied"] is False, "live personal ranking was enabled")

    direct = build_offering_intelligence("Walleye", water_temp_f=61, water_temp_source="manual", **common)
    check(direct["water_temp_f"] == 61 and direct["water_temp_source"] == "manual", "direct water temperature did not override safely")
    fallback = build_offering_intelligence("Largemouth Bass", timestamp="2026-07-15T22:00:00", **{k: v for k, v in common.items() if k not in {"sunrise", "sunset"}})
    check(fallback["daypart"]["source"] == "clock_fallback", "clock fallback was not used without solar data")
    winter = build_offering_intelligence("Largemouth Bass", timestamp="2026-01-15T13:00:00", **common)
    summer = build_offering_intelligence("Largemouth Bass", timestamp="2026-07-15T13:00:00", **common)
    check([o["id"] for o in winter["offerings"][:4]] != [o["id"] for o in summer["offerings"][:4]], "seasonal offering order did not change")
    app_source = (ROOT / "app.py").read_text()
    check(ast.parse(app_source), "app.py did not parse")
    check("Recommended Baits &amp; Lures" in (ROOT / "templates/index.html").read_text(), "dashboard terminology missing")
    check("Admin" not in (ROOT / "templates/index.html").read_text(), "Admin restored to normal dashboard navigation")
    print(f"PASS: V7.9 behavioral QC ({len(cases)} scenarios, {len(offerings)} offerings)")


if __name__ == "__main__":
    run()
