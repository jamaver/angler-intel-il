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
    "intelligence/catch_learning.py",
    "static/js/app.js",
    "templates/index.html",
    "data/version_v5_2_catch_learning.json",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_2_catch_learning.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.2-catch-learning":
        errors.append("v5.2 marker has unexpected version")
    if marker.get("catch_learning_enabled") is not True:
        errors.append("v5.2 marker must enable catch learning")
    if marker.get("optional_catch_waterbody_field") is not True:
        errors.append("v5.2 marker must enable optional catch waterbody entry")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v5.2-catch-learning",
        "v5.3-target-species-profile",
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
    }:
        errors.append("app_version.json is not aligned to v5.2")

app_text = read("app.py")
if 'APP_VERSION = "v5.2-catch-learning"' not in app_text and 'APP_VERSION = "v5.3-target-species-profile"' not in app_text and 'APP_VERSION = "v5.4-map-ranking-prep"' not in app_text and 'APP_VERSION = "v5.5-realistic-icon-system"' not in app_text:
    errors.append("app.py version string is not aligned to v5.2")
for needle, message in [
    ("build_catch_learning_summary", "app.py should use catch learning summary helper"),
    ('"waterbody": str(payload.get("waterbody", "")).strip()', "Catch POST should preserve waterbody context"),
]:
    if needle not in app_text:
        errors.append(message)

template_text = read("templates/index.html")
js_text = read("static/js/app.js")
if "catchWaterbody" not in template_text:
    errors.append("Catch form is missing the optional waterbody field")
for needle, message in [
    ("catchWaterbody", "Catch JS should read the waterbody field"),
    ("topWaterbodies", "Catch insights should display top waterbodies"),
    ("localTopWaterbodies", "Catch insights should display local waterbodies"),
    ("sampleQuality", "Catch insights should display sample quality"),
]:
    if needle not in js_text:
        errors.append(message)

from app import app as flask_app

client = flask_app.test_client()
catch_payload = {
    "zip": "60543",
    "species": "Largemouth Bass",
    "lure": "Spinnerbait",
    "waterbody": "QC Lake",
    "notes": "QC catch-learning sample",
}

response = client.post("/api/catches", json=catch_payload)
if response.status_code != 200:
    errors.append(f"Catch POST failed with HTTP {response.status_code}")
else:
    saved = response.get_json(force=True)
    if saved.get("waterbody") != "QC Lake":
        errors.append("Catch POST did not persist waterbody")

    catches = client.get("/api/catches")
    if catches.status_code != 200:
        errors.append(f"Catch GET failed with HTTP {catches.status_code}")
    else:
        payload = catches.get_json(force=True)
        if not any(item.get("waterbody") == "QC Lake" for item in payload):
            errors.append("Catch GET did not return waterbody context")

    intel = client.get("/api/intel?zip=60543")
    if intel.status_code != 200:
        errors.append(f"Intel GET failed with HTTP {intel.status_code}")
    else:
        payload = intel.get_json(force=True)
        catch_history = payload.get("catch_insights", {})
        if not catch_history.get("top_waterbodies"):
            errors.append("Catch insights did not include top waterbodies")
        if catch_history.get("sample_quality") not in {"thin", "useful", "solid"}:
            errors.append("Catch insights did not include a sample quality label")

if errors:
    print("QC FAILED: v5.2 Catch Learning")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.2 Catch Learning")
print("Catch logs now carry optional waterbody context and learning summaries.")
