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
    "angler_health_v39.py",
    "intelligence/smart_intelligence.py",
    "intelligence/app_health_intelligence.py",
    "tools/qc_v4_6_1_smart_intelligence_hardening.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v4_6_1_smart_intelligence_hardening.json"
if not marker_path.exists():
    errors.append("Missing data/version_v4_6_1_smart_intelligence_hardening.json")
else:
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("version") != "v4.6.1-smart-intelligence-hardening":
            errors.append("v4.6.1 marker has unexpected version")
        if marker.get("json_source_of_truth") is not True:
            errors.append("v4.6.1 marker does not preserve current JSON source-of-truth")
        if "mirror/read-only" not in str(marker.get("sqlite_role", "")).lower():
            errors.append("v4.6.1 marker does not preserve SQLite mirror/read-only role")
        if marker.get("sqlite_authority_allowed_after_migration") is not True:
            errors.append("v4.6.1 marker should declare future SQLite authority direction")
        if marker.get("rollback_required_before_sqlite_authority") is not True:
            errors.append("v4.6.1 marker should require rollback before SQLite authority")
        if marker.get("map_dashboard_planned") is not True:
            errors.append("v4.6.1 marker should declare map dashboard direction")
        if marker.get("confidence_fields_added") is not True:
            errors.append("v4.6.1 marker should record confidence fields added")
        if marker.get("explanation_fields_added") is not True:
            errors.append("v4.6.1 marker should record explanation fields added")
        if marker.get("empty_input_qc_added") is not True:
            errors.append("v4.6.1 marker should record empty-input QC")
        if marker.get("api_intel_fallback_added") is not True:
            errors.append("v4.6.1 marker should record API fallback support")
    except Exception as exc:
        errors.append(f"v4.6.1 marker invalid JSON: {exc}")

from intelligence.app_health_intelligence import get_smart_intelligence_health_for_app
from intelligence.smart_intelligence import build_smart_intelligence

sample = build_smart_intelligence(
    zip_code="60543",
    location={"city": "Oswego", "state": "Illinois"},
    weather={},
    area_type="lake",
    best_bet={
        "species": "Largemouth Bass",
        "species_score": 80,
        "lure_name": "Spinnerbait",
        "why": "sample",
    },
    best_time={"label": "Evening"},
    catch_insights={"total": 0, "local_total": 0, "top_species": []},
)

if sample.get("ok") is not True:
    errors.append("Smart Intelligence should tolerate missing weather inputs")

if not sample.get("input_quality", {}).get("missing"):
    errors.append("Smart Intelligence should report missing input quality fields")

if sample.get("input_quality", {}).get("fallback") is not True:
    errors.append("Smart Intelligence should mark empty weather inputs as fallback")

if not isinstance(sample.get("confidence"), dict):
    errors.append("Smart Intelligence should expose a confidence payload")

if not isinstance(sample.get("explanation"), list) or not sample.get("explanation"):
    errors.append("Smart Intelligence should expose an explanation list")

if not isinstance(sample.get("positive_signals"), list):
    errors.append("Smart Intelligence should expose positive signals")

if not isinstance(sample.get("caution_signals"), list):
    errors.append("Smart Intelligence should expose caution signals")

if sample.get("catch_history", {}).get("sample_size", {}).get("total") != 0:
    errors.append("Smart Intelligence should treat empty catch history as zero sample size")

if sample.get("clarity_signal", {}).get("inferred") is not False:
    errors.append("Smart Intelligence should label missing-weather clarity as not inferred")

minimal = build_smart_intelligence(
    zip_code="60543",
    location=None,
    weather=None,
    area_type="",
    best_bet=None,
    best_time=None,
    catch_insights=None,
)

if minimal.get("ok") is not True:
    errors.append("Smart Intelligence should tolerate minimal empty inputs")

if not isinstance(minimal.get("confidence"), dict) or minimal["confidence"].get("level") not in {"low", "moderate", "high"}:
    errors.append("Smart Intelligence should emit a confidence level for minimal inputs")

if not isinstance(minimal.get("explanation"), list) or not minimal.get("explanation"):
    errors.append("Smart Intelligence should explain minimal-input fallback behavior")

if minimal.get("clarity_signal", {}).get("inferred") is not False:
    errors.append("Smart Intelligence should mark missing minimal clarity as not inferred")

if minimal.get("catch_history", {}).get("sample_size", {}).get("total") != 0:
    errors.append("Smart Intelligence should keep minimal catch history at zero sample size")

if minimal.get("input_quality", {}).get("fallback") is not True:
    errors.append("Smart Intelligence should mark minimal inputs as fallback")

direction = sample.get("transition_direction", {})
if direction.get("map_dashboard_planned") is not True:
    errors.append("Smart Intelligence should declare map-driven dashboard direction")
if direction.get("sqlite_authority_allowed_after_migration") is not True:
    errors.append("Smart Intelligence should declare future SQLite authority direction")
if direction.get("requires_rollback_tools_before_sqlite_authority") is not True:
    errors.append("Smart Intelligence should require rollback before SQLite authority")

health = get_smart_intelligence_health_for_app()
if not isinstance(health, dict):
    errors.append("get_smart_intelligence_health_for_app did not return a dict")
if health.get("json_source_of_truth") is not True:
    errors.append("Smart Intelligence health should preserve current JSON source-of-truth")
if "mirror/read-only" not in str(health.get("sqlite_role", "")).lower():
    errors.append("Smart Intelligence health should preserve current SQLite mirror/read-only role")

health_text = read("angler_health_v39.py")
if "intelligence_health" not in health_text:
    errors.append("App Health does not wire Smart Intelligence readiness")
if "_smart_intelligence_health_card.html" not in health_text:
    errors.append("App Health does not render Smart Intelligence readiness card")

app_text = read("app.py")
if "build_smart_intelligence_fallback" not in app_text:
    errors.append("app.py does not use the smart intelligence fallback path")

card = APP_ROOT / "templates" / "_smart_intelligence_health_card.html"
if not card.exists():
    errors.append("Missing templates/_smart_intelligence_health_card.html")
else:
    card_text = card.read_text(encoding="utf-8")
    if "Admin" in card_text:
        errors.append("Smart Intelligence health card should not mention Admin")
    if "map" not in card_text.lower():
        errors.append("Smart Intelligence health card should mention map direction")
    if "rollback" not in card_text.lower():
        errors.append("Smart Intelligence health card should mention rollback guardrails")

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
if 'href="/admin"' in normal_page_text:
    errors.append("Normal navigation should not expose Admin")

js_text = read("static/js/app.js")
for fragment in (
    "intel.confidence",
    "intel.explanation",
    "positive_signals",
    "caution_signals",
    "input_quality",
    "catch_history",
):
    if fragment not in js_text:
        errors.append(f"Dashboard renderer is missing defensive field access for {fragment}")

if errors:
    print("QC FAILED: v4.6.1 Smart Intelligence Hardening")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.6.1 Smart Intelligence Hardening")
print("Smart Intelligence tolerates missing inputs and declares future architecture direction.")
print("JSON remains current source of truth until migration.")
print("SQLite authority requires deliberate migration and rollback tools.")
