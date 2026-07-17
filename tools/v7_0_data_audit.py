#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.importers import source_file_summaries
from persistence.provenance import file_sha256
from persistence.runtime_paths import DOMAIN_ENV_VARS, resolve_runtime_path

DATA = ROOT / "data"
REPORTS = ROOT / "reports"
EXPORTS = DATA / "exports"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _mode_string(mode: int) -> str:
    return stat.filemode(mode)


def _owner_string(path: Path) -> str:
    try:
        st = path.stat()
        user = str(st.st_uid)
        group = str(st.st_gid)
        try:
            import pwd
            import grp

            user = pwd.getpwuid(st.st_uid).pw_name
            group = grp.getgrgid(st.st_gid).gr_name
        except Exception:
            pass
        return f"{user}:{group}"
    except Exception:
        return ""


def _file_record(path: Path, *, optional: bool = True) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "optional": optional,
    }
    if not path.exists():
        return record
    stat_result = path.stat()
    record.update(
        {
            "type": "dir" if path.is_dir() else "file",
            "size": stat_result.st_size if path.is_file() else None,
            "mode": _mode_string(stat_result.st_mode),
            "owner": _owner_string(path),
            "modified_at": datetime.fromtimestamp(stat_result.st_mtime).isoformat(timespec="seconds"),
            "sha256": file_sha256(path) if path.is_file() else None,
        }
    )
    return record


def _scan_reports() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not REPORTS.exists():
        return rows
    for pattern, kind in (("*.json", "report_json"), ("*.html", "report_html")):
        for path in sorted(REPORTS.glob(pattern)):
            rows.append(_file_record(path))
            rows[-1]["kind"] = kind
    return rows


def _runtime_path_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    definitions = {
        "gear_inventory": {
            "env_var": DOMAIN_ENV_VARS["gear_inventory"],
            "legacy_path": DATA / "gear_inventory.json",
            "repo_default": DATA / "gear_inventory.json",
        },
        "manual_waters": {
            "env_var": DOMAIN_ENV_VARS["manual_waters"],
            "legacy_path": DATA / "manual_waters.json",
            "repo_default": DATA / "manual_waters.json",
        },
        "target_profile": {
            "env_var": DOMAIN_ENV_VARS["target_profile"],
            "legacy_path": DATA / "target_profile.json",
            "repo_default": DATA / "target_profile.json",
        },
        "gear_settings": {
            "env_var": DOMAIN_ENV_VARS["gear_settings"],
            "legacy_path": DATA / "gear_settings.json",
            "repo_default": DATA / "gear_settings.json",
        },
        "catches": {
            "env_var": DOMAIN_ENV_VARS["catches"],
            "legacy_path": DATA / "catches.json",
            "repo_default": DATA / "catches.json",
        },
        "favorites": {
            "env_var": DOMAIN_ENV_VARS["favorites"],
            "legacy_path": DATA / "favorites.json",
            "repo_default": DATA / "favorites.json",
        },
        "reports_index": {
            "env_var": DOMAIN_ENV_VARS["reports_index"],
            "legacy_path": DATA / "reports_index.json",
            "repo_default": DATA / "reports_index.json",
        },
        "sqlite": {
            "env_var": DOMAIN_ENV_VARS["sqlite"],
            "legacy_path": DATA / "angler_intel.sqlite3",
            "repo_default": DATA / "angler_intel.sqlite3",
        },
        "exports_dir": {
            "env_var": DOMAIN_ENV_VARS["exports_dir"],
            "legacy_path": DATA / "exports",
            "repo_default": DATA / "exports",
        },
        "gear_uploads": {
            "env_var": DOMAIN_ENV_VARS["gear_uploads"],
            "legacy_path": DATA / "gear_uploads",
            "repo_default": DATA / "gear_uploads",
        },
    }
    for domain, definition in definitions.items():
        resolved = resolve_runtime_path(
            domain,
            env_var=definition.get("env_var"),
            legacy_path=definition.get("legacy_path"),
            repo_default=definition.get("repo_default"),
        )
        records.append(
            {
                "domain": domain,
                "resolved_path": str(resolved.path),
                "source": resolved.source,
                "conflict": resolved.conflict,
                "conflict_paths": resolved.conflict_paths,
                "exists": resolved.path.exists(),
                "mode": _mode_string(resolved.path.stat().st_mode) if resolved.path.exists() else None,
                "owner": _owner_string(resolved.path) if resolved.path.exists() else None,
            }
        )
    return records


def audit() -> dict[str, Any]:
    source_records = source_file_summaries()
    runtime_records = _runtime_path_records()
    known_files = [
        DATA / "catches.json",
        DATA / "favorites.json",
        DATA / "gear_inventory.json",
        DATA / "gear_settings.json",
        DATA / "illinois_waters.json",
        DATA / "manual_waters.json",
        DATA / "reports_index.json",
        DATA / "species_profiles_v43.json",
        DATA / "species_settings_v431.json",
        DATA / "target_profile.json",
        DATA / "angler_intel.sqlite3",
        DATA / "gear_catalog_cache.json",
        DATA / "gear_uploads",
    ]
    report_files = _scan_reports()

    missing_optional = [record["path"] for record in source_records if not record.get("exists") and record.get("domain") not in {"species_settings"}]
    conflicts = [record for record in runtime_records if record.get("conflict")]

    return {
        "generated_at": _now(),
        "root": str(ROOT),
        "git_commit": os.environ.get("GIT_COMMIT", ""),
        "source_files": source_records,
        "runtime_paths": runtime_records,
        "reports": report_files,
        "files": [_file_record(path, optional=True) for path in known_files],
        "missing_optional": missing_optional,
        "conflicts": conflicts,
        "summary": {
            "source_file_count": len(source_records),
            "report_file_count": len(report_files),
            "conflict_count": len(conflicts),
            "missing_optional_count": len(missing_optional),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Angler Intel V7 runtime data audit")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--output", help="Write JSON to PATH")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on conflicts or missing optional data")
    args = parser.parse_args()

    payload = audit()
    rendered = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    if args.json or not args.output:
        print(rendered)

    if args.strict and (payload["conflicts"] or payload["missing_optional"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
