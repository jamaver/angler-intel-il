#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
import tempfile
import zipfile
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
    "angler_health_backup_v443.py",
    "tools/backup_restore.py",
    "tools/restore_user_data.sh",
    "static/js/app_health_backups_v443.js",
    "data/version_v5_8_structured_backup_restore.json",
    "docs/ROADMAP.md",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_8_structured_backup_restore.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.8-structured-backup-restore":
        errors.append("v5.8 marker has unexpected version")
    for key in ("structured_backup_restore_enabled", "restore_precheck_snapshot_enabled", "app_health_restore_controls_enabled"):
        if marker.get(key) is not True:
            errors.append(f"v5.8 marker must set {key}=true")

app_version = json.loads((APP_ROOT / "data" / "app_version.json").read_text(encoding="utf-8"))
if not str(app_version.get("version", "")).startswith(("v6.", "v7.")):
    errors.append("app_version.json is not aligned to the current v6 release line")

app_text = read("app.py")
if "APP_VERSION = \"v6." not in app_text and "APP_VERSION = \"v7." not in app_text:
    errors.append("app.py version string is not aligned to the current v6 release line")
if "structured_backup_restore" not in app_text and "modern_ui_refresh" not in app_text:
    errors.append("app.py should record the structured backup restore or modern UI refresh module")

backup_text = read("angler_health_backup_v443.py")
for needle, message in [
    ('@app.route("/api/app-health/backups/restore"', "Missing backup restore route"),
    ("safe_user_data_backup_path", "Restore route should validate backup filenames"),
    ("restore_user_data_backup", "Restore route should use structured restore helper"),
]:
    if needle not in backup_text:
        errors.append(message)

helper_text = read("tools/backup_restore.py")
for needle, message in [
    ("def safe_user_data_backup_path", "Restore helper missing safe path validation"),
    ("def restore_user_data_backup", "Restore helper missing restore logic"),
    ("ALLOWED_ROOTS", "Restore helper missing allowed roots"),
]:
    if needle not in helper_text:
        errors.append(message)

js_text = read("static/js/app_health_backups_v443.js")
for needle, message in [
    ("Restore", "App Health backups UI should include restore controls"),
    ("restoreBackup", "App Health backups UI should include restore action"),
]:
    if needle not in js_text:
        errors.append(message)

from tools.backup_restore import restore_user_data_backup, safe_user_data_backup_path
from angler_health_backup_v443 import register_health_backup_routes_v443
from flask import Flask

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    base = tmp / "angler-intel"
    (base / "data").mkdir(parents=True, exist_ok=True)
    (base / "intelligence").mkdir(parents=True, exist_ok=True)
    (base / "static" / "lures").mkdir(parents=True, exist_ok=True)
    (base / "static" / "fish").mkdir(parents=True, exist_ok=True)

    original = {
        "data/favorites.json": '[{"name":"Original"}]',
        "data/catches.json": "[]",
        "intelligence/placeholder.json": '{"base":true}',
        "static/lures/lure.txt": "original lure",
    }
    for rel, text in original.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    archive = tmp / "angler-intel-cli-backup-test.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data/favorites.json", '[{"name":"Restored"}]')
        zf.writestr("data/catches.json", '[{"species":"Bass"}]')
        zf.writestr("static/lures/lure.txt", "restored lure")
        zf.writestr("intelligence/placeholder.json", '{"base":false}')

    result = restore_user_data_backup(archive, base_dir=base, create_snapshot=True)
    if result.get("ok") is not True:
        errors.append("Structured restore helper did not return ok=true")
    if "data" not in result.get("restored_roots", []):
        errors.append("Structured restore helper did not restore the data root")
    if (base / "data" / "favorites.json").read_text(encoding="utf-8") != '[{"name":"Restored"}]':
        errors.append("Structured restore helper did not restore data/favorites.json")
    if (base / "static" / "lures" / "lure.txt").read_text(encoding="utf-8") != "restored lure":
        errors.append("Structured restore helper did not restore static/lures")
    snapshot_path = result.get("pre_restore_snapshot")
    if not snapshot_path or not Path(snapshot_path).exists():
        errors.append("Structured restore helper did not create a pre-restore snapshot")

    try:
        safe_user_data_backup_path("../escape.zip")
        errors.append("Traversal filename should be rejected")
    except ValueError:
        pass

    try:
        safe_user_data_backup_path("/tmp/escape.zip")
        errors.append("Absolute filename should be rejected")
    except ValueError:
        pass

    app = Flask(__name__)
    register_health_backup_routes_v443(app)
    client = app.test_client()

    invalid = client.post("/api/app-health/backups/restore", json={"filename": "../escape.zip"})
    if invalid.status_code == 200:
        errors.append("Traversal restore request should not succeed")

if errors:
    print("QC FAILED: v5.8 Structured Backup and Restore")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.8 Structured Backup and Restore")
print("Structured restore helper, route, and App Health controls are wired safely.")
