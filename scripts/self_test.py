#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent


def make_source(size: int = 256) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = size * 0.52
    cy = size * 0.48
    ellipse = ((x - cx) / (size * 0.34)) ** 2 + ((y - cy) / (size * 0.22)) ** 2
    alpha = np.clip((1.15 - ellipse) / 0.22, 0.0, 1.0)

    wing = np.clip((0.95 - ((x - size * 0.48) / (size * 0.45)) ** 2 - ((y - size * 0.42) / (size * 0.12)) ** 2) / 0.18, 0.0, 1.0)
    alpha = np.maximum(alpha, wing)

    rgb = np.zeros((size, size, 3), dtype=np.float32)
    rgb[..., 0] = 0.08 + 0.82 * (x / size)
    rgb[..., 1] = 0.12 + 0.50 * (y / size)
    rgb[..., 2] = 0.18 + 0.42 * (1.0 - x / size)

    dark_stripe = (x > size * 0.45) & (x < size * 0.52) & (alpha > 0.35)
    light_stripe = (x > size * 0.63) & (x < size * 0.70) & (alpha > 0.35)
    rgb[dark_stripe] = [0.02, 0.02, 0.025]
    rgb[light_stripe] = [0.96, 0.94, 0.88]
    return rgb, alpha


def save_rgb(path: Path, rgb: np.ndarray) -> None:
    Image.fromarray(np.clip(rgb * 255 + 0.5, 0, 255).astype("uint8"), "RGB").save(path)


def save_rgba(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> None:
    rgba = np.dstack([rgb, alpha])
    Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype("uint8"), "RGBA").save(path)


def load_rgba(path: Path) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255.0
    return arr[..., :3], arr[..., 3]


def mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def main() -> int:
    rgb, alpha = make_source()
    with tempfile.TemporaryDirectory(prefix="transparent-alpha-test-") as tmp:
        tmp_path = Path(tmp)
        truth = tmp_path / "truth.png"
        black = tmp_path / "black.png"
        white = tmp_path / "white.png"
        white_shifted = tmp_path / "white-shifted.png"
        paired_out = tmp_path / "paired.png"
        paired_webp = tmp_path / "paired.webp"
        single_out = tmp_path / "single.png"

        save_rgba(truth, rgb, alpha)
        save_rgb(black, rgb * alpha[..., None])
        save_rgb(white, rgb * alpha[..., None] + (1.0 - alpha[..., None]))
        shifted = np.roll(rgb * alpha[..., None] + (1.0 - alpha[..., None]), 1, axis=1)
        save_rgb(white_shifted, shifted)

        pair_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "alpha_from_black_white.py"),
                "--black",
                str(black),
                "--white",
                str(white),
                "--out",
                str(paired_out),
            ]
        )
        if pair_result.returncode != 0:
            print(pair_result.stdout)
            print(pair_result.stderr, file=sys.stderr)
            return pair_result.returncode

        paired_rgb, paired_alpha = load_rgba(paired_out)
        foreground_mask = alpha > 0.05
        print("aligned_pair_alpha_mae", mae(alpha, paired_alpha))
        print("aligned_pair_rgb_mae", mae(rgb[foreground_mask], paired_rgb[foreground_mask]))

        single_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "remove_solid_background.py"),
                "--input",
                str(black),
                "--bg",
                "#000000",
                "--out",
                str(single_out),
            ]
        )
        if single_result.returncode != 0:
            print(single_result.stdout)
            print(single_result.stderr, file=sys.stderr)
            return single_result.returncode

        _single_rgb, single_alpha = load_rgba(single_out)
        print("single_black_bg_alpha_mae", mae(alpha, single_alpha))

        webp_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "alpha_from_black_white.py"),
                "--black",
                str(black),
                "--white",
                str(white),
                "--out",
                str(paired_webp),
            ]
        )
        if webp_result.returncode != 0:
            print(webp_result.stdout)
            print(webp_result.stderr, file=sys.stderr)
            return webp_result.returncode

        misaligned_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "alpha_from_black_white.py"),
                "--black",
                str(black),
                "--white",
                str(white_shifted),
                "--out",
                str(tmp_path / "misaligned.png"),
            ]
        )
        print("misaligned_pair_exit_code", misaligned_result.returncode)
        if misaligned_result.returncode == 0:
            print("ERROR expected misaligned pair to fail strict check", file=sys.stderr)
            return 1

        verify_result = run([sys.executable, str(SCRIPT_DIR / "verify_alpha.py"), str(paired_out)])
        print("verify_exit_code", verify_result.returncode)
        if verify_result.returncode != 0:
            print(verify_result.stdout)
            print(verify_result.stderr, file=sys.stderr)
            return verify_result.returncode

        verify_webp_result = run([sys.executable, str(SCRIPT_DIR / "verify_alpha.py"), str(paired_webp)])
        print("verify_webp_exit_code", verify_webp_result.returncode)
        if verify_webp_result.returncode != 0:
            print(verify_webp_result.stdout)
            print(verify_webp_result.stderr, file=sys.stderr)
            return verify_webp_result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
