#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors: list[str] = []


def read(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


def require(rel: str) -> None:
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


def strip_debug_section(html: str) -> str:
    marker = "Raw saved JSON - debugging"
    if marker not in html:
        return html
    return html.split(marker, 1)[0]


for rel in ("app.py", "angler_reports_v38.py", "templates/snapshot.html", "templates/index.html", "static/css/style.css"):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py"):
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

snapshot_text = read("templates/snapshot.html") if (APP_ROOT / "templates/snapshot.html").exists() else ""
if "<details class=\"report-card report-debug-json\">" not in snapshot_text:
    errors.append("Trip report should keep a collapsed raw JSON debug section")
if "Raw saved JSON - debugging" not in snapshot_text:
    errors.append("Trip report debug section should be clearly labeled")

if not re.search(r"\.report-species-grid\s*\{[^}]*grid-template-columns:\s*1fr;", snapshot_text, re.S):
    errors.append("Trip report species ranking should use a single-column grid")
if not re.search(r"\.report-lure-grid\s*\{[^}]*grid-template-columns:\s*1fr;", snapshot_text, re.S):
    errors.append("Trip report lure recommendations should use a single-column grid")

from app import app as flask_app

client = flask_app.test_client()
payload = {
    "title": "QC Smart Trip Report",
    "zip": "60543",
    "saved_at": "2026-07-12T20:30:00",
    "intel": {
        "target_species": "Largemouth Bass",
        "overall": {"score": 84, "rating": "Excellent"},
        "weather": {
            "temp": 78.8,
            "wind": 3.5,
            "pressure": 30.12,
            "cloud": 0,
            "source": "Open-Meteo",
        },
        "best_bet": {
            "species": "Largemouth Bass",
            "species_score": 91,
            "time_label": "Evening",
            "time_range": "4 PM - 9 PM",
            "best_hour": "7 PM",
            "speed": "Medium speed",
            "size": "3/8 oz",
            "why": "Great search bait when wind and clouds help fish feed shallow.",
            "fish_image": "/static/fish/largemouth_bass.png",
            "lure_image": "/static/lures/spinnerbait/chartreuse_white.png",
            "lure_asset": {
                "type": "spinnerbait",
                "color": "chartreuse_white",
                "label": "Chartreuse White Spinnerbait",
                "path": "/static/lures/spinnerbait/chartreuse_white.png",
                "fallback_used": False,
            },
            "reasons": [
                "Detected pond-style habitat favors bass, bluegill, crappie, and catfish.",
                "Your catch log has 9 local catch records for Largemouth Bass.",
            ],
        },
        "species": [
            {
                "name": "Largemouth Bass",
                "score": 91,
                "rating": "Best match",
                "habitat": "pond, lake, reservoir",
                "fish_image": "/static/fish/largemouth_bass.png",
                "lures": {
                    "cards": {
                        "evening": {
                            "name": "Spinnerbait",
                            "species": "Largemouth Bass",
                            "species_score": 91,
                            "color": "chartreuse white",
                            "speed": "Medium retrieve",
                            "size": "3/8 oz",
                            "why": "Wind and cloud cover make this a good search bait.",
                            "lure_asset": {
                                "type": "spinnerbait",
                                "color": "chartreuse_white",
                                "label": "Chartreuse White Spinnerbait",
                                "path": "/static/lures/spinnerbait/chartreuse_white.png",
                                "fallback_used": False,
                            },
                        }
                    }
                },
            },
            {
                "name": "Bluegill",
                "score": 68,
                "rating": "Good match",
                "habitat": "shallow cover, docks",
                "fish_image": "/static/fish/bluegill.png",
                "lures": {
                    "cards": {
                        "evening": {
                            "name": "Worm",
                            "species": "Bluegill",
                            "species_score": 68,
                            "color": "green pumpkin",
                            "speed": "Slow",
                            "size": "1/16 oz",
                            "why": "Small bait under floats can be effective on calm water.",
                            "lure_asset": {
                                "type": "soft_plastic_worm",
                                "color": "green_pumpkin",
                                "label": "Green Pumpkin Worm",
                                "path": "/static/lures/soft_plastic_worm/green_pumpkin.png",
                                "fallback_used": False,
                            },
                        }
                    }
                },
            },
        ],
        "lure_cards": [
            {
                "species": "Largemouth Bass",
                "species_score": 91,
                "name": "Spinnerbait",
                "color": "chartreuse white",
                "speed": "Medium retrieve",
                "size": "3/8 oz",
                "why": "Windy shallows are a good fit.",
                "lure_asset": {
                    "type": "spinnerbait",
                    "color": "chartreuse_white",
                    "label": "Chartreuse White Spinnerbait",
                    "path": "/static/lures/spinnerbait/chartreuse_white.png",
                    "fallback_used": False,
                },
                "image": "/static/lures/spinnerbait/chartreuse_white.png",
                "top_pick": True,
            }
        ],
        "waters": [
            {"name": "Montgomery Area", "type": "River", "count": 3}
        ],
        "forecast": [
            {"date": "2026-07-12", "rating": "Excellent", "high": 86, "low": 64, "wind": 8, "score": 82},
            {"date": "2026-07-13", "rating": "Good", "high": 84, "low": 63, "wind": 6, "score": 75},
        ],
        "catch_insights": {
            "sample_size": 9,
            "note": "Small but useful local sample."
        },
    },
}

save_res = client.post("/api/reports/save?title=QC%20Smart%20Trip%20Report&zip=60543", json=payload)
if save_res.status_code != 200:
    errors.append(f"/api/reports/save failed with HTTP {save_res.status_code}")
    print("QC FAILED: smart trip report display")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

saved = save_res.get_json(silent=True) or {}
report = saved.get("report") if isinstance(saved, dict) else {}
view_url = report.get("view_url")
if not view_url:
    errors.append("Report creation did not return a view URL")
else:
    view_res = client.get(view_url)
    if view_res.status_code != 200:
        errors.append(f"{view_url} failed with HTTP {view_res.status_code}")
    else:
        html = view_res.get_data(as_text=True)
        prefix = strip_debug_section(html)
        for needle in ("lure_asset", "fish_image", "lure_image", "fallback_used", "filename", "species_score", "best_hour", "{\"date\":", "{'date':", "{\"fish_image\"", "{\"color\""):
            if needle in prefix:
                errors.append(f"Main report view still exposes {needle}")
        for needle in ("Best Bet Today", "Trip Conditions", "Species Ranking", "Recommended Lures", "7-Day Fishing Outlook"):
            if needle not in html:
                errors.append(f"Missing report section: {needle}")
        for needle in ("Species:", "Best Time:", "Lure:", "Why:"):
            if needle not in html:
                errors.append(f"Missing friendly best-bet label: {needle}")
        if "report-debug-json" not in html or "<details" not in html:
            errors.append("Trip report should keep the raw JSON in a collapsed details block")
        if 'src="/static/fish/largemouth_bass.png"' not in html and "species-icon" not in html:
            errors.append("Trip report should render fish artwork via image src")
        if 'src="/static/lures/spinnerbait/chartreuse_white.png"' not in html and "lure-art" not in html:
            errors.append("Trip report should render lure artwork via image src")
        if "report-outlook-table" not in html or "<table" not in html:
            errors.append("Trip report should render the 7-day outlook as a table")
        if "Raw saved JSON - debugging" not in html:
            errors.append("Trip report should include the raw JSON debug label")

if client.get("/").status_code != 200:
    errors.append("Dashboard failed to load")

if "/admin" in snapshot_text or "/admin" in read("templates/index.html"):
    errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: smart trip report display")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: smart trip report display")
