#!/usr/bin/env python3
"""Regression coverage for the dashboard's focused-water forecast contract."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
JS_PATH = ROOT / "static" / "js" / "app.js"
CSS_PATH = ROOT / "static" / "css" / "style.css"


def main() -> int:
    errors: list[str] = []
    try:
        ast.parse(APP_PATH.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"app.py syntax error: {exc}")

    js = JS_PATH.read_text(encoding="utf-8")
    css = CSS_PATH.read_text(encoding="utf-8")
    for needle in ("scoreText", "emptyDashboardPanel", "Hourly bite forecast is unavailable", "7-day forecast is unavailable"):
        if needle not in js:
            errors.append(f"dashboard JS missing {needle!r}")
    if "dashboard-panel-empty" not in css:
        errors.append("dashboard CSS is missing the forecast empty-state style")

    try:
        syntax = subprocess.run(["node", "--check", str(JS_PATH)], capture_output=True, text=True)
        if syntax.returncode:
            errors.append(f"app.js syntax error: {syntax.stderr.strip() or syntax.stdout.strip()}")
    except FileNotFoundError:
        errors.append("node is required for app.js syntax validation")

    sys.path.insert(0, str(ROOT))
    from app import app as flask_app  # Imported after static checks.

    client = flask_app.test_client()
    map_response = client.get("/api/map-data")
    map_payload = map_response.get_json(silent=True) or {}
    waters = map_payload.get("top_waters") or map_payload.get("waters") or []
    water = next((item for item in waters if isinstance(item, dict) and item.get("id")), None)
    if map_response.status_code != 200 or not water:
        errors.append("could not obtain a mapped waterbody for focused-dashboard QC")
    else:
        response = client.get(f"/api/intel?zip=60543&water_id={water['id']}")
        payload = response.get_json(silent=True) or {}
        if response.status_code != 200:
            errors.append(f"focused /api/intel failed with HTTP {response.status_code}")
        else:
            overall = payload.get("overall") or {}
            if not isinstance(overall.get("score"), (int, float)):
                errors.append("focused intelligence is missing overall score")
            if not isinstance(payload.get("time_blocks"), list) or not payload["time_blocks"]:
                errors.append("focused intelligence is missing bite windows")
            if not isinstance(payload.get("hourly"), list) or not payload["hourly"]:
                errors.append("focused intelligence is missing hourly bite forecast")
            if not isinstance(payload.get("forecast"), list) or len(payload["forecast"]) < 1:
                errors.append("focused intelligence is missing 7-day forecast")
            if not isinstance((payload.get("water") or {}).get("local_score"), (int, float)):
                errors.append("focused water is missing a Map Brief score")

    if errors:
        print("QC FAILED: dashboard focused forecast contract")
        for error in errors:
            print(f"- {error}")
        return 1

    print("QC PASSED: dashboard focused forecast contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
