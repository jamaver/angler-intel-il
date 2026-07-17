from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
INSTANCE_DIR = BASE_DIR / "instance"


@dataclass(slots=True)
class ResolvedRuntimePath:
    domain: str
    path: Path
    source: str
    candidates: list[Path] = field(default_factory=list)
    conflict: bool = False
    conflict_paths: list[str] = field(default_factory=list)


DOMAIN_ENV_VARS = {
    "sqlite": "AI_SQLITE_PATH",
    "gear_inventory": "AI_GEAR_INVENTORY_PATH",
    "gear_settings": "AI_GEAR_SETTINGS_PATH",
    "gear_catalog_cache": "AI_GEAR_CATALOG_CACHE_PATH",
    "manual_waters": "AI_MANUAL_WATERS_PATH",
    "target_profile": "AI_TARGET_PROFILE_PATH",
    "favorites": "AI_FAVORITES_PATH",
    "catches": "AI_CATCHES_PATH",
    "reports_index": "AI_REPORTS_INDEX_PATH",
    "reports_dir": "AI_REPORTS_DIR",
    "gear_uploads": "AI_GEAR_UPLOADS_DIR",
    "exports_dir": "AI_EXPORTS_DIR",
    "instance_dir": "AI_INSTANCE_DIR",
}


def _existing(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return path if path.exists() else None
    except Exception:
        return None


def _resolve_instance_candidate(domain: str, filename: str | None = None) -> Path | None:
    instance_dir = os.environ.get("AI_INSTANCE_DIR", "").strip()
    if not instance_dir:
        return None
    root = Path(instance_dir)
    if filename:
        return root / filename
    return root / domain


def resolve_runtime_path(
    domain: str,
    *,
    filename: str | None = None,
    env_var: str | None = None,
    legacy_path: str | Path | None = None,
    repo_default: str | Path | None = None,
) -> ResolvedRuntimePath:
    candidates: list[tuple[str, Path]] = []

    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        if env_value:
            candidates.append(("env", Path(env_value)))

    instance_candidate = _resolve_instance_candidate(domain, filename=filename)
    if instance_candidate is not None:
        candidates.append(("instance", instance_candidate))

    if legacy_path is not None:
        candidates.append(("legacy", Path(legacy_path)))

    if repo_default is not None:
        candidates.append(("repo_default", Path(repo_default)))

    existing = [(source, path) for source, path in candidates if _existing(path) is not None]
    if existing:
        source, path = existing[0]
        conflict_paths = [str(p) for _, p in existing if p != path]
        return ResolvedRuntimePath(
            domain=domain,
            path=path,
            source=source,
            candidates=[p for _, p in candidates],
            conflict=bool(conflict_paths),
            conflict_paths=conflict_paths,
        )

    if candidates:
        source, path = candidates[0]
        return ResolvedRuntimePath(domain=domain, path=path, source=source, candidates=[p for _, p in candidates])

    fallback = Path(repo_default) if repo_default is not None else DATA_DIR / domain
    return ResolvedRuntimePath(domain=domain, path=fallback, source="repo_default", candidates=[fallback])


def resolve_runtime_paths(definitions: dict[str, dict[str, str | Path | None]]) -> dict[str, ResolvedRuntimePath]:
    return {
        domain: resolve_runtime_path(
            domain,
            filename=definition.get("filename"),
            env_var=definition.get("env_var"),
            legacy_path=definition.get("legacy_path"),
            repo_default=definition.get("repo_default"),
        )
        for domain, definition in definitions.items()
    }

