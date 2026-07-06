#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def require_pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow is required. Use the bundled Codex Python runtime or install Pillow "
            "for this interpreter."
        ) from exc
    return Image


def alpha_stats(path: Path) -> dict[str, object]:
    Image = require_pillow()
    image = Image.open(path)
    has_alpha = image.mode in {"LA", "RGBA"} or (
        image.mode == "P" and "transparency" in image.info
    )

    result: dict[str, object] = {
        "path": str(path),
        "format": image.format,
        "mode": image.mode,
        "width": image.width,
        "height": image.height,
        "has_alpha": bool(has_alpha),
    }

    if not has_alpha:
        return result

    alpha = image.convert("RGBA").getchannel("A")
    histogram = alpha.histogram()
    total = image.width * image.height
    transparent = sum(histogram[:255])
    fully_transparent = histogram[0]
    fully_opaque = histogram[255]
    semi_transparent = transparent - fully_transparent

    result.update(
        {
            "alpha_min": min(i for i, count in enumerate(histogram) if count),
            "alpha_max": max(i for i, count in enumerate(histogram) if count),
            "transparent_pixels": transparent,
            "fully_transparent_pixels": fully_transparent,
            "semi_transparent_pixels": semi_transparent,
            "fully_opaque_pixels": fully_opaque,
            "transparent_ratio": transparent / total if total else 0,
            "semi_transparent_ratio": semi_transparent / total if total else 0,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify whether an image has true alpha.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--allow-all-opaque",
        action="store_true",
        help="Exit 0 even when the file has alpha but no transparent pixels.",
    )
    args = parser.parse_args()

    stats = alpha_stats(args.image)

    if args.json:
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        for key, value in stats.items():
            print(f"{key}: {value}")

    if not stats["has_alpha"]:
        return 2

    if not args.allow_all_opaque and stats.get("transparent_pixels", 0) == 0:
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
