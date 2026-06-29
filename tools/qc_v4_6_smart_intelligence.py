#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors: list[str] = []


def read(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


for rel in (
    "app.py",
    "intelligence/smart_intelligence.py",
    "tools/qc_v4_6_smart_intelligence.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v4_6_smart_intelligence_upgrade.json"
if not marker_path.exists():
    errors.append("Missing data/version_v4_6_smart_intelligence_upgrade.json")
else:
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("version") != "v4.6-smart-intelligence-upgrade":
            errors.append("v4.6 marker has unexpected version")
        if marker.get("json_source_of_truth") is not True:
            errors.append("v4.6 marker does not preserve JSON source-of-truth")
        if "mirror/read-only" not in str(marker.get("sqlite_role", "")).lower():
            errors.append("v4.6 marker does not preserve SQLite mirror/read-only role")
    except Exception as exc:
        errors.append(f"v4.6 marker invalid JSON: {exc}")

app_text = read("app.py")
index_text = read("templates/index.html")
js_text = read("static/js/app.js")
nav_text = read("static/js/global_nav_v433.js")
normal_page_text = "\n".join(
    read(rel)
    for rel in (
        "templates/index.html",
        "angler_recommendations_v44.py",
        "angler_waters_v40.py",
        "angler_reports_v38.py",
        "angler_species_rigs_v43.py",
        "angler_health_v39.py",
        "static/js/global_nav_v433.js",
    )
)

if "build_smart_intelligence" not in app_text:
    errors.append("app.py does not build smart intelligence")

if "smart_intelligence" not in app_text:
    errors.append("app.py does not return smart_intelligence payload")

if 'id="smartIntelligence"' not in index_text:
    errors.append("Dashboard missing smart intelligence target")

if "renderSmartIntelligence" not in js_text:
    errors.append("static/js/app.js does not render smart intelligence")

if "Angler Intel IL" in index_text:
    errors.append("Dashboard visible brand should not be IL-only")

if "Angler Intel IL" in nav_text:
    errors.append("Global navigation visible brand should not be IL-only")

if 'href="/admin"' in normal_page_text:
    errors.append("Normal navigation should not expose Admin")

if 'href="/exports"' in normal_page_text:
    errors.append("Normal navigation should not expose Export")

if "{% include" in index_text and "_health_card" in index_text:
    errors.append("Dashboard should not duplicate App Health maintenance cards")

from intelligence.smart_intelligence import build_smart_intelligence

sample = build_smart_intelligence(
    zip_code="60543",
    location={"city": "Oswego", "state": "Illinois"},
    weather={"temp": 72, "wind": 9, "pressure": 29.95, "cloud": 65},
    area_type="lake",
    best_bet={
        "species": "Largemouth Bass",
        "species_score": 82,
        "lure_name": "White/chartreuse spinnerbait",
        "why": "sample",
    },
    best_time={"label": "Evening"},
    catch_insights={"total": 0, "local_total": 0, "top_species": []},
)

if sample.get("json_source_of_truth") is not True:
    errors.append("smart intelligence does not preserve JSON source-of-truth marker")

if "mirror/read-only" not in str(sample.get("sqlite_role", "")).lower():
    errors.append("smart intelligence does not preserve SQLite mirror/read-only role")

summary = str(sample.get("summary", "")).lower()
for required in ("weather", "wind", "pressure", "cloud", "season", "water", "lure", "catch"):
    if required not in summary:
        errors.append(f"smart intelligence summary missing {required} signal")

if errors:
    print("QC FAILED: v4.6 Smart Intelligence Upgrade")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.6 Smart Intelligence Upgrade")
print("Smart intelligence is additive and dashboard-visible.")
print("JSON remains source of truth.")
print("SQLite remains mirror/read-only foundation.")
