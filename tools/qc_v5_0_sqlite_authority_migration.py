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
    "intelligence/app_health_sqlite_authority.py",
    "tools/sqlite_authority_preflight.py",
    "tools/qc_v5_0_sqlite_authority_migration.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_0_sqlite_authority_migration.json"
if not marker_path.exists():
    errors.append("Missing data/version_v5_0_sqlite_authority_migration.json")
else:
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.0-sqlite-authority-migration":
        errors.append("v5.0 marker has unexpected version")
    if marker.get("json_source_of_truth") is not True:
        errors.append("v5.0 marker must preserve JSON source-of-truth until explicit migration")
    if marker.get("authority_flipped") is not False:
        errors.append("v5.0 marker must not claim authority was flipped")
    for key in ("backup_proven", "export_proven", "rollback_proven"):
        if marker.get(key) is not True:
            errors.append(f"v5.0 marker must set {key}=true after preflight")

card_path = APP_ROOT / "templates" / "_sqlite_authority_health_card.html"
if not card_path.exists():
    errors.append("Missing templates/_sqlite_authority_health_card.html")
else:
    card = card_path.read_text(encoding="utf-8")
    if "Admin" in card:
        errors.append("SQLite authority card should not mention Admin")
    for word in ("backup", "export", "rollback"):
        if word not in card.lower():
            errors.append(f"SQLite authority card should mention {word}")

from tools.sqlite_authority_preflight import collect_preflight
from intelligence.app_health_sqlite_authority import get_sqlite_authority_health_for_app

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v5.0-sqlite-authority-migration",
        "v5.1-sqlite-waterbody-migration-prep",
        "v5.2-catch-learning",
        "v5.3-target-species-profile",
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
        "v5.6-waterbody-detail-panels",
        "v5.7-waterbody-dataset-import-export",
        "v5.8-structured-backup-restore",
        "v5.9-modern-ui-refresh",
    } and not str(app_version.get("version") or "").startswith(("v6.", "v7.")):
        errors.append("app_version.json is not aligned to the v5.0/v5.1 migration line")

preflight = collect_preflight()
if not isinstance(preflight, dict):
    errors.append("collect_preflight did not return dict")
else:
    if preflight.get("json_source_of_truth") is not True:
        errors.append("preflight must preserve JSON source-of-truth marker")
    if preflight.get("authority_flipped") is not False:
        errors.append("preflight must not flip authority")
    if "mirror" not in str(preflight.get("sqlite_role", "")).lower():
        errors.append("preflight must keep SQLite as mirror foundation until explicit migration")
    gates = {gate.get("name"): gate for gate in preflight.get("gates", [])}
    for gate in ("backup", "sqlite_integrity", "export", "rollback"):
        if gate not in gates:
            errors.append(f"preflight missing {gate} gate")
        elif gates[gate].get("ok") is not True:
            errors.append(f"preflight gate failed: {gate} - {gates[gate].get('summary')}")

health = get_sqlite_authority_health_for_app()
if not isinstance(health, dict):
    errors.append("get_sqlite_authority_health_for_app did not return dict")
else:
    if health.get("current_authority") != "json":
        errors.append("authority health must keep JSON as current authority")
    if health.get("authority_flipped") is not False:
        errors.append("authority health must not report switched authority")
    if health.get("ready_for_authority_migration") is not True:
        errors.append("authority health should report v5.0 preflight proven")

health_text = read("angler_health_v39.py")
if "sqlite_authority_health" not in health_text:
    errors.append("App Health does not wire sqlite_authority_health")
if "_sqlite_authority_health_card.html" not in health_text:
    errors.append("App Health does not render SQLite authority card")
for existing in ("sqlite_health", "backup_health", "sqlite_transition_health", "version_health"):
    if existing not in health_text:
        errors.append(f"App Health lost existing {existing} context")

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
    print("QC FAILED: v5.0 SQLite Authority Migration")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.0 SQLite Authority Migration")
print("Backup, export, and rollback preflight gates are proven.")
print("JSON remains current authority until a later explicit migration flips it.")
