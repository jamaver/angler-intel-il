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
    "intelligence/app_health_sqlite_transition.py",
    "tools/qc_v4_7_sqlite_transition.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

plan_path = APP_ROOT / "data" / "sqlite_authority_transition_plan_v47.json"
marker_path = APP_ROOT / "data" / "version_v4_7_sqlite_authority_transition_plan.json"

for path in (plan_path, marker_path):
    if not path.exists():
        errors.append(f"Missing {path.relative_to(APP_ROOT)}")

plan = {}
if plan_path.exists():
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("current_authority") != "json":
        errors.append("v4.7 plan must keep JSON as current authority")
    if plan.get("authority_switch_allowed_now") is not False:
        errors.append("v4.7 plan must block authority switch now")
    if not plan.get("rollback_plan"):
        errors.append("v4.7 plan must include rollback plan")
    required = " ".join(plan.get("required_before_authority_switch", [])).lower()
    for word in ("backup", "export", "rollback", "qc"):
        if word not in required:
            errors.append(f"v4.7 plan missing required {word} gate")

if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v4.7-sqlite-authority-transition-plan":
        errors.append("v4.7 marker has unexpected version")
    if marker.get("json_source_of_truth") is not True:
        errors.append("v4.7 marker must preserve current JSON source-of-truth")
    if marker.get("authority_switch_allowed_now") is not False:
        errors.append("v4.7 marker must block authority switch now")

from intelligence.app_health_sqlite_transition import get_sqlite_transition_health_for_app

health = get_sqlite_transition_health_for_app()
if not isinstance(health, dict):
    errors.append("get_sqlite_transition_health_for_app did not return dict")
if health.get("json_source_of_truth") is not True:
    errors.append("transition health must preserve JSON source-of-truth marker")
if health.get("current_authority") != "json":
    errors.append("transition health must keep JSON as current authority")
if health.get("readiness", {}).get("authority_switch_allowed_now") is not False:
    errors.append("transition health must block authority switch now")

health_text = read("angler_health_v39.py")
if "sqlite_transition_health" not in health_text:
    errors.append("App Health does not wire sqlite_transition_health")
if "_sqlite_transition_health_card.html" not in health_text:
    errors.append("App Health does not render SQLite transition card")

card_path = APP_ROOT / "templates" / "_sqlite_transition_health_card.html"
if not card_path.exists():
    errors.append("Missing templates/_sqlite_transition_health_card.html")
else:
    card = card_path.read_text(encoding="utf-8")
    if "Admin" in card:
        errors.append("SQLite transition card should not mention Admin")
    if "rollback" not in card.lower():
        errors.append("SQLite transition card should mention rollback")

normal_nav = "\n".join(
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
if 'href="/admin"' in normal_nav:
    errors.append("Normal navigation should not expose Admin")

if errors:
    print("QC FAILED: v4.7 SQLite Authority Transition Plan")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.7 SQLite Authority Transition Plan")
print("JSON remains current authority.")
print("SQLite authority is planned but blocked until migration and rollback gates pass.")
