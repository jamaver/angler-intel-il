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


def assert_exists(rel: str) -> None:
    if not (APP_ROOT / rel).exists():
        errors.append(f"Missing {rel}")


for rel in (
    "app.py",
    "angler_health_v39.py",
    "intelligence/sqlite_foundation.py",
    "intelligence/sqlite_waterbodies.py",
    "intelligence/app_health_sqlite_waterbodies.py",
    "tools/sqlite_waterbody_preflight.py",
    "tools/sqlite_export_snapshot.py",
    "templates/_sqlite_waterbodies_health_card.html",
    "data/version_v5_1_sqlite_waterbody_migration_prep.json",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_1_sqlite_waterbody_migration_prep.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.1-sqlite-waterbody-migration-prep":
        errors.append("v5.1 marker has unexpected version")
    if marker.get("json_source_of_truth") is not True:
        errors.append("v5.1 marker must preserve JSON source-of-truth")
    if marker.get("authority_flipped") is not False:
        errors.append("v5.1 marker must not claim authority was flipped")
    if marker.get("waterbody_mirror_enabled") is not True:
        errors.append("v5.1 marker must enable waterbody mirror prep")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v5.1-sqlite-waterbody-migration-prep",
        "v5.2-catch-learning",
        "v5.3-target-species-profile",
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
        "v5.6-waterbody-detail-panels",
        "v5.7-waterbody-dataset-import-export",
        "v5.8-structured-backup-restore",
    }:
        errors.append("app_version.json is not aligned to v5.1 or later")

app_text = read("app.py")
if 'APP_VERSION = "v5.1-sqlite-waterbody-migration-prep"' not in app_text and 'APP_VERSION = "v5.2-catch-learning"' not in app_text and 'APP_VERSION = "v5.3-target-species-profile"' not in app_text and 'APP_VERSION = "v5.4-map-ranking-prep"' not in app_text and 'APP_VERSION = "v5.5-realistic-icon-system"' not in app_text and 'APP_VERSION = "v5.6-waterbody-detail-panels"' not in app_text and 'APP_VERSION = "v5.7-waterbody-dataset-import-export"' not in app_text and 'APP_VERSION = "v5.8-structured-backup-restore"' not in app_text:
    errors.append("app.py version string is not aligned to v5.1 or later")

if "waterbodies_mirror" not in read("intelligence/sqlite_foundation.py"):
    errors.append("sqlite_foundation is missing the waterbodies_mirror table")
if "mirror_waterbodies" not in read("intelligence/sqlite_waterbodies.py"):
    errors.append("sqlite_waterbodies mirror helper is missing")
if "get_sqlite_waterbodies_health_for_app" not in read("angler_health_v39.py"):
    errors.append("App Health is missing the waterbodies health helper")
if "_sqlite_waterbodies_health_card.html" not in read("angler_health_v39.py"):
    errors.append("App Health is missing the waterbodies health card render")
if "sqlite_waterbodies_health" not in read("angler_health_v39.py"):
    errors.append("App Health does not wire sqlite_waterbodies_health")

from intelligence.app_health_sqlite_waterbodies import get_sqlite_waterbodies_health_for_app
from tools.sqlite_waterbody_preflight import collect_preflight

preflight = collect_preflight()
if not isinstance(preflight, dict):
    errors.append("collect_preflight did not return a dict")
else:
    if preflight.get("version") != "v5.1-sqlite-waterbody-migration-prep":
        errors.append("preflight version is not aligned to v5.1")
    if preflight.get("json_source_of_truth") is not True:
        errors.append("preflight must keep JSON as source of truth")
    if preflight.get("authority_flipped") is not False:
        errors.append("preflight must not flip authority")
    if preflight.get("ok") is not True:
        errors.append(f"preflight is not green: {preflight.get('errors')}")
    gates = {gate.get("name"): gate for gate in preflight.get("gates", [])}
    for gate_name in ("waterbody_catalog", "waterbody_mirror", "export_snapshot", "sqlite_status"):
        gate = gates.get(gate_name)
        if gate is None:
            errors.append(f"preflight missing {gate_name} gate")
        elif gate.get("ok") is not True:
            errors.append(f"preflight gate failed: {gate_name} - {gate.get('summary')}")

health = get_sqlite_waterbodies_health_for_app()
if not isinstance(health, dict):
    errors.append("waterbody health helper did not return dict")
else:
    if health.get("current_authority") != "json":
        errors.append("waterbody health must keep JSON authority")
    if health.get("authority_flipped") is not False:
        errors.append("waterbody health must not claim authority flip")
    if health.get("ok") is not True:
        errors.append(f"waterbody health is not green: {health.get('errors')}")

normal_nav = "\n".join(
    read(rel)
    for rel in (
        "templates/index.html",
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
    print("QC FAILED: v5.1 SQLite Waterbody Migration Prep")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.1 SQLite Waterbody Migration Prep")
print("Waterbody mirror prep is wired, exportable, and still JSON-first.")
