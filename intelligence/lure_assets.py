from __future__ import annotations

from pathlib import Path
import re
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
LURE_ROOT = APP_ROOT / "static" / "lures"

TYPE_SYNONYMS = [
    ("jig", "jig"),
    ("football jig", "jig"),
    ("flipping jig", "jig"),
    ("swim jig", "jig"),
    ("crankbait", "crankbait"),
    ("crank", "crankbait"),
    ("squarebill", "crankbait"),
    ("diving crankbait", "crankbait"),
    ("spinnerbait", "spinnerbait"),
    ("spinner bait", "spinnerbait"),
    ("worm", "soft_plastic_worm"),
    ("soft plastic", "soft_plastic_worm"),
    ("stick bait", "soft_plastic_worm"),
    ("senko", "soft_plastic_worm"),
    ("texas rig", "soft_plastic_worm"),
    ("topwater popper", "topwater_popper"),
    ("topwater frog", "topwater_popper"),
    ("swimbait", "swimbait"),
    ("paddle tail", "swimbait"),
    ("paddletail", "swimbait"),
    ("popper", "topwater_popper"),
    ("walking bait", "topwater_popper"),
    ("frog", "frog"),
    ("hollow body frog", "frog"),
    ("topwater frog", "frog"),
    ("spoon", "spoon"),
    ("inline spinner", "inline_spinner"),
    ("rooster tail", "inline_spinner"),
    ("spinner", "inline_spinner"),
    ("drop shot", "drop_shot"),
    ("dropshot", "drop_shot"),
    ("finesse rig", "drop_shot"),
]

COLOR_SYNONYMS = [
    ("green pumpkin", "green_pumpkin"),
    ("gp", "green_pumpkin"),
    ("black and blue", "black_blue"),
    ("black blue", "black_blue"),
    ("black/blue", "black_blue"),
    ("black blue jig", "black_blue"),
    ("brown orange", "brown_orange_craw"),
    ("orange craw", "brown_orange_craw"),
    ("crawdad", "brown_orange_craw"),
    ("crawfish", "brown_orange_craw"),
    ("craw", "brown_orange_craw"),
    ("shad", "shad"),
    ("natural shad", "natural_shad"),
    ("white shad", "white_shad"),
    ("white", "white_shad"),
    ("pearl white", "pearl_white"),
    ("pearl", "pearl_white"),
    ("chartreuse white", "chartreuse_white"),
    ("chartreuse black back", "chartreuse_black_back"),
    ("bluegill", "bluegill"),
    ("sunfish", "bluegill"),
    ("firetiger", "firetiger"),
    ("fire tiger", "firetiger"),
    ("bone", "bone"),
    ("black night", "black_night"),
    ("black", "black"),
    ("junebug", "junebug"),
    ("watermelon red", "watermelon_red"),
    ("morning dawn", "morning_dawn"),
    ("pbj", "pbj"),
    ("peanut butter jelly", "pbj"),
    ("gold shiner", "gold_shiner"),
    ("gold", "gold"),
    ("silver", "silver"),
    ("white silver", "white_silver"),
    ("white/silver", "white_silver"),
    ("chrome blue", "chrome_blue"),
    ("chrome/blue", "chrome_blue"),
    ("frog green", "frog_green"),
    ("leopard frog", "leopard_frog"),
    ("brown frog", "brown_frog"),
    ("ayu", "ayu"),
]

TYPE_LABELS = {
    "jig": "Jig",
    "crankbait": "Crankbait",
    "spinnerbait": "Spinnerbait",
    "soft_plastic_worm": "Soft Plastic Worm",
    "swimbait": "Swimbait",
    "topwater_popper": "Topwater Popper",
    "frog": "Frog",
    "spoon": "Spoon",
    "inline_spinner": "Inline Spinner",
    "drop_shot": "Drop Shot",
}

TYPE_DEFAULT_COLOR = {
    "jig": "green_pumpkin",
    "crankbait": "shad",
    "spinnerbait": "white_silver",
    "soft_plastic_worm": "green_pumpkin",
    "swimbait": "shad",
    "topwater_popper": "bone",
    "frog": "green_frog",
    "spoon": "silver",
    "inline_spinner": "silver",
    "drop_shot": "green_pumpkin",
}

TYPE_ALTERNATES = {
    "jig": ["green_pumpkin", "black_blue", "brown_orange_craw", "white_shad", "pbj"],
    "crankbait": ["shad", "bluegill", "craw_red", "chartreuse_black_back", "sexy_shad", "firetiger"],
    "spinnerbait": ["white_silver", "chartreuse_white", "gold_shiner", "bluegill", "black_night"],
    "soft_plastic_worm": ["green_pumpkin", "watermelon_red", "black_blue", "junebug", "natural_shad", "white_pearl"],
    "swimbait": ["pearl_white", "shad", "bluegill", "green_pumpkin", "ayu"],
    "topwater_popper": ["bone", "frog_green", "black", "shad", "chrome_blue"],
    "frog": ["green_frog", "black_frog", "white_frog", "leopard_frog", "brown_frog"],
    "spoon": ["silver", "gold", "blue_silver", "firetiger", "chartreuse"],
    "inline_spinner": ["silver", "gold", "firetiger", "chartreuse"],
    "drop_shot": ["green_pumpkin", "shad", "morning_dawn", "watermelon_red"],
}


def _slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _clean_key(value: Any) -> str:
    return _slugify(value).replace(" ", "_")


def _match_synonym(text: str, mapping: list[tuple[str, str]]) -> str | None:
    for needle, replacement in mapping:
        if needle in text:
            return replacement
    return None


def _resolve_type(text: str, explicit: str | None = None) -> str | None:
    key = _clean_key(explicit) if explicit else ""
    if key in TYPE_LABELS:
        return key
    return _match_synonym(text, TYPE_SYNONYMS)


def _resolve_color(text: str, lure_type: str | None = None, explicit: str | None = None) -> str | None:
    key = _clean_key(explicit) if explicit else ""
    if key:
        return key

    if lure_type == "spinnerbait" and "chartreuse" in text:
        return "chartreuse_white"
    if lure_type == "swimbait" and "white" in text:
        return "pearl_white"
    if lure_type == "topwater_popper" and "white" in text:
        return "bone"

    direct = _match_synonym(text, COLOR_SYNONYMS)
    if direct:
        if direct == "craw_red" and lure_type == "jig":
            return "brown_orange_craw"
        if direct == "white" and lure_type == "spinnerbait":
            return "white_silver"
        if direct == "white" and lure_type == "swimbait":
            return "pearl_white"
        if direct == "white" and lure_type == "jig":
            return "white_shad"
        if direct == "black" and lure_type == "spinnerbait":
            return "black_night"
        return direct

    if lure_type == "jig":
        if "pbj" in text:
            return "pbj"
        if "black" in text and "blue" in text:
            return "black_blue"
        if "craw" in text:
            return "brown_orange_craw"
        if "white" in text:
            return "white_shad"
    elif lure_type == "crankbait":
        if "firetiger" in text or "fire tiger" in text:
            return "firetiger"
        if "chartreuse" in text and "black" in text:
            return "chartreuse_black_back"
        if "craw" in text:
            return "craw_red"
        if "bluegill" in text:
            return "bluegill"
        if "sexy shad" in text:
            return "sexy_shad"
        if "shad" in text:
            return "shad"
    elif lure_type == "spinnerbait":
        if "black" in text and "night" in text:
            return "black_night"
        if "chartreuse" in text:
            return "chartreuse_white"
        if "gold" in text and "shiner" in text:
            return "gold_shiner"
        if "bluegill" in text:
            return "bluegill"
        if "silver" in text or "white" in text:
            return "white_silver"
    elif lure_type == "soft_plastic_worm":
        if "watermelon" in text and "red" in text:
            return "watermelon_red"
        if "junebug" in text:
            return "junebug"
        if "black" in text and "blue" in text:
            return "black_blue"
        if "white" in text or "pearl" in text:
            return "white_pearl"
        if "natural" in text and "shad" in text:
            return "natural_shad"
        if "green" in text and "pumpkin" in text:
            return "green_pumpkin"
    elif lure_type == "swimbait":
        if "green" in text and "pumpkin" in text:
            return "green_pumpkin"
        if "bluegill" in text:
            return "bluegill"
        if "ayu" in text:
            return "ayu"
        if "pearl" in text or "white" in text:
            return "pearl_white"
        if "shad" in text:
            return "shad"
    elif lure_type == "topwater_popper":
        if "chrome" in text and "blue" in text:
            return "chrome_blue"
        if "frog" in text and "green" in text:
            return "frog_green"
        if "black" in text:
            return "black"
        if "shad" in text:
            return "shad"
        if "bone" in text or "white" in text:
            return "bone"
    elif lure_type == "frog":
        if "leopard" in text:
            return "leopard_frog"
        if "brown" in text:
            return "brown_frog"
        if "black" in text:
            return "black_frog"
        if "white" in text:
            return "white_frog"
        if "frog" in text or "green" in text:
            return "green_frog"
    elif lure_type == "spoon":
        if "blue" in text and "silver" in text:
            return "blue_silver"
        if "firetiger" in text or "fire tiger" in text:
            return "firetiger"
        if "chartreuse" in text:
            return "chartreuse"
        if "gold" in text:
            return "gold"
        if "silver" in text:
            return "silver"
    elif lure_type == "inline_spinner":
        if "firetiger" in text or "fire tiger" in text:
            return "firetiger"
        if "chartreuse" in text:
            return "chartreuse"
        if "gold" in text:
            return "gold"
        if "silver" in text:
            return "silver"
    elif lure_type == "drop_shot":
        if "morning dawn" in text:
            return "morning_dawn"
        if "watermelon" in text and "red" in text:
            return "watermelon_red"
        if "shad" in text:
            return "shad"
        if "green" in text and "pumpkin" in text:
            return "green_pumpkin"

    return None


def _asset_exists(lure_type: str, color: str) -> bool:
    return (LURE_ROOT / lure_type / f"{color}.png").exists()


def _label_from(type_name: str, color_name: str) -> str:
    type_label = TYPE_LABELS.get(type_name, "Lure")
    color_label = color_name.replace("_", " ").title()
    return f"{color_label} {type_label}" if type_name != "generic" else "Lure"


def resolve_lure_asset(
    recommendation_text: Any = None,
    lure_type: Any = None,
    color: Any = None,
) -> dict[str, Any]:
    text = _slugify(recommendation_text)
    resolved_type = _resolve_type(text, str(lure_type) if lure_type is not None else None)

    if not resolved_type:
        return {
            "type": "generic",
            "color": "generic",
            "label": "Lure",
            "path": "/static/lures/generic_lure.png",
            "fallback_used": True,
            "filename": "generic_lure.png",
        }

    resolved_color = _resolve_color(text, resolved_type, str(color) if color is not None else None)
    candidates: list[str] = []

    if resolved_color:
        candidates.append(resolved_color)
    default_color = TYPE_DEFAULT_COLOR.get(resolved_type)
    if default_color and default_color not in candidates:
        candidates.append(default_color)
    for alt in TYPE_ALTERNATES.get(resolved_type, []):
        if alt not in candidates:
            candidates.append(alt)

    for candidate in candidates:
        if _asset_exists(resolved_type, candidate):
            return {
                "type": resolved_type,
                "color": candidate,
                "label": _label_from(resolved_type, candidate),
                "path": f"/static/lures/{resolved_type}/{candidate}.png",
                "fallback_used": candidate != resolved_color,
                "filename": f"{candidate}.png",
            }

    return {
        "type": resolved_type,
        "color": resolved_color or default_color or "generic",
        "label": _label_from(resolved_type, resolved_color or default_color or "generic"),
        "path": "/static/lures/generic_lure.png",
        "fallback_used": True,
        "filename": "generic_lure.png",
    }
