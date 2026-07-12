from __future__ import annotations

import re
from typing import Any

_SPECIES_IMAGE_MAP = {
    "largemouth-bass": "largemouth_bass.png",
    "smallmouth-bass": "smallmouth_bass.png",
    "crappie": "crappie.png",
    "black-crappie": "crappie.png",
    "white-crappie": "crappie.png",
    "bluegill": "bluegill.png",
    "channel-catfish": "channel_catfish.png",
    "catfish": "channel_catfish.png",
    "rainbow-trout": "rainbow_trout.png",
    "trout": "rainbow_trout.png",
    "walleye": "walleye.png",
    "sauger": "sauger.png",
    "white-bass": "white_bass.png",
    "northern-pike": "northern_pike.png",
    "pike": "northern_pike.png",
    "flathead-catfish": "channel_catfish.png",
    "brown-trout": "rainbow_trout.png",
    "muskie": "northern_pike.png",
    "musky": "northern_pike.png",
}


def _slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def get_species_image(species_name: Any) -> str:
    key = _slugify(species_name)
    if not key:
        return "/static/fish/generic_fish.png"
    filename = _SPECIES_IMAGE_MAP.get(key, "generic_fish.png")
    return f"/static/fish/{filename}"

