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


for rel in (
    "tools/split_lure_sheets.py",
    "intelligence/lure_assets.py",
    "intelligence/lures.py",
    "tools/qc_lure_variant_assets.py",
    "app.py",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

source_dir = APP_ROOT / "static" / "lures" / "source_sheets"
if not source_dir.exists():
    errors.append("Missing static/lures/source_sheets/")
else:
    expected_sources = [
        "jig_variants_sheet.png",
        "crankbait_variants_sheet.png",
        "spinnerbait_variants_sheet.png",
        "soft_plastic_worm_variants_sheet.png",
        "swimbait_variants_sheet.png",
        "topwater_popper_variants_sheet.png",
        "frog_variants_sheet.png",
        "spoon_variants_sheet.png",
        "inline_spinner_variants_sheet.png",
        "drop_shot_variants_sheet.png",
    ]
    for name in expected_sources:
        path = source_dir / name
        if not path.exists():
            errors.append(f"Missing source sheet {name}")
        elif path.stat().st_size <= 0:
            errors.append(f"Empty source sheet {name}")

required_outputs = {
    "jig": ["green_pumpkin.png", "black_blue.png", "brown_orange_craw.png", "white_shad.png", "pbj.png"],
    "crankbait": ["shad.png", "bluegill.png", "craw_red.png", "chartreuse_black_back.png", "sexy_shad.png", "firetiger.png"],
    "spinnerbait": ["white_silver.png", "chartreuse_white.png", "gold_shiner.png", "bluegill.png", "black_night.png"],
    "soft_plastic_worm": ["green_pumpkin.png", "watermelon_red.png", "black_blue.png", "junebug.png", "natural_shad.png", "white_pearl.png"],
    "swimbait": ["pearl_white.png", "shad.png", "bluegill.png", "green_pumpkin.png", "ayu.png"],
    "topwater_popper": ["bone.png", "frog_green.png", "black.png", "shad.png", "chrome_blue.png"],
    "frog": ["green_frog.png", "black_frog.png", "white_frog.png", "leopard_frog.png", "brown_frog.png"],
    "spoon": ["silver.png", "gold.png", "blue_silver.png", "firetiger.png", "chartreuse.png"],
    "inline_spinner": ["silver.png", "gold.png", "firetiger.png", "chartreuse.png"],
    "drop_shot": ["green_pumpkin.png", "shad.png", "morning_dawn.png", "watermelon_red.png"],
}

for folder, files in required_outputs.items():
    for name in files:
        path = APP_ROOT / "static" / "lures" / folder / name
        if not path.exists():
            errors.append(f"Missing lure asset {folder}/{name}")
        elif path.stat().st_size <= 0:
            errors.append(f"Empty lure asset {folder}/{name}")

preview = APP_ROOT / "static" / "lures" / "_preview" / "lure_asset_contact_sheet.png"
if not preview.exists():
    errors.append("Missing lure asset contact sheet preview")

generic = APP_ROOT / "static" / "lures" / "generic_lure.png"
if not generic.exists():
    errors.append("Missing static/lures/generic_lure.png")

version_path = APP_ROOT / "data" / "version_v5_9_2_lure_variant_assets.json"
if not version_path.exists():
    errors.append("Missing data/version_v5_9_2_lure_variant_assets.json")
else:
    marker = json.loads(version_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.9.2-lure-variant-assets":
        errors.append("Lure variant version marker has unexpected version")
    if marker.get("lure_assets") is not True:
        errors.append("Version marker must set lure_assets=true")
    if marker.get("source_sheets_preserved") is not True:
        errors.append("Version marker must preserve source sheets flag")

from intelligence.lure_assets import resolve_lure_asset

cases = {
    "green pumpkin jig": "/static/lures/jig/green_pumpkin.png",
    "black and blue jig": "/static/lures/jig/black_blue.png",
    "shad crankbait": "/static/lures/crankbait/shad.png",
    "chartreuse spinnerbait": "/static/lures/spinnerbait/chartreuse_white.png",
    "white swimbait": "/static/lures/swimbait/pearl_white.png",
    "topwater frog": "/static/lures/topwater_popper/bone.png",
    "silver spoon": "/static/lures/spoon/silver.png",
    "drop shot morning dawn": "/static/lures/drop_shot/morning_dawn.png",
}

for text, expected in cases.items():
    asset = resolve_lure_asset(recommendation_text=text)
    if asset.get("path") != expected:
        errors.append(f"Resolver mismatch for '{text}': {asset.get('path')} != {expected}")

fallback = resolve_lure_asset(recommendation_text="unknown bait thing")
if fallback.get("path") != "/static/lures/generic_lure.png" or fallback.get("fallback_used") is not True:
    errors.append("Unknown lure text must fall back to generic_lure.png")

image_check = subprocess.run(
    [
        "python3",
        "-c",
        "\n".join(
            [
                "from PIL import Image",
                "from pathlib import Path",
                "paths = list(Path('static/lures').rglob('*.png'))",
                "assert paths, 'no pngs'",
                "for p in paths:",
                "    im = Image.open(p)",
                "    im.load()",
                "    assert im.size[0] > 0 and im.size[1] > 0",
            ]
        ),
    ],
    cwd=str(APP_ROOT),
    capture_output=True,
    text=True,
)
if image_check.returncode != 0:
    errors.append("Pillow image open check failed for lure assets")

app_text = read("app.py")
if "resolve_lure_asset" not in app_text:
    errors.append("app.py should import resolve_lure_asset")
if "lure_asset" not in app_text:
    errors.append("app.py should expose lure_asset metadata")

smart_text = read("intelligence/smart_intelligence.py")
if "lure_recommendation" not in smart_text:
    errors.append("smart_intelligence.py should expose lure_recommendation metadata")

js_text = read("static/js/app.js")
if "lureIconPath" not in js_text or "generic_lure.png" not in js_text:
    errors.append("static/js/app.js must resolve lure artwork and generic fallback")
if "recommendation-lure-art" not in js_text:
    errors.append("static/js/app.js should render lure artwork in intelligence cards")

if "Admin" in read("templates/index.html") and "/admin" in read("templates/index.html"):
    errors.append("Normal navigation should not restore Admin")

if errors:
    print("QC FAILED: lure variant assets")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: lure variant assets")
print("Source sheets, split outputs, resolver mappings, and UI hooks are wired.")
