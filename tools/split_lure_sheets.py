#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

APP_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = APP_ROOT / "static" / "lures" / "source_sheets"
LURE_ROOT = APP_ROOT / "static" / "lures"
PREVIEW_PATH = LURE_ROOT / "_preview" / "lure_asset_contact_sheet.png"
GENERIC_PATH = LURE_ROOT / "generic_lure.png"


@dataclass(frozen=True)
class AssetSpec:
    sheet: str
    output: str
    box: tuple[int, int, int, int]


def box(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
    return (x0, y0, x1, y1)


LAYOUTS = [
    AssetSpec("jig_variants_sheet.png", "jig/green_pumpkin.png", box(0, 70, 520, 540)),
    AssetSpec("jig_variants_sheet.png", "jig/black_blue.png", box(430, 70, 1040, 540)),
    AssetSpec("jig_variants_sheet.png", "jig/brown_orange_craw.png", box(925, 70, 1448, 540)),
    AssetSpec("jig_variants_sheet.png", "jig/white_shad.png", box(60, 500, 760, 1086)),
    AssetSpec("jig_variants_sheet.png", "jig/pbj.png", box(680, 500, 1448, 1086)),
    AssetSpec("crankbait_variants_sheet.png", "crankbait/shad.png", box(0, 50, 760, 360)),
    AssetSpec("crankbait_variants_sheet.png", "crankbait/bluegill.png", box(688, 50, 1448, 360)),
    AssetSpec("crankbait_variants_sheet.png", "crankbait/craw_red.png", box(0, 330, 760, 760)),
    AssetSpec("crankbait_variants_sheet.png", "crankbait/chartreuse_black_back.png", box(688, 330, 1448, 760)),
    AssetSpec("crankbait_variants_sheet.png", "crankbait/sexy_shad.png", box(0, 680, 760, 1086)),
    AssetSpec("crankbait_variants_sheet.png", "crankbait/firetiger.png", box(688, 680, 1448, 1086)),
    AssetSpec("spinnerbait_variants_sheet.png", "spinnerbait/white_silver.png", box(0, 70, 500, 520)),
    AssetSpec("spinnerbait_variants_sheet.png", "spinnerbait/chartreuse_white.png", box(440, 70, 990, 520)),
    AssetSpec("spinnerbait_variants_sheet.png", "spinnerbait/gold_shiner.png", box(920, 70, 1448, 520)),
    AssetSpec("spinnerbait_variants_sheet.png", "spinnerbait/bluegill.png", box(60, 500, 760, 1086)),
    AssetSpec("spinnerbait_variants_sheet.png", "spinnerbait/black_night.png", box(680, 500, 1448, 1086)),
    AssetSpec("soft_plastic_worm_variants_sheet.png", "soft_plastic_worm/green_pumpkin.png", box(0, 50, 760, 360)),
    AssetSpec("soft_plastic_worm_variants_sheet.png", "soft_plastic_worm/watermelon_red.png", box(688, 50, 1448, 360)),
    AssetSpec("soft_plastic_worm_variants_sheet.png", "soft_plastic_worm/black_blue.png", box(0, 330, 760, 760)),
    AssetSpec("soft_plastic_worm_variants_sheet.png", "soft_plastic_worm/junebug.png", box(688, 330, 1448, 760)),
    AssetSpec("soft_plastic_worm_variants_sheet.png", "soft_plastic_worm/natural_shad.png", box(0, 680, 760, 1086)),
    AssetSpec("soft_plastic_worm_variants_sheet.png", "soft_plastic_worm/white_pearl.png", box(688, 680, 1448, 1086)),
    AssetSpec("swimbait_variants_sheet.png", "swimbait/pearl_white.png", box(0, 70, 760, 520)),
    AssetSpec("swimbait_variants_sheet.png", "swimbait/shad.png", box(688, 70, 1448, 520)),
    AssetSpec("swimbait_variants_sheet.png", "swimbait/bluegill.png", box(0, 320, 760, 760)),
    AssetSpec("swimbait_variants_sheet.png", "swimbait/green_pumpkin.png", box(688, 320, 1448, 760)),
    AssetSpec("swimbait_variants_sheet.png", "swimbait/ayu.png", box(230, 700, 1218, 1086)),
    AssetSpec("topwater_popper_variants_sheet.png", "topwater_popper/bone.png", box(0, 70, 520, 540)),
    AssetSpec("topwater_popper_variants_sheet.png", "topwater_popper/frog_green.png", box(430, 70, 1040, 540)),
    AssetSpec("topwater_popper_variants_sheet.png", "topwater_popper/black.png", box(925, 70, 1448, 540)),
    AssetSpec("topwater_popper_variants_sheet.png", "topwater_popper/shad.png", box(60, 500, 760, 1086)),
    AssetSpec("topwater_popper_variants_sheet.png", "topwater_popper/chrome_blue.png", box(680, 500, 1448, 1086)),
    AssetSpec("frog_variants_sheet.png", "frog/green_frog.png", box(0, 70, 520, 540)),
    AssetSpec("frog_variants_sheet.png", "frog/black_frog.png", box(430, 70, 1040, 540)),
    AssetSpec("frog_variants_sheet.png", "frog/white_frog.png", box(925, 70, 1448, 540)),
    AssetSpec("frog_variants_sheet.png", "frog/leopard_frog.png", box(60, 500, 760, 1086)),
    AssetSpec("frog_variants_sheet.png", "frog/brown_frog.png", box(680, 500, 1448, 1086)),
    AssetSpec("spoon_variants_sheet.png", "spoon/silver.png", box(0, 70, 520, 540)),
    AssetSpec("spoon_variants_sheet.png", "spoon/gold.png", box(430, 70, 1040, 540)),
    AssetSpec("spoon_variants_sheet.png", "spoon/blue_silver.png", box(925, 70, 1448, 540)),
    AssetSpec("spoon_variants_sheet.png", "spoon/firetiger.png", box(60, 500, 760, 1086)),
    AssetSpec("spoon_variants_sheet.png", "spoon/chartreuse.png", box(680, 500, 1448, 1086)),
    AssetSpec("inline_spinner_variants_sheet.png", "inline_spinner/silver.png", box(0, 0, 760, 560)),
    AssetSpec("inline_spinner_variants_sheet.png", "inline_spinner/gold.png", box(688, 0, 1448, 560)),
    AssetSpec("inline_spinner_variants_sheet.png", "inline_spinner/firetiger.png", box(0, 520, 760, 1086)),
    AssetSpec("inline_spinner_variants_sheet.png", "inline_spinner/chartreuse.png", box(688, 520, 1448, 1086)),
    AssetSpec("drop_shot_variants_sheet.png", "drop_shot/green_pumpkin.png", box(0, 50, 760, 560)),
    AssetSpec("drop_shot_variants_sheet.png", "drop_shot/shad.png", box(688, 50, 1448, 560)),
    AssetSpec("drop_shot_variants_sheet.png", "drop_shot/morning_dawn.png", box(0, 520, 760, 1086)),
    AssetSpec("drop_shot_variants_sheet.png", "drop_shot/watermelon_red.png", box(688, 520, 1448, 1086)),
]


def ensure_dirs() -> None:
    (LURE_ROOT / "_preview").mkdir(parents=True, exist_ok=True)
    for rel in {spec.output.split("/")[0] for spec in LAYOUTS}:
        (LURE_ROOT / rel).mkdir(parents=True, exist_ok=True)


def load_sheet(name: str) -> Image.Image:
    path = SOURCE_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing source sheet: {path}")
    return Image.open(path).convert("RGB")


def estimate_background(crop: Image.Image) -> tuple[int, int, int]:
    arr = np.asarray(crop.convert("RGB"), dtype=np.uint8)
    samples = np.concatenate(
        [
            arr[:16, :16].reshape(-1, 3),
            arr[:16, -16:].reshape(-1, 3),
            arr[-16:, :16].reshape(-1, 3),
            arr[-16:, -16:].reshape(-1, 3),
        ],
        axis=0,
    )
    return tuple(int(v) for v in np.median(samples, axis=0))


def trim_subject(crop: Image.Image, pad: int = 28) -> Image.Image:
    rgb = np.asarray(crop.convert("RGB"), dtype=np.int16)
    bg = np.array(estimate_background(crop), dtype=np.int16)
    delta = np.abs(rgb - bg).sum(axis=2)
    value = rgb.max(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    mask = (delta > 24) | (chroma > 14) | (value < 240)

    if not mask.any():
        return crop

    mask_img = Image.fromarray((mask.astype(np.uint8) * 255), "L").filter(ImageFilter.MaxFilter(5))
    bbox = mask_img.getbbox()
    if not bbox:
        return crop

    x0, y0, x1, y1 = bbox
    x0 = max(x0 - pad, 0)
    y0 = max(y0 - pad, 0)
    x1 = min(x1 + pad, crop.width)
    y1 = min(y1 + pad, crop.height)

    if (x1 - x0) * (y1 - y0) >= int(crop.width * crop.height * 0.97):
        return crop

    return crop.crop((x0, y0, x1, y1))


def make_generic_lure() -> Image.Image:
    canvas = Image.new("RGBA", (1200, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    body = (220, 320, 900, 460)
    tail = (820, 340, 1010, 450)
    head = (180, 300, 320, 490)

    draw.rounded_rectangle(body, radius=72, fill=(125, 125, 130, 255), outline=(35, 35, 35, 255), width=8)
    draw.ellipse(head, fill=(150, 150, 155, 255), outline=(35, 35, 35, 255), width=6)
    draw.polygon([(900, 360), (1090, 295), (1085, 505), (900, 450)], fill=(110, 110, 115, 255))
    draw.line((112, 252, 250, 430), fill=(65, 65, 70, 255), width=8)
    draw.line((112, 252, 250, 430), fill=(180, 180, 180, 90), width=2)
    draw.ellipse((250, 345, 315, 410), fill=(240, 240, 240, 220))
    draw.ellipse((270, 360, 298, 388), fill=(20, 20, 20, 255))
    draw.line((1010, 398, 1125, 405), fill=(35, 35, 35, 255), width=7)
    draw.line((1010, 398, 1110, 368), fill=(35, 35, 35, 255), width=7)
    draw.line((1010, 398, 1110, 435), fill=(35, 35, 35, 255), width=7)
    draw.line((1010, 398, 1128, 398), fill=(190, 190, 190, 80), width=2)

    return canvas


def save_asset(sheet: Image.Image, spec: AssetSpec) -> Path:
    crop = sheet.crop(spec.box)
    trimmed = trim_subject(crop)
    out_path = LURE_ROOT / spec.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    trimmed.save(out_path)
    return out_path


def build_preview(paths: list[Path]) -> None:
    if not paths:
        return

    tile_w = 320
    tile_h = 260
    cols = 4
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * tile_w + 40, rows * tile_h + 40), (10, 17, 30, 255))
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    for index, path in enumerate(paths):
        row = index // cols
        col = index % cols
        x = 20 + col * tile_w
        y = 20 + row * tile_h
        tile = Image.new("RGBA", (tile_w - 20, tile_h - 42), (22, 32, 47, 255))
        try:
            asset = Image.open(path).convert("RGBA")
            asset.thumbnail((tile.width - 20, tile.height - 20), Image.Resampling.LANCZOS)
            ax = (tile.width - asset.width) // 2
            ay = (tile.height - asset.height) // 2
            tile.alpha_composite(asset, (ax, ay))
        except Exception:
            pass
        sheet.alpha_composite(tile, (x, y))
        draw.rectangle((x, y, x + tile.width, y + tile.height), outline=(96, 165, 250, 80), width=1)
        label = path.relative_to(LURE_ROOT).as_posix()
        draw.text((x + 8, y + tile.height + 4), label, fill=(226, 232, 240, 255), font=font)

    sheet.save(PREVIEW_PATH)


def main() -> int:
    if not SOURCE_DIR.exists():
        raise SystemExit(f"Missing source sheet directory: {SOURCE_DIR}")

    missing = [name for name in sorted({spec.sheet for spec in LAYOUTS}) if not (SOURCE_DIR / name).exists()]
    if missing:
        raise SystemExit("Missing source sheets: " + ", ".join(missing))

    ensure_dirs()

    generated: list[Path] = []
    sheet_cache: dict[str, Image.Image] = {}
    for spec in LAYOUTS:
        sheet = sheet_cache.get(spec.sheet)
        if sheet is None:
            sheet = load_sheet(spec.sheet)
            sheet_cache[spec.sheet] = sheet
        generated.append(save_asset(sheet, spec))

    if not GENERIC_PATH.exists():
        make_generic_lure().save(GENERIC_PATH)

    build_preview(generated + [GENERIC_PATH])
    print(f"Generated {len(generated)} lure assets")
    print(f"Preview: {PREVIEW_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
