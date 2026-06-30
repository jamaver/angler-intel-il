#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

SPECIES_PATH = DATA_DIR / "species_profiles_v43.json"
RIGS_PATH = DATA_DIR / "lure_rig_setups_v43.json"
WATERS_PATH = DATA_DIR / "illinois_waters.json"
MANUAL_WATERS_PATH = DATA_DIR / "manual_waters.json"
SETTINGS_PATH = DATA_DIR / "species_settings_v431.json"
VERSION_PATH = DATA_DIR / "app_version.json"

KNOWN_LURE_IDS = {
    "spinnerbait",
    "jig",
    "micro-jig",
    "microjig",
    "spoon",
    "minnow",
    "worm",
    "walleye-jig",
    "walleyejig",
    "topwater",
    "catfish-bait",
    "catfishbait",
    "pike-wire-leader",
    "trout-float-rig",
}


def read_json(path: Path) -> tuple[bool, Any, str | None]:
    if not path.exists():
        return False, None, "missing"

    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return True, None, "empty"
        return True, json.loads(text), None
    except Exception as exc:
        return True, None, str(exc)


def ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    out = set()
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            out.add(str(item["id"]))
    return out


def duplicate_ids(items: Any) -> list[str]:
    seen = set()
    dupes = set()
    if not isinstance(items, list):
        return []
    for item in items:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if not sid:
            continue
        if sid in seen:
            dupes.add(sid)
        seen.add(sid)
    return sorted(dupes)


def validate() -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    exists_species, species, err_species = read_json(SPECIES_PATH)
    exists_rigs, rigs, err_rigs = read_json(RIGS_PATH)
    exists_waters, waters, err_waters = read_json(WATERS_PATH)
    exists_manual_waters, manual_waters, err_manual_waters = read_json(MANUAL_WATERS_PATH)
    exists_settings, settings, err_settings = read_json(SETTINGS_PATH)
    exists_version, version, err_version = read_json(VERSION_PATH)

    files = {
        "species_profiles": {
            "path": str(SPECIES_PATH),
            "exists": exists_species,
            "valid": err_species is None,
            "error": err_species,
        },
        "rig_setups": {
            "path": str(RIGS_PATH),
            "exists": exists_rigs,
            "valid": err_rigs is None,
            "error": err_rigs,
        },
        "illinois_waters": {
            "path": str(WATERS_PATH),
            "exists": exists_waters,
            "valid": err_waters is None,
            "error": err_waters,
        },
        "manual_waters": {
            "path": str(MANUAL_WATERS_PATH),
            "exists": exists_manual_waters,
            "valid": err_manual_waters is None,
            "error": err_manual_waters,
        },
        "species_settings": {
            "path": str(SETTINGS_PATH),
            "exists": exists_settings,
            "valid": err_settings is None,
            "error": err_settings,
        },
        "app_version": {
            "path": str(VERSION_PATH),
            "exists": exists_version,
            "valid": err_version is None,
            "error": err_version,
        },
    }

    for name, info in files.items():
        if not info["exists"]:
            issues.append(f"{name} file is missing")
        elif not info["valid"]:
            issues.append(f"{name} file is invalid JSON: {info['error']}")

    species_ids = ids(species)
    rig_ids = ids(rigs)
    for label, data in [("species", species), ("rigs", rigs), ("waters", waters), ("manual_waters", manual_waters)]:
        dupes = duplicate_ids(data)
        if dupes:
            issues.append(f"{label} has duplicate IDs: {', '.join(dupes)}")

    if isinstance(species, list):
        for item in species:
            if not isinstance(item, dict):
                issues.append("species list contains non-object item")
                continue
            for key in ("id", "name", "group", "best_lures", "habitat", "quick_pattern"):
                if key not in item:
                    issues.append(f"species {item.get('id', 'unknown')} missing {key}")

    if isinstance(settings, dict):
        active = settings.get("active_species", [])
        if not isinstance(active, list):
            issues.append("species_settings active_species must be a list")
        else:
            for sid in active:
                if sid not in species_ids:
                    issues.append(f"active species references missing species id: {sid}")

    if isinstance(rigs, list):
        for rig in rigs:
            if not isinstance(rig, dict):
                issues.append("rig list contains non-object item")
                continue

            rid = rig.get("id", "unknown")
            lure_id = rig.get("lure_id") or rig.get("id")
            if lure_id not in KNOWN_LURE_IDS:
                warnings.append(f"rig {rid} has unrecognized lure_id: {lure_id}")

            for sid in rig.get("species_ids", []):
                if sid not in species_ids:
                    warnings.append(f"rig {rid} references unknown species id: {sid}")

    if isinstance(waters, list):
        for water in waters:
            if not isinstance(water, dict):
                issues.append("waters list contains non-object item")
                continue

            wid = water.get("id", "unknown")
            for key in ("id", "name", "type", "lat", "lon"):
                if key not in water:
                    issues.append(f"water {wid} missing {key}")

            for sid in water.get("species_ids", []):
                if sid not in species_ids:
                    warnings.append(f"water {wid} references unknown species id: {sid}")

    if isinstance(manual_waters, list):
        for water in manual_waters:
            if not isinstance(water, dict):
                issues.append("manual_waters list contains non-object item")
                continue

            wid = water.get("id", "unknown")
            for key in ("id", "name", "type", "lat", "lon"):
                if key not in water:
                    issues.append(f"manual water {wid} missing {key}")

            for sid in water.get("species_ids", []):
                if sid not in species_ids:
                    warnings.append(f"manual water {wid} references unknown species id: {sid}")

    return {
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "counts": {
            "species": len(species) if isinstance(species, list) else 0,
            "rigs": len(rigs) if isinstance(rigs, list) else 0,
            "waters": len(waters) if isinstance(waters, list) else 0,
            "manual_waters": len(manual_waters) if isinstance(manual_waters, list) else 0,
            "active_species": len(settings.get("active_species", [])) if isinstance(settings, dict) and isinstance(settings.get("active_species"), list) else 0,
        },
        "files": files,
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)
