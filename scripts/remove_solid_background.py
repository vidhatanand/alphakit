#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def require_deps():
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow and NumPy are required. Use the bundled Codex Python runtime or install "
            "Pillow and NumPy for this interpreter."
        ) from exc
    return np, Image, ImageFilter


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    parts = [part.strip() for part in value.split(",")]
    if len(parts) == 3:
        return tuple(max(0, min(255, int(part))) for part in parts)  # type: ignore[return-value]
    raise argparse.ArgumentTypeError("Use #RRGGBB or r,g,b for --bg.")


def estimate_corner_color(rgb):
    np, _Image, _ImageFilter = require_deps()
    h, w, _channels = rgb.shape
    samples = np.vstack(
        [
            rgb[: max(1, h // 20), : max(1, w // 20)].reshape(-1, 3),
            rgb[: max(1, h // 20), -max(1, w // 20) :].reshape(-1, 3),
            rgb[-max(1, h // 20) :, : max(1, w // 20)].reshape(-1, 3),
            rgb[-max(1, h // 20) :, -max(1, w // 20) :].reshape(-1, 3),
        ]
    )
    return np.median(samples, axis=0)


def remove_background_array(rgb, bg_rgb, tolerance, softness):
    np, _Image, _ImageFilter = require_deps()
    distance = np.linalg.norm(rgb - bg_rgb[None, None, :], axis=2)
    start = max(0.0, tolerance)
    end = max(start + 1.0 / 255.0, tolerance + softness)
    alpha = np.clip((distance - start) / (end - start), 0.0, 1.0)
    return alpha


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lower-confidence removal of one known solid background color."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--bg", type=parse_color, help="Background color as #RRGGBB or r,g,b.")
    parser.add_argument(
        "--auto-corners",
        action="store_true",
        help="Estimate the background color from image corners.",
    )
    parser.add_argument("--tolerance", type=float, default=0.025)
    parser.add_argument("--softness", type=float, default=0.08)
    parser.add_argument("--feather", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.bg and not args.auto_corners:
        raise SystemExit("Pass --bg or --auto-corners.")

    np, Image, ImageFilter = require_deps()
    image = Image.open(args.input).convert("RGB")
    rgb = np.asarray(image, dtype=np.float32) / 255.0
    bg_rgb = (
        np.asarray(args.bg, dtype=np.float32) / 255.0
        if args.bg
        else estimate_corner_color(rgb)
    )

    alpha = remove_background_array(rgb, bg_rgb, args.tolerance, args.softness)
    rgba = np.dstack([rgb, alpha])
    output = Image.fromarray(np.clip(rgba * 255.0 + 0.5, 0, 255).astype("uint8"), "RGBA")

    if args.feather > 0:
        alpha_channel = output.getchannel("A").filter(ImageFilter.GaussianBlur(args.feather))
        output.putalpha(alpha_channel)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.suffix.lower() == ".webp":
        output.save(args.out, format="WEBP", lossless=True, quality=100, method=6)
    else:
        output.save(args.out, format="PNG")

    report = {
        "input": str(args.input),
        "out": str(args.out),
        "width": image.width,
        "height": image.height,
        "background_rgb": [float(v) for v in bg_rgb],
        "transparent_pixels": int((alpha < 1.0 / 255.0).sum()),
        "semi_transparent_pixels": int(((alpha >= 1.0 / 255.0) & (alpha < 254.0 / 255.0)).sum()),
        "opaque_pixels": int((alpha >= 254.0 / 255.0).sum()),
        "warning": "single-background removal is approximate and cannot reliably recover true translucent edges",
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
