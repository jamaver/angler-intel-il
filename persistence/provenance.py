from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceRecord:
    domain: str
    logical_name: str
    path: str
    sha256: str | None
    record_count: int
    source_of_truth: str = "json"
    generated_only: bool = False
    last_seen_at: str | None = None
    last_imported_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

