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
    "intelligence/app_health_versions.py",
    "tools/qc_v4_5_4_version_ledger.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

partial = APP_ROOT / "templates" / "_version_health_card.html"
if not partial.exists():
    errors.append("Missing templates/_version_health_card.html")

marker_path = APP_ROOT / "data" / "version_v4_5_4_app_health_version_ledger.json"
if not marker_path.exists():
    errors.append("Missing data/version_v4_5_4_app_health_version_ledger.json")
else:
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("version") != "v4.5.4-app-health-version-ledger":
            errors.append("v4.5.4 marker has unexpected version")
        if marker.get("json_source_of_truth") is not True:
            errors.append("v4.5.4 marker does not preserve JSON source-of-truth")
        if "mirror" not in str(marker.get("sqlite_role", "")).lower():
            errors.append("v4.5.4 marker does not preserve SQLite mirror role")
    except Exception as exc:
        errors.append(f"v4.5.4 marker invalid JSON: {exc}")

from intelligence.app_health_versions import get_version_health_for_app

version_health = get_version_health_for_app()
if not isinstance(version_health, dict):
    errors.append("get_version_health_for_app did not return a dict")

if version_health.get("json_source_of_truth") is not True:
    errors.append("version_health does not preserve JSON source-of-truth marker")

if "mirror" not in str(version_health.get("sqlite_role", "")).lower():
    errors.append("version_health does not preserve SQLite mirror/read-only role")

if "read-only" not in str(version_health.get("sqlite_role", "")).lower():
    errors.append("version_health SQLite role should remain read-only")

if int(version_health.get("marker_count", 0)) < 1:
    errors.append("version_health did not find version markers")

latest = version_health.get("latest") or {}
if not latest.get("version"):
    errors.append("version_health latest marker is missing version")

recent_versions = [
    item.get("version")
    for item in version_health.get("recent", [])
    if isinstance(item, dict)
]
if "v4.5.4-app-health-version-ledger" not in recent_versions:
    errors.append("version_health recent markers do not include v4.5.4")

app_text = read("app.py")
health_text = read("angler_health_v39.py")
index_text = read("templates/index.html")
version_card_text = read("templates/_version_health_card.html") if partial.exists() else ""

if "get_version_health_for_app" not in app_text:
    errors.append("app.py is missing version health helper wiring")

if "version_health" not in health_text:
    errors.append("App Health render does not pass version_health")

if "_version_health_card.html" not in health_text:
    errors.append("App Health render does not include version health card")

if "sqlite_health" not in health_text:
    errors.append("Existing sqlite_health context was removed from App Health")

if "backup_health" not in health_text:
    errors.append("Existing backup_health context was removed from App Health")

if "Admin" in version_card_text:
    errors.append("Version health card should not mention Admin")

if 'href="/admin"' in index_text:
    errors.append("Normal navigation should not expose Admin")

if '{% include "_version_health_card.html" %}' in index_text:
    errors.append("Version ledger card should live in App Health, not the dashboard")

if errors:
    print("QC FAILED: v4.5.4 App Health Version Ledger")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.5.4 App Health Version Ledger")
print("App Health shows version markers.")
print("JSON remains source of truth.")
print("SQLite remains mirror/read-only foundation.")
