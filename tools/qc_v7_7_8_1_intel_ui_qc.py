#!/usr/bin/env python3
"""Focused QC for V7.7.8.1 evidence integrity and ordered target UI."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import intelligence.target_profile as profile


def main() -> int:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    report_source = (ROOT / "angler_reports_v38.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    js = (ROOT / "static/js/app.js").read_text(encoding="utf-8")

    ast.parse(app_source)
    ast.parse(report_source)
    assert "record_water_species_observation" not in report_source, "report save must not create species evidence"
    assert "water_species_update" not in report_source, "report response must not imply an observation update"
    assert "record_water_species_observation" in app_source, "catch observation hook disappeared"

    old_reader = profile._read_profile_document
    old_loader = profile.load_target_profile
    old_authority = profile.require_write_authority
    old_writer = profile._write_json
    old_mirror = profile.mirror_target_profile
    captured = {}
    try:
        profile._read_profile_document = lambda: {"current_trip_target": "Bluegill"}  # type: ignore[assignment]
        assert profile.load_target_profile()["current_trip_targets"] == ["Bluegill"]
        profile.load_target_profile = lambda: {"current_trip_target": "Bluegill", "current_trip_targets": ["Bluegill"], "favorite_species": []}  # type: ignore[assignment]
        profile.require_write_authority = lambda *_args: "json"  # type: ignore[assignment]
        profile._write_json = lambda _path, payload: captured.update(payload)  # type: ignore[assignment]
        profile.mirror_target_profile = lambda *_args: {"ok": True}  # type: ignore[assignment]
        saved = profile.save_target_profile({"current_trip_targets": ["Walleye", "Crappie", "Walleye"]})
        assert saved["current_trip_targets"] == ["Walleye", "Crappie"]
        assert saved["current_trip_target"] == "Walleye"
        assert captured["current_trip_targets"] == ["Walleye", "Crappie"]
    finally:
        profile._read_profile_document = old_reader
        profile.load_target_profile = old_loader
        profile.require_write_authority = old_authority
        profile._write_json = old_writer
        profile.mirror_target_profile = old_mirror

    assert 'id="primaryTargetSpecies"' in template
    assert 'id="secondaryTargetSpecies"' in template
    assert 'id="addSecondaryTargetButton"' in template
    assert 'id="targetSpecies" multiple' not in template
    assert "selectedOptions" not in js
    for phrase in ("primary target drives today", "secondary targets are saved for planning context"):
        assert phrase in template.lower()
    assert "Admin" not in template

    marker = json.loads((ROOT / "data/version_v7_7_8_1_intel_ui_qc.json").read_text(encoding="utf-8"))
    assert marker["live_personal_ranking_enabled"] is False
    assert marker["data_authority_changed"] is False
    print("PASS: V7.7.8.1 intelligence integrity and ordered target UI QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
