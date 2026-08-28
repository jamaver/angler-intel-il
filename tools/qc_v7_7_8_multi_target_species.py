#!/usr/bin/env python3
"""Focused QC for ordered multi-species trip targets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import intelligence.target_profile as profile


def main() -> int:
    old_reader = profile._read_profile_document
    old_loader = profile.load_target_profile
    old_authority = profile.require_write_authority
    old_writer = profile._write_json
    old_mirror = profile.mirror_target_profile
    captured = {}
    try:
        profile._read_profile_document = lambda: {"current_trip_target": "Bluegill"}  # type: ignore[assignment]
        loaded = profile.load_target_profile()
        assert loaded["current_trip_targets"] == ["Bluegill"]
        profile.load_target_profile = lambda: {"default_target_species": "Bluegill", "current_trip_target": "Bluegill", "current_trip_targets": ["Bluegill"], "favorite_species": []}  # type: ignore[assignment]
        profile.require_write_authority = lambda *_args: "json"  # type: ignore[assignment]
        profile._write_json = lambda _path, payload: captured.update(payload)  # type: ignore[assignment]
        profile.mirror_target_profile = lambda *_args: {"ok": True}  # type: ignore[assignment]
        saved = profile.save_target_profile({"current_trip_targets": ["Largemouth Bass", "Crappie", "Largemouth Bass"]})
        assert saved["current_trip_targets"] == ["Largemouth Bass", "Crappie"]
        assert saved["current_trip_target"] == "Largemouth Bass"
        assert captured["current_trip_targets"] == ["Largemouth Bass", "Crappie"]
        assert profile.resolve_target_species("", saved) == ("Largemouth Bass", "current_trip_target")
    finally:
        profile._read_profile_document = old_reader
        profile.load_target_profile = old_loader
        profile.require_write_authority = old_authority
        profile._write_json = old_writer
        profile.mirror_target_profile = old_mirror
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="primaryTargetSpecies"' in template
    assert 'id="secondaryTargetSpecies"' in template
    assert 'id="targetSpecies" multiple' not in template
    for needle in ("selectedTargetSpecies", "setTargetSpeciesSelection", "current_trip_targets"):
        assert needle in js
    assert "selectedOptions" not in js
    assert "Admin" not in template
    print("PASS: V7.7.8 multi-target species QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
