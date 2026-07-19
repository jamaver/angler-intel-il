#!/usr/bin/env python3
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(path: str, errors: list[str]) -> None:
    p = ROOT / path
    if not p.exists():
        errors.append(f"Missing {path}")
    elif p.stat().st_size <= 0:
        errors.append(f"Empty {path}")


def parse(path: str, errors: list[str]) -> None:
    try:
        ast.parse((ROOT / path).read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path} parse error: {exc}")


def run_script(path: Path, errors: list[str]) -> None:
    print(f"RUN {path.name}", flush=True)
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        errors.append(f"{path.name} failed:\n{proc.stdout}\n{proc.stderr}")
    else:
        print(f"OK  {path.name}", flush=True)


def client_check(path: str, needle: str, client, errors: list[str]) -> None:
    res = client.get(path)
    if res.status_code != 200:
        errors.append(f"{path} failed with HTTP {res.status_code}")
        return
    html = res.get_data(as_text=True)
    if needle and needle not in html:
        errors.append(f"{path} missing expected text: {needle}")


def isolated_gear_checks(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        inventory_path = tmp / "gear_inventory.json"
        cache_path = tmp / "gear_catalog_cache.json"
        settings_path = tmp / "gear_settings.json"
        catches_path = tmp / "catches.json"
        os.environ["AI_GEAR_INVENTORY_PATH"] = str(inventory_path)
        os.environ["AI_GEAR_CATALOG_CACHE_PATH"] = str(cache_path)
        os.environ["AI_GEAR_SETTINGS_PATH"] = str(settings_path)

        from gear import inventory as gear_inventory
        from gear import product_url_import
        from intelligence.gear_intelligence import recommend_owned_setup
        from app import app as flask_app

        gear_inventory.CATCHES_PATH = catches_path
        import app as app_module
        app_module.CATCHES_FILE = catches_path

        client = flask_app.test_client()

        if client.get("/rigs").status_code != 200:
            errors.append("/rigs failed in isolated gear QC")
        if client.get("/tackle-locker").status_code != 200:
            errors.append("/tackle-locker failed in isolated gear QC")

        rod_payload = {
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
        }
        lure_payload = {
            "category": "lure",
            "brand": "Strike King",
            "model": "Premier Plus Spinnerbait",
            "display_name": "Strike King Premier Plus Spinnerbait",
            "lure_type": "spinnerbait",
            "color": "white_chartreuse",
            "weight_oz": 0.375,
            "species_tags": "largemouth_bass",
            "technique_tags": "steady_retrieve, slow_roll",
            "status": "owned",
            "favorite": True,
        }

        rod_res = client.post("/api/gear/items", json=rod_payload)
        lure_res = client.post("/api/gear/items", json=lure_payload)
        if rod_res.status_code != 200 or lure_res.status_code != 200:
            errors.append("Creating isolated gear items failed")
            return

        rod_item = (rod_res.get_json(silent=True) or {}).get("item", {})
        lure_item = (lure_res.get_json(silent=True) or {}).get("item", {})
        if not rod_item.get("id") or not lure_item.get("id"):
            errors.append("Isolated gear item ids missing")
            return
        if not str(rod_item.get("fallback_image", "")).startswith("/static/gear/fallback/"):
            errors.append("Missing gear image should use fallback")

        archive_res = client.post(f"/api/gear/items/{rod_item['id']}/retire")
        if archive_res.status_code != 200:
            errors.append("Retire route failed in isolated gear QC")
        restore_res = client.post(f"/api/gear/items/{rod_item['id']}/restore")
        if restore_res.status_code != 200:
            errors.append("Restore route failed in isolated gear QC")
        if (restore_res.get_json(silent=True) or {}).get("item", {}).get("status") != "owned":
            errors.append("Restore route did not return item to owned status")

        catches_path.write_text(json.dumps([
            {
                "id": "qc-catch-1",
                "gear_refs": {"rod": rod_item["id"]},
                "gear_labels": {"rod": rod_item.get("display_name")},
                "species": "Largemouth Bass",
            }
        ], indent=2), encoding="utf-8")
        blocked = client.post(f"/api/gear/items/{rod_item['id']}/delete")
        if blocked.status_code != 409:
            errors.append("Referenced gear delete should be blocked")
        blocked_data = blocked.get_json(silent=True) or {}
        if blocked_data.get("reference_count", 0) < 1:
            errors.append("Blocked delete should report references")

        # Remove the reference and confirm a delete succeeds.
        catches_path.write_text("[]", encoding="utf-8")
        deleted = client.post(f"/api/gear/items/{lure_item['id']}/delete")
        if deleted.status_code != 200:
            errors.append("Unreferenced gear delete should succeed")

        upload = client.post(
            "/api/gear/upload-image",
            data={"image": (io.BytesIO(b"not-a-real-image"), "gear.png")},
            content_type="multipart/form-data",
        )
        if upload.status_code != 200:
            errors.append("Image upload route should accept image/png uploads")

        bad_upload = client.post(
            "/api/gear/upload-image",
            data={"image": (io.BytesIO(b"plain text"), "gear.txt")},
            content_type="multipart/form-data",
        )
        if bad_upload.status_code == 200:
            errors.append("Non-image uploads should be rejected")

        rec = recommend_owned_setup(
            "largemouth bass",
            expected_fish_weight=3.0,
            lure_type="spinnerbait",
            lure_weight_oz=0.375,
            technique="steady_retrieve",
            habitat="pond",
            cover="vegetation",
            conditions={"clarity": "stained", "time_of_day": "evening"},
            owned_gear=[rod_item, lure_item],
        )
        if not rec.get("confidence_notes"):
            errors.append("Recommendation should include confidence notes")
        rod_choice = rec.get("rod") if isinstance(rec, dict) else {}
        if not rod_choice or not rod_choice.get("specifications_used"):
            errors.append("Recommendation should expose specifications_used")
        if not rec.get("warnings"):
            errors.append("Recommendation should include warnings or guidance")

        generic = product_url_import.normalize_structured_product(
            {
                "provider": "structured",
                "provider_product_id": "qc-rod",
                "source_name": "QC Source",
                "source_url": "https://example.com/qc-rod",
                "category": "rod",
                "brand": "Site Maintenance",
                "model": "Site Maintenance",
                "display_name": "Site Maintenance",
                "image_url": "",
                "specifications": {"length_label": "7'1\"", "power": "medium_heavy"},
                "identifiers": {},
                "confidence": "low",
                "raw_provider_data_cached": False,
                "page_is_generic": True,
            },
            source_url="https://example.com/qc-rod",
            category="rod",
            allow_remote_images=False,
        )
        if generic.get("brand") == "Site Maintenance" or generic.get("display_name") == "Site Maintenance":
            errors.append("Generic pages should not preserve maintenance text as product identity")


def route_smoke_checks(errors: list[str]) -> None:
    from app import app as flask_app

    client = flask_app.test_client()
    client_check("/", "Angler Intel", client, errors)
    client_check("/map", "Map", client, errors)
    client_check("/recommendations", "Smart Picks", client, errors)
    client_check("/waters", "Local Waters", client, errors)
    client_check("/reports", "Saved Reports", client, errors)
    client_check("/rigs", "My Tackle Locker", client, errors)
    client_check("/app-health", "App Health", client, errors)


def main() -> int:
    errors: list[str] = []
    required_files = [
        "app.py",
        "angler_species_rigs_v43.py",
        "gear/inventory.py",
        "gear/settings.py",
        "gear/product_url_import.py",
        "intelligence/gear_intelligence.py",
        "tools/app_backup.py",
        "templates/tackle_locker.html",
        "static/js/tackle_locker_v610.js",
        "docs/RUNTIME_DATA_POLICY.md",
        "docs/V7_GEAR_DATA_MODEL.md",
        "docs/V7_MIGRATION_PLAN.md",
        "tools/qc_tackle_locker.py",
        "tools/qc_gear_catalog_search.py",
        "tools/qc_smart_trip_report_display.py",
        "tools/qc_dashboard_consolidation.py",
        "tools/qc_ui_cleanup_preview.py",
        "tools/qc_shell_consolidation.py",
        "tools/qc_reports_backup_delete.py",
        "tools/qc_smart_trip_forecast_date.py",
    ]
    for rel in required_files:
        require(rel, errors)
    for rel in ("app.py", "angler_species_rigs_v43.py", "gear/inventory.py", "gear/settings.py", "gear/product_url_import.py", "intelligence/gear_intelligence.py", "tools/app_backup.py"):
        parse(rel, errors)

    route_smoke_checks(errors)

    isolated_gear_checks(errors)

    for script_name in (
        "qc_tackle_locker.py",
        "qc_gear_catalog_search.py",
        "qc_smart_trip_report_display.py",
        "qc_smart_trip_forecast_date.py",
        "qc_dashboard_consolidation.py",
        "qc_ui_cleanup_preview.py",
        "qc_shell_consolidation.py",
        "qc_reports_backup_delete.py",
        "qc_v6_7_waterbody_detail_refinement.py",
        "qc_v6_13_gear_intelligence_packing_catch_linking.py",
        "qc_v6_9_dashboard_cohesion.py",
        "qc_v5_9_1_species_image_assets.py",
        "qc_v5_5_realistic_icon_system.py",
    ):
        script = ROOT / "tools" / script_name
        if script.exists():
            run_script(script, errors)

    if errors:
        print("QC FAILED: pre-v7 stabilization")
        for error in errors:
            print(f"- {error}")
        return 1

    print("QC PASSED: pre-v7 stabilization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
