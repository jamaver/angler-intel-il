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
    "tools/qc_v4_9_1_ui_snapshot_polish.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v4_9_1_ui_snapshot_polish.json"
if not marker_path.exists():
    errors.append("Missing data/version_v4_9_1_ui_snapshot_polish.json")
else:
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("version") != "v4.9.1-ui-snapshot-polish":
            errors.append("v4.9.1 marker has unexpected version")
        if marker.get("trip_snapshot_upgraded") is not True:
            errors.append("v4.9.1 marker should record Trip Snapshot upgrade")
        if marker.get("export_current_page_removed") is not True:
            errors.append("v4.9.1 marker should record export action removal")
    except Exception as exc:
        errors.append(f"v4.9.1 marker invalid JSON: {exc}")

index = read("templates/index.html")
snapshot = read("templates/snapshot.html")
app_js = read("static/js/app.js")
style = read("static/css/style.css")

if "Export Current Page" in app_js or "function exportPDF" in app_js:
    errors.append("Dashboard export PDF action should be removed")

if "Trip Snapshot" not in app_js:
    errors.append("Dashboard should keep Trip Snapshot as the print/PDF path")

for required in ("dashboard-shell", "dashboard-primary", "control-panel"):
    if required not in index and required not in style:
        errors.append(f"Dashboard UI polish class missing: {required}")

for required in ("Smart Intelligence", "Trip Notes", "Print / Save PDF", "Fallback weather estimate"):
    if required not in snapshot:
        errors.append(f"Trip Snapshot missing expected content: {required}")

if "Save / Export PDF" in snapshot:
    errors.append("Trip Snapshot should not use old export wording")

if "background: #eef6f0" not in snapshot or "color: var(--ink)" not in snapshot:
    errors.append("Trip Snapshot should declare readable background and text colors")

normal_page_text = "\n".join(
    read(rel)
    for rel in (
        "templates/index.html",
        "templates/snapshot.html",
        "templates/map.html",
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

if errors:
    print("QC FAILED: v4.9.1 UI Snapshot Polish")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.9.1 UI Snapshot Polish")
print("Main UI is cleaner, Trip Snapshot is upgraded, and Export Current Page is removed.")
