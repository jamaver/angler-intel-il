#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors = []

paths = [
    APP_ROOT / "tools" / "app_backup.py",
    APP_ROOT / "intelligence" / "app_health_backup.py",
    APP_ROOT / "app.py",
]

for path in paths:
    try:
        ast.parse(path.read_text())
    except SyntaxError as exc:
        errors.append(f"{path.relative_to(APP_ROOT)} syntax error: {exc}")

partial = APP_ROOT / "templates" / "_backup_health_card.html"
if not partial.exists():
    errors.append("Missing templates/_backup_health_card.html")

app_text = (APP_ROOT / "app.py").read_text()
if "get_backup_health_for_app" not in app_text:
    errors.append("app.py does not import/use get_backup_health_for_app")

if "app_health_backup_status" not in app_text:
    errors.append("app.py missing app_health_backup_status helper")

if partial.exists() and "Admin" in partial.read_text():
    errors.append("Backup health card should not mention Admin")

from tools.app_backup import backup_status
from intelligence.app_health_backup import get_backup_health_for_app

status = backup_status()
health = get_backup_health_for_app()

if not isinstance(status, dict):
    errors.append("backup_status did not return a dict")

if not isinstance(health, dict):
    errors.append("get_backup_health_for_app did not return a dict")

if health.get("json_source_of_truth") is not True:
    errors.append("Backup health does not preserve JSON source-of-truth marker")

if int(status.get("archive_count", 0)) < 1:
    errors.append("No backup archives found after v4.5.2 setup")

index = APP_ROOT / "backups" / "backup_index.json"
if not index.exists():
    errors.append("Missing backups/backup_index.json")
else:
    try:
        payload = json.loads(index.read_text())
        if not isinstance(payload, list):
            errors.append("backup_index.json is not a list")
    except Exception as exc:
        errors.append(f"backup_index.json invalid JSON: {exc}")

if errors:
    print("QC FAILED: v4.5.2 Backup Polish")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.5.2 Backup Polish")
print("App Health remains maintenance hub.")
print("JSON remains source of truth.")
