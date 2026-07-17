from __future__ import annotations

import sqlite3
from pathlib import Path

from .runtime_paths import BASE_DIR, DATA_DIR

DEFAULT_DB = DATA_DIR / "angler_intel.sqlite3"


def connect(db_path: str | Path = DEFAULT_DB, *, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path)
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def db_path() -> Path:
    return DEFAULT_DB
