"""Safe ZIP extraction for backup and restore tooling."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath


def validate_member(root: Path, member: zipfile.ZipInfo) -> Path:
    name = member.filename
    pure = PurePosixPath(name)
    if not name or "\\" in name or pure.is_absolute() or ".." in pure.parts:
        raise RuntimeError(f"Unsafe archive path: {name}")
    target = root / pure
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Unsafe archive path: {name}") from exc
    return target


def safe_extract(archive: str | Path, root: str | Path) -> None:
    destination = Path(root)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as bundle:
        members = [(member, validate_member(destination, member)) for member in bundle.infolist()]
        for member, target in members:
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
