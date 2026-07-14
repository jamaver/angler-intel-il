#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app.py"
TEMPLATE_PATH = ROOT / "templates" / "index.html"
JS_PATH = ROOT / "static" / "js" / "app.js"
CSS_PATH = ROOT / "static" / "css" / "style.css"
MARKER_PATH = ROOT / "data" / "version_v6_2_dashboard_consolidation.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    try:
        ast.parse(read(APP_PATH))
    except Exception as exc:  # pragma: no cover - qc utility
        errors.append(f"app.py did not parse: {exc}")

    template = read(TEMPLATE_PATH)
    app_js = read(JS_PATH)
    css = read(CSS_PATH)

    for needle, label in [
        ("dashboard-command-center", "dashboard command center shell"),
        ("dashboard-secondary-stack", "dashboard secondary stack"),
        ("dashboard-accordion", "dashboard accordion"),
        ("tripPlan", "trip plan container"),
        ("smartIntelligence", "smart intelligence container"),
        ("bestBet", "best bet container"),
        ("bestTime", "best time container"),
        ("conditions", "conditions container"),
        ("lureCards", "lure cards container"),
        ("hourly", "hourly forecast container"),
        ("timeBlocks", "bite windows container"),
        ("species", "species container"),
        ("waters", "waters container"),
        ("forecast", "forecast container"),
        ("catchInsights", "catch insights container"),
        ("catchLog", "catch log container"),
    ]:
        if needle not in template:
            errors.append(f"templates/index.html missing {label}")

    if "dashboard_sections_v431.js" in template:
        errors.append("dashboard section controls script is still included in the dashboard")

    for needle, label in [
        ("trip-plan-hero", "trip plan hero styles"),
        ("trip-plan-fish-art", "trip plan fish art styles"),
        ("trip-plan-lure", "trip plan lure styles"),
        ("dashboard-command-center", "command center styles"),
        ("dashboard-accordion", "accordion styles"),
        ("dashboard-panel-compact", "compact panel styles"),
    ]:
        if needle not in css:
            errors.append(f"style.css missing {label}")

    release_label_present = (
        "v6.2-dashboard-consolidation" in app_js
        or "v6.2-dashboard-consolidation" in read(APP_PATH)
        or "v6.4-report-planning-polish" in app_js
        or "v6.4-report-planning-polish" in read(APP_PATH)
    )
    if not release_label_present:
        errors.append("app.js/app.py missing release label")

    for needle, label in [
        ("trip-plan-hero", "trip plan hero render"),
        ("trip-plan-fish-art", "trip plan fish image render"),
        ("trip-plan-lure", "trip plan lure image render"),
        ("trip-plan-condition-row", "trip plan condition chips"),
        ("trip-plan-reason-list", "trip plan reason list"),
    ]:
        if needle not in app_js and needle not in read(APP_PATH):
            errors.append(f"app.js/app.py missing {label}")

    if not MARKER_PATH.exists():
        errors.append("v6.2 dashboard consolidation marker is missing")
    else:
        marker = json.loads(read(MARKER_PATH))
        if marker.get("version") != "v6.2-dashboard-consolidation":
            errors.append("dashboard consolidation marker version mismatch")
        for key in (
            "dashboard_consolidation",
            "trip_plan_primary",
            "secondary_sections_collapsed",
            "map_first_flow",
            "smart_intelligence_preserved",
            "catch_learning_preserved",
            "fish_and_lure_assets_preserved",
            "app_health_maintenance_only",
            "admin_not_in_normal_nav",
        ):
            if not marker.get(key):
                errors.append(f"dashboard consolidation marker missing {key}")

    if errors:
        print("QC failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("QC passed: dashboard consolidation layout and release markers are in place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
