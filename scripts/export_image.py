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


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]

    parts = [part.strip() for part in value.split(",")]
    if len(parts) == 3:
        return tuple(max(0, min(255, int(part))) for part in parts)  # type: ignore[return-value]

    raise argparse.ArgumentTypeError("Use #RRGGBB or r,g,b.")


def has_alpha(image) -> bool:
    return image.mode in {"LA", "RGBA"} or (
        image.mode == "P" and "transparency" in image.info
    )


def flatten_to_background(image, background: tuple[int, int, int]):
    Image = require_pillow()
    rgba = image.convert("RGBA")
    canvas = Image.new("RGBA", rgba.size, (*background, 255))
    canvas.alpha_composite(rgba)
    return canvas.convert("RGB")


def output_path_for_format(input_path: Path, requested_format: str, out: Path | None) -> Path:
    if out:
        return out

    suffix = {
        "png": ".png",
        "jpeg": ".jpg",
        "webp": ".webp",
    }[requested_format]
    return input_path.with_name(f"{input_path.stem}-export{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export standard or transparent image assets as PNG, JPEG, or WebP."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--format",
        required=True,
        choices=["png", "jpeg", "jpg", "webp"],
        help="Output format. jpg is normalized to jpeg.",
    )
    parser.add_argument(
        "--background",
        type=parse_color,
        default=(255, 255, 255),
        help="Flattening color for JPEG or non-alpha exports. Use #RRGGBB or r,g,b.",
    )
    parser.add_argument(
        "--preserve-alpha",
        action="store_true",
        help="Preserve alpha for PNG/WebP. Ignored for JPEG because JPEG cannot store alpha.",
    )
    parser.add_argument("--quality", type=int, default=95)
    parser.add_argument("--lossless", action="store_true", help="Use lossless WebP.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    requested_format = "jpeg" if args.format == "jpg" else args.format
    Image = require_pillow()
    image = Image.open(args.input)
    source_has_alpha = has_alpha(image)
    out_path = output_path_for_format(args.input, requested_format, args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    flattened = False

    if requested_format == "jpeg":
        output_image = flatten_to_background(image, args.background)
        output_image.save(out_path, format="JPEG", quality=args.quality, optimize=True)
        flattened = source_has_alpha
    elif requested_format == "png":
        output_image = image.convert("RGBA") if args.preserve_alpha and source_has_alpha else image.convert("RGB")
        if args.preserve_alpha and source_has_alpha:
            output_image.save(out_path, format="PNG")
        else:
            if source_has_alpha:
                output_image = flatten_to_background(image, args.background)
                flattened = True
            output_image.save(out_path, format="PNG")
    else:
        if args.preserve_alpha and source_has_alpha:
            output_image = image.convert("RGBA")
            output_image.save(
                out_path,
                format="WEBP",
                lossless=args.lossless,
                quality=args.quality,
                method=6,
            )
        else:
            output_image = flatten_to_background(image, args.background) if source_has_alpha else image.convert("RGB")
            flattened = source_has_alpha
            output_image.save(
                out_path,
                format="WEBP",
                lossless=args.lossless,
                quality=args.quality,
                method=6,
            )

    report = {
        "input": str(args.input),
        "out": str(out_path),
        "format": requested_format,
        "source_mode": image.mode,
        "source_has_alpha": source_has_alpha,
        "preserve_alpha": bool(args.preserve_alpha and requested_format in {"png", "webp"}),
        "flattened": flattened,
        "background": args.background,
        "quality": args.quality,
        "lossless": bool(args.lossless if requested_format == "webp" else False),
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
