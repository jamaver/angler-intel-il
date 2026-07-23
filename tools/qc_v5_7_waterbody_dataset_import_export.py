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
    "angler_waters_v40.py",
    "intelligence/water_registry.py",
    "static/css/style.css",
    "data/version_v5_7_waterbody_dataset_import_export.json",
    "docs/ROADMAP.md",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_7_waterbody_dataset_import_export.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.7-waterbody-dataset-import-export":
        errors.append("v5.7 marker has unexpected version")
    for key in ("waterbody_dataset_export_enabled", "waterbody_dataset_import_enabled", "manual_waters_untouched", "catalog_refresh_after_import"):
        if marker.get(key) is not True:
            errors.append(f"v5.7 marker must set {key}=true")

app_version = json.loads((APP_ROOT / "data" / "app_version.json").read_text(encoding="utf-8"))
if not str(app_version.get("version", "")).startswith(("v6.", "v7.")):
    errors.append("app_version.json is not aligned to the current v6 release line")

app_text = read("app.py")
if "APP_VERSION = \"v6." not in app_text and "APP_VERSION = \"v7." not in app_text:
    errors.append("app.py version string is not aligned to the current v6 release line")

waters_text = read("templates/waters.html")
for needle, message in [
    ("Dataset Tools", "Local waters page missing dataset tools section"),
    ("exportWaterDataset", "Local waters page missing export JS"),
    ("importWaterDataset", "Local waters page missing import JS"),
]:
    if needle not in waters_text:
        errors.append(message)

registry_text = read("intelligence/water_registry.py")
for needle, message in [
    ("def export_waterbody_dataset", "Water registry export helper missing"),
    ("def import_waterbody_dataset", "Water registry import helper missing"),
]:
    if needle not in registry_text:
        errors.append(message)

from app import app as flask_app
from intelligence.water_registry import load_custom_water_records

client = flask_app.test_client()

export_manual = client.get("/api/waters/export?scope=manual")
if export_manual.status_code != 200:
    errors.append(f"Manual export failed with HTTP {export_manual.status_code}")
else:
    manual_payload = export_manual.get_json(force=True)
    if manual_payload.get("export_scope") != "manual":
        errors.append("Manual export did not report manual scope")
    if not isinstance(manual_payload.get("manual_waters"), list):
        errors.append("Manual export did not include manual waters list")

export_merged = client.get("/api/waters/export?scope=merged")
if export_merged.status_code != 200:
    errors.append(f"Merged export failed with HTTP {export_merged.status_code}")
else:
    merged_payload = export_merged.get_json(force=True)
    if merged_payload.get("export_scope") != "merged":
        errors.append("Merged export did not report merged scope")
    if not isinstance(merged_payload.get("waters"), list):
        errors.append("Merged export did not include merged waters list")

before_manual = load_custom_water_records()
roundtrip = client.post("/api/waters/import", json={
    "mode": "replace",
    "manual_waters": manual_payload.get("manual_waters", []),
})
if roundtrip.status_code != 200:
    errors.append(f"Manual import failed with HTTP {roundtrip.status_code}")
else:
    imported = roundtrip.get_json(force=True)
    if imported.get("ok") is not True:
        errors.append("Manual import did not return ok=true")
    if imported.get("import", {}).get("imported_count") != len(manual_payload.get("manual_waters", [])):
        errors.append("Manual import imported count mismatch")
    after_manual = load_custom_water_records()
    if len(after_manual) != len(before_manual):
        errors.append("Manual import should preserve manual water count during round-trip")

invalid = client.post("/api/waters/import", json={"mode": "replace", "manual_waters": "invalid"})
if invalid.status_code == 200:
    errors.append("Invalid import payload should not succeed")

if errors:
    print("QC FAILED: v5.7 Waterbody Dataset Import/Export")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.7 Waterbody Dataset Import/Export")
print("Manual water dataset export/import is wired end to end.")
