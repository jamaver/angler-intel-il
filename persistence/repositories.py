"""Read-selection primitives for staged V7 SQLite reads.

The framework is intentionally detached from Flask routes in V7.2.0.  JSON is
the production reader until a domain-specific cutover explicitly adopts one of
these repositories after its V7.1 soak gate passes.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from .canonical_json import canonicalize, record_hash
from .connection import DEFAULT_DB, connect

ReadSource = Literal["json", "sqlite", "sqlite_with_json_fallback", "compare_json"]
VALID_READ_SOURCES: frozenset[str] = frozenset({"json", "sqlite", "sqlite_with_json_fallback", "compare_json"})


class DomainRepository(Protocol):
    domain: str

    def read(self) -> Any: ...


@dataclass(slots=True)
class ReadResult:
    domain: str
    selected_source: ReadSource
    effective_source: str
    value: Any = None
    fallback_used: bool = False
    comparison_status: str | None = None
    comparison_differences: list[str] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)
    error: str | None = None


def _read(repository: DomainRepository) -> tuple[Any, float]:
    started = time.perf_counter()
    return repository.read(), round((time.perf_counter() - started) * 1000, 3)


def _compare(json_value: Any, sqlite_value: Any) -> tuple[str, list[str]]:
    if record_hash(json_value) == record_hash(sqlite_value):
        return "exact", []
    return "changed", ["canonical payload hash differs"]


def read_domain(
    domain: str,
    *,
    json_repository: DomainRepository,
    sqlite_repository: DomainRepository,
    source: ReadSource = "json",
) -> ReadResult:
    """Read a domain using an explicit, observable selection policy.

    ``compare_json`` always returns JSON so it can be used safely before a
    cutover. ``sqlite_with_json_fallback`` is the only mode that falls back;
    strict SQLite mode returns an error rather than silently changing source.
    """
    if source not in VALID_READ_SOURCES:
        raise ValueError(f"Unsupported read source: {source}")
    if json_repository.domain != domain or sqlite_repository.domain != domain:
        raise ValueError("Repository domain does not match requested domain")

    if source == "json":
        try:
            value, elapsed = _read(json_repository)
            return ReadResult(domain, source, "json", value=value, timing_ms={"json": elapsed})
        except Exception as exc:
            return ReadResult(domain, source, "json", error=f"JSON read failed: {type(exc).__name__}: {exc}")

    if source == "sqlite":
        try:
            value, elapsed = _read(sqlite_repository)
            return ReadResult(domain, source, "sqlite", value=value, timing_ms={"sqlite": elapsed})
        except Exception as exc:
            return ReadResult(domain, source, "sqlite", error=f"SQLite read failed: {type(exc).__name__}: {exc}")

    if source == "sqlite_with_json_fallback":
        try:
            value, elapsed = _read(sqlite_repository)
            return ReadResult(domain, source, "sqlite", value=value, timing_ms={"sqlite": elapsed})
        except Exception as sqlite_exc:
            try:
                value, elapsed = _read(json_repository)
                return ReadResult(
                    domain,
                    source,
                    "json",
                    value=value,
                    fallback_used=True,
                    timing_ms={"json": elapsed},
                    error=f"SQLite fallback: {type(sqlite_exc).__name__}: {sqlite_exc}",
                )
            except Exception as json_exc:
                return ReadResult(
                    domain,
                    source,
                    "unavailable",
                    fallback_used=True,
                    error=(f"SQLite read failed: {type(sqlite_exc).__name__}: {sqlite_exc}; "
                           f"JSON fallback failed: {type(json_exc).__name__}: {json_exc}"),
                )

    try:
        json_value, json_elapsed = _read(json_repository)
    except Exception as exc:
        return ReadResult(domain, source, "json", error=f"JSON comparison read failed: {type(exc).__name__}: {exc}")
    try:
        sqlite_value, sqlite_elapsed = _read(sqlite_repository)
        status, differences = _compare(json_value, sqlite_value)
        return ReadResult(
            domain,
            source,
            "json",
            value=json_value,
            comparison_status=status,
            comparison_differences=differences,
            timing_ms={"json": json_elapsed, "sqlite": sqlite_elapsed},
        )
    except Exception as exc:
        return ReadResult(
            domain,
            source,
            "json",
            value=json_value,
            comparison_status="sqlite_unavailable",
            comparison_differences=[f"SQLite comparison failed: {type(exc).__name__}: {exc}"],
            timing_ms={"json": json_elapsed},
        )


class JsonTargetProfileRepository:
    domain = "target_profile"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Target profile JSON must be an object")
        return canonicalize(payload)


class SQLiteTargetProfileRepository:
    domain = "target_profile"

    def __init__(self, db_path: str | Path = DEFAULT_DB, profile_id: str = "current"):
        self.db_path = Path(db_path)
        self.profile_id = profile_id

    def read(self) -> dict[str, Any]:
        with connect(self.db_path, read_only=True) as conn:
            row = conn.execute(
                "SELECT legacy_payload_json FROM target_profiles WHERE id = ?", (self.profile_id,)
            ).fetchone()
        if row is None:
            raise LookupError(f"SQLite target profile not found: {self.profile_id}")
        payload = json.loads(row["legacy_payload_json"] or "{}")
        if not isinstance(payload, dict):
            raise ValueError("SQLite target profile payload must be an object")
        return canonicalize(payload)


class JsonGearInventoryRepository:
    domain = "gear_inventory"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Gear inventory JSON must be an object")
        return canonicalize(payload)


class SQLiteGearInventoryRepository:
    domain = "gear_inventory"
    SETTING_KEY = "v7.gear_inventory.envelope"

    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)

    def read(self) -> dict[str, Any]:
        with connect(self.db_path, read_only=True) as conn:
            row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (self.SETTING_KEY,)).fetchone()
        if row is None:
            raise LookupError("SQLite gear inventory envelope not found")
        payload = json.loads(row["value_json"] or "{}")
        if not isinstance(payload, dict):
            raise ValueError("SQLite gear inventory envelope must be an object")
        return canonicalize(payload)


class JsonWaterCatalogRepository:
    domain = "waters"

    def __init__(self, loader: Callable[[], dict[str, Any]]):
        self.loader = loader

    def read(self) -> dict[str, Any]:
        payload = self.loader()
        if not isinstance(payload, dict):
            raise ValueError("Water catalog loader must return an object")
        return canonicalize(payload)


class SQLiteWaterCatalogRepository:
    domain = "waters"
    SETTING_KEY = "v7.water_catalog.envelope"

    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)

    def read(self) -> dict[str, Any]:
        with connect(self.db_path, read_only=True) as conn:
            row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (self.SETTING_KEY,)).fetchone()
        if row is None:
            raise LookupError("SQLite water catalog envelope not found")
        payload = json.loads(row["value_json"] or "{}")
        if not isinstance(payload, dict):
            raise ValueError("SQLite water catalog envelope must be an object")
        return canonicalize(payload)


class JsonCatchesRepository:
    domain = "catches"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> list[Any]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Catches JSON must be a list")
        return canonicalize(payload)


class SQLiteCatchesRepository:
    domain = "catches"
    SETTING_KEY = "v7.catches.envelope"

    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)

    def read(self) -> list[Any]:
        with connect(self.db_path, read_only=True) as conn:
            row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (self.SETTING_KEY,)).fetchone()
        if row is None:
            raise LookupError("SQLite catches envelope not found")
        payload = json.loads(row["value_json"] or "[]")
        if not isinstance(payload, list):
            raise ValueError("SQLite catches envelope must be a list")
        return canonicalize(payload)
