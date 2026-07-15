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


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


for rel in (
    "app.py",
    "angler_species_rigs_v43.py",
    "gear/inventory.py",
    "gear/catalog_providers.py",
    "templates/tackle_locker.html",
    "static/js/tackle_locker_v610.js",
    "data/version_v6_10_tackle_locker.json",
    "docs/MY_TACKLE_LOCKER.md",
):
    require(rel)

for rel in ("app.py", "angler_species_rigs_v43.py", "gear/inventory.py", "gear/catalog_providers.py"):
    path = ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

template_text = read("templates/tackle_locker.html")
if "My Tackle Locker" not in template_text:
    errors.append("Tackle locker page should be titled My Tackle Locker")
if "Fishing Rig Reference" not in template_text:
    errors.append("Fishing rig reference should remain at the bottom")
if "gearForm" not in template_text or "catalogSearchButton" not in template_text:
    errors.append("Tackle locker template should include add and catalog controls")
if "/admin" in template_text:
    errors.append("Admin should not appear in tackle locker navigation")

style_text = read("static/css/style.css")
for needle in ("gear-shell", "gear-item-card", "gear-reference-grid", "gear-form-columns"):
    if needle not in style_text:
        errors.append(f"style.css missing {needle}")

js_text = read("static/js/tackle_locker_v610.js")
for needle in ("submitForm", "searchCatalog", "favorite", "archive", "syncCategoryFields"):
    if needle not in js_text:
        errors.append(f"Locker JS missing {needle}")

marker = json.loads(read("data/version_v6_10_tackle_locker.json"))
if marker.get("version") != "v6.10-tackle-locker":
    errors.append("Version marker mismatch")

with tempfile.TemporaryDirectory() as tmpdir:
    inventory_path = Path(tmpdir) / "gear_inventory.json"
    cache_path = Path(tmpdir) / "gear_catalog_cache.json"
    os.environ["AI_GEAR_INVENTORY_PATH"] = str(inventory_path)
    os.environ["AI_GEAR_CATALOG_CACHE_PATH"] = str(cache_path)

    from app import app as flask_app

    client = flask_app.test_client()

    for route in ("/rigs", "/tackle-locker"):
        res = client.get(route)
        if res.status_code != 200:
            errors.append(f"{route} failed with HTTP {res.status_code}")
        else:
            html = res.get_data(as_text=True)
            if "My Tackle Locker" not in html:
                errors.append(f"{route} missing My Tackle Locker heading")
            if "Fishing Rig Reference" not in html:
                errors.append(f"{route} missing Fishing Rig Reference section")
            if "/admin" in html:
                errors.append(f"{route} should not expose admin navigation")

    initial = client.get("/api/gear/items")
    if initial.status_code != 200:
        errors.append(f"/api/gear/items failed with HTTP {initial.status_code}")
    else:
        data = initial.get_json(silent=True) or {}
        if not data.get("ok"):
            errors.append("/api/gear/items should return ok")
        if data.get("summary", {}).get("total") != 0:
            errors.append("Fresh gear inventory should start empty in QC temp storage")

    payloads = [
        {
            "category": "rod",
            "brand": "St. Croix",
            "model": "Mojo Bass",
            "display_name": "St. Croix Mojo Bass 7'1\" MH Fast",
            "length_ft": 7.08,
            "length_label": "7'1\"",
            "power": "medium_heavy",
            "action": "fast",
            "pieces": 1,
            "lure_weight_min_oz": 0.25,
            "lure_weight_max_oz": 1.0,
            "line_rating_min_lb": 12,
            "line_rating_max_lb": 20,
            "technique_tags": "spinnerbait, jig, chatterbait",
            "species_tags": "largemouth_bass, smallmouth_bass",
            "status": "owned",
            "favorite": True,
            "notes": "QC rod",
        },
        {
            "category": "reel",
            "brand": "Shimano",
            "model": "Curado DC 150",
            "display_name": "Shimano Curado DC 150",
            "reel_type": "baitcasting",
            "gear_ratio": 7.4,
            "max_drag_lb": 11,
            "line_capacity": "12 lb / 120 yd",
            "weight_oz": 7.8,
            "handedness": "right",
            "status": "owned",
        },
        {
            "category": "line",
            "brand": "PowerPro",
            "model": "Super 8 Slick",
            "display_name": "PowerPro Super 8 Slick 30 lb",
            "line_type": "braid",
            "strength_lb": 30,
            "diameter_equivalent": ".008 in",
            "color": "moss_green",
            "length_yd": 150,
            "status": "owned",
        },
        {
            "category": "lure",
            "brand": "Strike King",
            "model": "Premier Plus Spinnerbait",
            "display_name": "Strike King Premier Plus Spinnerbait",
            "lure_type": "spinnerbait",
            "color": "white_chartreuse",
            "weight_oz": 0.375,
            "species_tags": "largemouth_bass",
            "technique_tags": "steady_retrieve, slow_roll",
            "quantity": 2,
            "image": "",
            "status": "owned",
            "favorite": True,
        },
        {
            "category": "terminal",
            "brand": "Owner",
            "model": "Hooks",
            "display_name": "Owner 3/0 Hooks",
            "subtype": "hook",
            "size": "3/0",
            "quantity": 10,
            "status": "owned",
        },
    ]

    created_ids: list[str] = []
    for payload in payloads:
        res = client.post("/api/gear/items", json=payload)
        if res.status_code != 200:
            errors.append(f"Create gear item failed for {payload.get('category')} with HTTP {res.status_code}")
            continue
        data = res.get_json(silent=True) or {}
        item = data.get("item") if isinstance(data, dict) else {}
        if not isinstance(item, dict) or not item.get("id"):
            errors.append(f"Create gear item did not return an id for {payload.get('category')}")
            continue
        created_ids.append(item["id"])
        if not item.get("fallback_image", "").startswith("/static/gear/fallback/") and payload.get("image") == "":
            errors.append("Missing image should use a fallback gear image")

    if created_ids:
        edit_id = created_ids[0]
        res = client.post("/api/gear/items", json={
            "id": edit_id,
            "category": "rod",
            "brand": "St. Croix",
            "model": "Mojo Bass",
            "display_name": "St. Croix Mojo Bass 7'1\" MH Fast",
            "notes": "Updated rod note",
        })
        if res.status_code != 200:
            errors.append("Editing gear item failed")
        else:
            item = (res.get_json(silent=True) or {}).get("item", {})
            if item.get("notes") != "Updated rod note":
                errors.append("Editing gear item did not persist updates")

        fav_res = client.post(f"/api/gear/items/{edit_id}/favorite", json={"favorite": True})
        if fav_res.status_code != 200:
            errors.append("Favorite toggle failed")
        else:
            item = (fav_res.get_json(silent=True) or {}).get("item", {})
            if not item.get("favorite"):
                errors.append("Favorite toggle did not mark item as favorite")

        archive_res = client.post(f"/api/gear/items/{edit_id}/archive")
        if archive_res.status_code != 200:
            errors.append("Archive route failed")
        else:
            item = (archive_res.get_json(silent=True) or {}).get("item", {})
            if item.get("status") != "retired":
                errors.append("Archive route did not retire the gear item")

    full = client.get("/api/gear/items")
    if full.status_code != 200:
        errors.append("Reloading gear inventory failed")
    else:
        data = full.get_json(silent=True) or {}
        if data.get("summary", {}).get("total") != len(created_ids):
            errors.append("Gear inventory total count did not match created items")

    search_res = client.get("/api/gear/catalog/search?q=Curado&category=reel")
    if search_res.status_code != 200:
        errors.append("Catalog search route failed")
    else:
        data = search_res.get_json(silent=True) or {}
        if not data.get("ok"):
            errors.append("Catalog search should return ok")
        if "products" not in data:
            errors.append("Catalog search should return products list")

    rigs_res = client.get("/api/rigs?species=bass")
    if rigs_res.status_code != 200:
        errors.append("/api/rigs should remain available for dashboard rig bridge")

if errors:
    print("QC FAILED: tackle locker")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: tackle locker")

