#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

errors: list[str] = []


def require(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


for rel in (
    "app.py",
    "angler_species_rigs_v43.py",
    "gear/inventory.py",
    "gear/settings.py",
    "gear/catalog_providers.py",
    "intelligence/gear_intelligence.py",
    "templates/tackle_locker.html",
    "static/js/tackle_locker_v610.js",
    "static/js/app.js",
    "static/css/style.css",
    "docs/MY_TACKLE_LOCKER.md",
    "docs/GEAR_INTELLIGENCE.md",
    "docs/V7_GEAR_DATA_MODEL.md",
    "data/version_v6_13_gear_intelligence_packing_catch_linking.json",
):
    require(rel)

for rel in ("app.py", "angler_species_rigs_v43.py", "gear/inventory.py", "gear/settings.py", "gear/catalog_providers.py", "intelligence/gear_intelligence.py"):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

template_text = read("templates/tackle_locker.html")
for needle in (
    "My Tackle Locker",
    "Recommended Setup for Current Trip",
    "gearTripSpecies",
    "gearRecommendation",
    "gearPackingList",
    "gearUsageSummary",
    "gearMaintenanceSummary",
    "Fishing Rig Reference",
    "gearImageUpload",
):
    if needle not in template_text:
        errors.append(f"tackle locker template missing {needle}")
if "/admin" in template_text:
    errors.append("Admin should not appear in tackle locker navigation")

js_text = read("static/js/tackle_locker_v610.js")
for needle in (
    "loadTripRecommendation",
    "renderRecommendationCard",
    "renderPackingCard",
    "renderUsageCard",
    "renderMaintenanceCard",
    "tripContextPayload",
    "gearTripSpecies",
    "gearRefreshTripPlan",
):
    if needle not in js_text:
        errors.append(f"tackle locker JS missing {needle}")

dash_js = read("static/js/app.js")
for needle in (
    "loadCatchGearOptions",
    "catchRod",
    "catchReel",
    "catchLine",
    "catchGearLure",
    "catchTerminal",
    "gear_summary",
    "gear_labels",
):
    if needle not in dash_js:
        errors.append(f"dashboard JS missing {needle}")

style_text = read("static/css/style.css")
for needle in (
    "gear-trip-card",
    "gear-trip-context-grid",
    "gear-trip-recommendation",
    "gear-pack-grid",
    "gear-trip-mini-list",
    "catch-gear-grid",
    "catch-row",
):
    if needle not in style_text:
        errors.append(f"style.css missing {needle}")

marker = json.loads(read("data/version_v6_13_gear_intelligence_packing_catch_linking.json"))
if marker.get("version") != "v6.13-gear-intelligence-packing-catch-linking":
    errors.append("Version marker mismatch")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    inventory_path = tmp / "gear_inventory.json"
    settings_path = tmp / "gear_settings.json"
    cache_path = tmp / "gear_catalog_cache.json"
    _write_json(inventory_path, {"version": "v6.13-gear-intelligence-packing-catch-linking", "updated_at": "2026-07-17T00:00:00", "items": [], "maintenance": [], "catalog_cache": []})
    _write_json(settings_path, {
        "version": "v6.13-gear-intelligence-packing-catch-linking",
        "updated_at": "2026-07-17T00:00:00",
        "search_scope_default": "both",
        "online_lookup_enabled": False,
        "enabled_providers": {"structured": True, "manufacturer": False, "walmart": False, "amazon": False},
        "allow_remote_images": False,
        "cache_lookup_results": True,
        "cache_duration_days": 30,
        "prefer_manufacturer_specs": True,
    })
    _write_json(cache_path, {"version": "v6.13-gear-intelligence-packing-catch-linking", "updated_at": "2026-07-17T00:00:00", "products": []})

    os.environ["AI_GEAR_INVENTORY_PATH"] = str(inventory_path)
    os.environ["AI_GEAR_SETTINGS_PATH"] = str(settings_path)
    os.environ["AI_GEAR_CATALOG_CACHE_PATH"] = str(cache_path)

    import app as app_module
    from app import app as flask_app

    # Keep this integration fixture out of the user's JSON-authoritative catch
    # log. The route retains its production behavior; only this QC path moves.
    app_module.CATCHES_FILE = tmp / "catches.json"
    _write_json(app_module.CATCHES_FILE, [])

    client = flask_app.test_client()

    for route in ("/rigs", "/tackle-locker"):
        res = client.get(route)
        if res.status_code != 200:
            errors.append(f"{route} returned HTTP {res.status_code}")
            continue
        html = res.get_data(as_text=True)
        for needle in ("My Tackle Locker", "Recommended Setup for Current Trip", "Fishing Rig Reference"):
            if needle not in html:
                errors.append(f"{route} missing {needle}")
        if "/admin" in html:
            errors.append(f"{route} should not expose admin navigation")

    payloads = [
        {
            "category": "rod",
            "brand": "St. Croix",
            "model": "Mojo Bass",
            "display_name": "St. Croix Mojo Bass 7'1\" MH Fast",
            "status": "owned",
            "favorite": True,
            "length_ft": 7.08,
            "length_label": "7'1\"",
            "power": "medium_heavy",
            "action": "fast",
            "lure_weight_min_oz": 0.25,
            "lure_weight_max_oz": 1.0,
            "line_rating_min_lb": 12,
            "line_rating_max_lb": 20,
            "technique_tags": "spinnerbait, jig, chatterbait",
            "species_tags": "largemouth_bass, smallmouth_bass",
            "maintenance_interval_days": 90,
        },
        {
            "category": "reel",
            "brand": "Shimano",
            "model": "Curado DC 150",
            "display_name": "Shimano Curado DC 150",
            "status": "owned",
            "favorite": True,
            "reel_type": "baitcasting",
            "gear_ratio": 7.4,
            "max_drag_lb": 11,
        },
        {
            "category": "line",
            "brand": "PowerPro",
            "model": "Super 8 Slick",
            "display_name": "PowerPro Super 8 Slick 30 lb",
            "status": "owned",
            "line_type": "braid",
            "strength_lb": 30,
            "color": "moss_green",
            "length_yd": 150,
            "maintenance_interval_days": 120,
        },
        {
            "category": "lure",
            "brand": "Strike King",
            "model": "Premier Plus Spinnerbait",
            "display_name": "Strike King Premier Plus Spinnerbait",
            "status": "owned",
            "favorite": True,
            "lure_type": "spinnerbait",
            "color": "white_chartreuse",
            "weight_oz": 0.375,
            "species_tags": "largemouth_bass",
            "technique_tags": "steady_retrieve, slow_roll",
        },
        {
            "category": "terminal",
            "brand": "Owner",
            "model": "Hooks",
            "display_name": "Owner 3/0 Hooks",
            "status": "owned",
            "subtype": "hook",
            "size": "3/0",
            "quantity": 10,
        },
    ]

    created = {}
    for payload in payloads:
        res = client.post("/api/gear/items", json=payload)
        if res.status_code != 200:
            errors.append(f"Create gear item failed for {payload.get('category')} with HTTP {res.status_code}")
            continue
        item = (res.get_json(silent=True) or {}).get("item", {})
        if not item.get("id"):
            errors.append(f"Create gear item did not return an id for {payload.get('category')}")
            continue
        created[payload["category"]] = item

    rec_res = client.get("/api/gear/recommendation", query_string={
        "species": "Largemouth Bass",
        "expected_fish_weight": "3",
        "lure_type": "spinnerbait",
        "lure_weight_oz": "0.375",
        "technique": "steady_retrieve",
        "cover": "vegetation",
        "clarity": "stained",
    })
    if rec_res.status_code != 200:
        errors.append(f"/api/gear/recommendation failed with HTTP {rec_res.status_code}")
    else:
        rec_data = rec_res.get_json(silent=True) or {}
        rec = rec_data.get("recommendation") or {}
        packing = rec_data.get("packing_list") or {}
        if not rec_data.get("ok"):
            errors.append("/api/gear/recommendation should return ok")
        if rec.get("score", 0) <= 0:
            errors.append("Recommendation score should be positive for the QC setup")
        if not rec.get("lure") or not rec.get("rod"):
            errors.append("Recommendation should include a rod and lure")
        if not packing.get("core"):
            errors.append("Packing list should include core gear")

    catch_payload = {
        "zip": "60543",
        "species": "Largemouth Bass",
        "lure": "White/Chartreuse Spinnerbait",
        "waterbody": "QC Pond",
        "notes": "QC catch",
        "rod_id": created.get("rod", {}).get("id", ""),
        "reel_id": created.get("reel", {}).get("id", ""),
        "line_id": created.get("line", {}).get("id", ""),
        "lure_id": created.get("lure", {}).get("id", ""),
        "terminal_id": created.get("terminal", {}).get("id", ""),
    }
    catch_res = client.post("/api/catches", json=catch_payload)
    saved_catch_id = ""
    if catch_res.status_code != 200:
        errors.append(f"Catch save with gear links failed with HTTP {catch_res.status_code}")
    else:
        catch = catch_res.get_json(silent=True) or {}
        saved_catch_id = str(catch.get("id") or "")
        if not catch.get("gear_summary"):
            errors.append("Catch response should include a gear summary")
        if not catch.get("gear_labels", {}).get("lure"):
            errors.append("Catch response should include gear labels")

    catches_res = client.get("/api/catches")
    if catches_res.status_code != 200:
        errors.append(f"/api/catches failed with HTTP {catches_res.status_code}")
    else:
        catches = catches_res.get_json(silent=True) or []
        saved = next((item for item in catches if str(item.get("id") or "") == saved_catch_id), {})
        if not saved.get("gear_summary"):
            errors.append("Catch log should include enriched gear summary text")

    inventory_res = client.get("/api/gear/items")
    if inventory_res.status_code != 200:
        errors.append(f"/api/gear/items failed with HTTP {inventory_res.status_code}")
    else:
        inventory = inventory_res.get_json(silent=True) or {}
        items = inventory.get("items") if isinstance(inventory, dict) else []
        rod = next((item for item in items if item.get("category") == "rod"), {})
        lure = next((item for item in items if item.get("category") == "lure"), {})
        if not rod.get("last_used") or int(rod.get("trips_used") or 0) <= 0:
            errors.append("Rod usage should update after catch save")
        if int(lure.get("catches_logged") or 0) <= 0:
            errors.append("Lure catches_logged should update after catch save")


if errors:
    for error in errors:
        print(error)
    raise SystemExit(1)

print("v6.13 gear intelligence / packing / catch-linking QC passed")
