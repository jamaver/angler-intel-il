#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import subprocess
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


def assert_nonempty(rel: str) -> None:
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        return
    if path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


required_files = (
    "app.py",
    "static/js/app.js",
    "static/js/map_dashboard_v49.js",
    "static/js/ui_polish_v442.js",
    "static/css/style.css",
    "templates/index.html",
    "templates/map.html",
    "intelligence/lures.py",
    "data/version_v5_3_icon_system.json",
)
for rel in required_files:
    assert_exists(rel)

for rel in ("app.py", "intelligence/lures.py"):
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_3_icon_system.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.3-icon-system":
        errors.append("Icon marker has unexpected version")
    for key in ("icon_update", "fish_icons", "lure_icons", "map_icons"):
        if marker.get(key) is not True:
            errors.append(f"Icon marker must set {key}=true")
    if marker.get("copied_fishbrain_assets") is not False:
        errors.append("Icon marker must state copied_fishbrain_assets=false")

for rel in (
    "static/icons/fish/largemouth_bass.svg",
    "static/icons/fish/smallmouth_bass.svg",
    "static/icons/fish/crappie.svg",
    "static/icons/fish/bluegill.svg",
    "static/icons/fish/catfish.svg",
    "static/icons/fish/trout.svg",
    "static/icons/fish/walleye.svg",
    "static/icons/fish/pike.svg",
    "static/icons/fish/generic_fish.svg",
    "static/icons/lures/jig.svg",
    "static/icons/lures/crankbait.svg",
    "static/icons/lures/spinnerbait.svg",
    "static/icons/lures/soft_plastic_worm.svg",
    "static/icons/lures/swimbait.svg",
    "static/icons/lures/topwater_popper.svg",
    "static/icons/lures/frog.svg",
    "static/icons/lures/spoon.svg",
    "static/icons/lures/inline_spinner.svg",
    "static/icons/lures/drop_shot.svg",
    "static/icons/lures/bobber_live_bait.svg",
    "static/icons/lures/generic_lure.svg",
    "static/icons/map/lake.svg",
    "static/icons/map/pond.svg",
    "static/icons/map/river.svg",
    "static/icons/map/creek.svg",
    "static/icons/map/reservoir.svg",
    "static/icons/map/spillway.svg",
    "static/icons/map/favorite_water.svg",
    "static/icons/map/manual_water.svg",
    "static/icons/map/catch_history.svg",
    "static/icons/map/high_confidence.svg",
    "static/icons/map/missing_coordinates.svg",
    "static/icons/ui/placeholder.svg",
):
    assert_nonempty(rel)

for rel in ("static/icons/fish", "static/icons/lures", "static/icons/map", "static/icons/ui"):
    if not (APP_ROOT / rel).is_dir():
        errors.append(f"Missing directory {rel}")

app_text = read("app.py")
for needle in (
    "fish_icon_name",
    "lure_icon_name",
    "/static/icons/fish/",
    "/static/icons/lures/",
):
    if needle not in app_text:
        errors.append(f"app.py missing {needle}")

js_text = read("static/js/app.js")
map_js_text = read("static/js/map_dashboard_v49.js")
template_text = read("templates/map.html")
for needle in (
    "/static/icons/fish/",
    "/static/icons/lures/",
    "/static/icons/map/",
    "ai-icon",
    "fish-icon",
    "lure-icon",
    "map-marker-icon",
):
    if needle not in js_text and needle not in map_js_text and needle not in template_text:
        errors.append(f"Icon wiring missing {needle}")

for rel in ("static/js/app.js", "static/js/map_dashboard_v49.js", "static/js/ui_polish_v442.js"):
    if subprocess.run(["node", "--check", str(APP_ROOT / rel)], capture_output=True, text=True).returncode != 0:
        errors.append(f"{rel} failed node --check")

if subprocess.run(["python", "-m", "py_compile", str(APP_ROOT / "app.py"), str(APP_ROOT / "intelligence/lures.py")], capture_output=True, text=True).returncode != 0:
    errors.append("Python compile check failed")

for rel in ("templates/index.html", "templates/map.html"):
    text = read(rel)
    if 'href="/admin"' in text:
        errors.append(f"{rel} should not expose Admin in normal navigation")

if "Fishbrain" in app_text or "Fishbrain" in js_text or "Fishbrain" in template_text:
    errors.append("Fishbrain references should not appear in live code")

if errors:
    print("QC FAILED: v5.3 Icon System")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.3 Icon System")
