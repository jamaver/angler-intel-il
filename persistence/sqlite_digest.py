"""Deterministic logical content digests for SQLite runtime backups."""
from __future__ import annotations

import base64
import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float):
        # SQLite stores finite numeric values for application fields. Keeping the
        # repr avoids a platform-dependent JSON float formatting surprise.
        return {"$float": repr(value)}
    return value


def logical_database_digest(path: str | Path) -> dict[str, Any]:
    """Return table hashes for all non-transient tables and SQLite checks.

    Rows are streamed in a deterministic order. Primary-key order is preferred;
    ordinary rowid tables use rowid, which SQLite's backup API preserves.
    """
    database = Path(path)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        table_rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        table_results: dict[str, dict[str, Any]] = {}
        for table_row in table_rows:
            table = str(table_row["name"])
            columns = [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({_quote(table)})")]
            pk_columns = [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({_quote(table)})") if int(row["pk"] or 0)]
            if not columns:
                continue
            ordering = ", ".join(_quote(column) for column in pk_columns) if pk_columns else "rowid"
            digest = hashlib.sha256()
            count = 0
            query = f"SELECT {', '.join(_quote(column) for column in columns)} FROM {_quote(table)} ORDER BY {ordering}"
            try:
                cursor = conn.execute(query)
            except sqlite3.DatabaseError:
                # WITHOUT ROWID tables have no rowid. Full-column ordering is
                # deterministic for a logical comparison and avoids page bytes.
                cursor = conn.execute(
                    f"SELECT {', '.join(_quote(column) for column in columns)} FROM {_quote(table)} "
                    f"ORDER BY {', '.join(_quote(column) for column in columns)}"
                )
            for row in cursor:
                item = {column: _value(row[column]) for column in columns}
                digest.update(canonical_dumps(item).encode("utf-8"))
                digest.update(b"\n")
                count += 1
            table_results[table] = {"rows": count, "sha256": digest.hexdigest()}
        combined = hashlib.sha256(canonical_dumps(table_results).encode("utf-8")).hexdigest()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
    return {
        "database": str(database),
        "tables": table_results,
        "combined_sha256": combined,
        "integrity_check": integrity,
        "foreign_key_errors": len(foreign_keys),
        "foreign_key_check": foreign_keys,
    }


def assert_logical_database_match(source: str | Path, destination: str | Path) -> dict[str, Any]:
    left = logical_database_digest(source)
    right = logical_database_digest(destination)
    if left["integrity_check"] != "ok" or right["integrity_check"] != "ok":
        raise RuntimeError("SQLite integrity check failed during logical comparison")
    if left["foreign_key_errors"] or right["foreign_key_errors"]:
        raise RuntimeError("SQLite foreign-key check failed during logical comparison")
    if left["tables"] != right["tables"] or left["combined_sha256"] != right["combined_sha256"]:
        raise RuntimeError("Logical SQLite content digest mismatch after backup")
    return {"source": left, "destination": right, "match": True}
