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


def read_text(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


def require_exists(rel: str) -> None:
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")


for rel in (
    "app.py",
    "intelligence/species_assets.py",
):
    require_exists(rel)
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

for rel in (
    "static/js/app.js",
    "static/css/style.css",
    "templates/water.html",
    "templates/snapshot.html",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")

fish_dir = APP_ROOT / "static" / "fish"
if not fish_dir.exists():
    errors.append("Missing static/fish/")
else:
    required = [
        "largemouth_bass.png",
        "smallmouth_bass.png",
        "crappie.png",
        "bluegill.png",
        "channel_catfish.png",
        "rainbow_trout.png",
        "walleye.png",
        "sauger.png",
        "white_bass.png",
        "northern_pike.png",
    ]
    for name in required:
        file_path = fish_dir / name
        if not file_path.exists():
            errors.append(f"Missing static/fish/{name}")
        elif file_path.stat().st_size <= 0:
            errors.append(f"Empty static/fish/{name}")

    fallback = fish_dir / "generic_fish.png"
    if not fallback.exists():
        errors.append("Missing static/fish/generic_fish.png")
    elif fallback.stat().st_size <= 0:
        errors.append("Empty static/fish/generic_fish.png")

app_text = read_text("app.py") if (APP_ROOT / "app.py").exists() else ""
if "from intelligence.species_assets import get_species_image" not in app_text:
    errors.append("app.py must import get_species_image")
if "fish_image" not in app_text:
    errors.append("app.py should expose fish_image usage")
if "/static/fish/" not in app_text:
    errors.append("app.py should reference static/fish assets")

js_text = read_text("static/js/app.js") if (APP_ROOT / "static/js/app.js").exists() else ""
if "FISH_ICON_MAP" not in js_text:
    errors.append("static/js/app.js must include fish icon mapping")
if "generic_fish.png" not in js_text:
    errors.append("static/js/app.js should use generic_fish.png fallback")
if "generic_fish.svg" in js_text:
    errors.append("static/js/app.js should not reference generic_fish.svg")

for rel in ("templates/water.html", "templates/snapshot.html"):
    if (APP_ROOT / rel).exists():
        text = read_text(rel)
        if "species-icon" not in text:
            errors.append(f"{rel} should use species-icon classes")

if "Admin" in read_text("templates/water.html") and "/admin" in read_text("templates/water.html"):
    errors.append("water.html should not restore Admin navigation")
if "Admin" in read_text("templates/snapshot.html") and "/admin" in read_text("templates/snapshot.html"):
    errors.append("snapshot.html should not restore Admin navigation")

if errors:
    print("QC FAILED")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: species image assets are wired into the app")
