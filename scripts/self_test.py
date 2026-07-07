#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import importlib.util

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


def load_generate_demo_pairs_module():
    spec = importlib.util.spec_from_file_location(
        "generate_demo_pairs", SCRIPT_DIR / "generate_demo_pairs.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load generate_demo_pairs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    rgb, alpha = make_source()
    with tempfile.TemporaryDirectory(prefix="transparent-alpha-test-") as tmp:
        tmp_path = Path(tmp)
        truth = tmp_path / "truth.png"
        black = tmp_path / "black.png"
        white = tmp_path / "white.png"
        green = tmp_path / "green.png"
        white_negative_bad = tmp_path / "white-negative-bad.png"
        white_shifted = tmp_path / "white-shifted.png"
        paired_out = tmp_path / "paired.png"
        paired_webp = tmp_path / "paired.webp"
        standard_jpeg = tmp_path / "standard.jpg"
        standard_webp = tmp_path / "standard.webp"
        save_rgba(truth, rgb, alpha)
        save_rgb(black, rgb * alpha[..., None])
        save_rgb(white, rgb * alpha[..., None] + (1.0 - alpha[..., None]))
        green_bg = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        save_rgb(green, rgb * alpha[..., None] + (1.0 - alpha[..., None]) * green_bg)
        white_bad_rgb = rgb * alpha[..., None] + (1.0 - alpha[..., None])
        white_bad_rgb[104:152, 104:152] = 0.0
        save_rgb(white_negative_bad, white_bad_rgb)
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

        strict_negative_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "alpha_from_black_white.py"),
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--out",
                str(tmp_path / "strict-negative.png"),
            ]
        )
        print("strict_negative_pair_exit_code", strict_negative_result.returncode)
        if strict_negative_result.returncode == 0:
            print("ERROR expected strict negative-diff pair to fail", file=sys.stderr)
            return 1

        soft_negative_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "alpha_from_black_white.py"),
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--out",
                str(tmp_path / "soft-negative.png"),
                "--quality-profile",
                "soft-photoreal",
            ]
        )
        print("soft_negative_pair_exit_code", soft_negative_result.returncode)
        if soft_negative_result.returncode != 0:
            print(soft_negative_result.stdout)
            print(soft_negative_result.stderr, file=sys.stderr)
            return soft_negative_result.returncode

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

        jpeg_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "export_image.py"),
                "--input",
                str(paired_out),
                "--format",
                "jpeg",
                "--out",
                str(standard_jpeg),
                "--background",
                "#ffffff",
            ]
        )
        print("standard_jpeg_export_exit_code", jpeg_result.returncode)
        if jpeg_result.returncode != 0 or not standard_jpeg.exists():
            print(jpeg_result.stdout)
            print(jpeg_result.stderr, file=sys.stderr)
            return jpeg_result.returncode or 1

        webp_standard_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "export_image.py"),
                "--input",
                str(paired_out),
                "--format",
                "webp",
                "--out",
                str(standard_webp),
                "--quality",
                "90",
            ]
        )
        print("standard_webp_export_exit_code", webp_standard_result.returncode)
        if webp_standard_result.returncode != 0 or not standard_webp.exists():
            print(webp_standard_result.stdout)
            print(webp_standard_result.stderr, file=sys.stderr)
            return webp_standard_result.returncode or 1

        demo_dry_run_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "generate_demo_pairs.py"),
                "--dry-run",
                "--only",
                "photorealistic-product-cutouts",
                "--run-dir",
                str(tmp_path / "demo-run"),
                "--examples-dir",
                str(tmp_path / "examples"),
            ]
        )
        print("demo_pair_generator_dry_run_exit_code", demo_dry_run_result.returncode)
        if demo_dry_run_result.returncode != 0:
            print(demo_dry_run_result.stdout)
            print(demo_dry_run_result.stderr, file=sys.stderr)
            return demo_dry_run_result.returncode
        if "photorealistic-product-cutouts" not in demo_dry_run_result.stdout:
            print("ERROR demo dry-run did not include expected demo id", file=sys.stderr)
            return 1
        if "actual black image dimensions after generation" not in demo_dry_run_result.stdout:
            print("ERROR demo dry-run did not declare actual-size reference generation", file=sys.stderr)
            return 1

        demo_pairs = load_generate_demo_pairs_module()
        actual_size_image = tmp_path / "actual-size.png"
        Image.new("RGB", (333, 222), (0, 0, 0)).save(actual_size_image)
        actual_size = demo_pairs.image_size_label(actual_size_image)
        print("actual_size_reader", actual_size)
        if actual_size != "333x222":
            print(f"ERROR expected actual size 333x222, got {actual_size}", file=sys.stderr)
            return 1

        add_pair_dry_run_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "add_demo_pair.py"),
                "--demo-id",
                "synthetic-test",
                "--black",
                str(black),
                "--white",
                str(white),
                "--examples-dir",
                str(tmp_path / "examples"),
                "--force",
            ]
        )
        print("add_demo_pair_exit_code", add_pair_dry_run_result.returncode)
        if add_pair_dry_run_result.returncode != 0:
            print(add_pair_dry_run_result.stdout)
            print(add_pair_dry_run_result.stderr, file=sys.stderr)
            return add_pair_dry_run_result.returncode

        add_pair_green_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "add_demo_pair.py"),
                "--demo-id",
                "synthetic-green-fallback-test",
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--green",
                str(green),
                "--examples-dir",
                str(tmp_path / "examples-green"),
                "--force",
            ]
        )
        print("add_demo_pair_green_fallback_exit_code", add_pair_green_result.returncode)
        if add_pair_green_result.returncode != 0:
            print(add_pair_green_result.stdout)
            print(add_pair_green_result.stderr, file=sys.stderr)
            return add_pair_green_result.returncode
        if "black-green" not in add_pair_green_result.stdout and "green-white" not in add_pair_green_result.stdout:
            print("ERROR green fallback did not evaluate green candidates", file=sys.stderr)
            return 1

        add_pair_soft_needs_qa_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "add_demo_pair.py"),
                "--demo-id",
                "synthetic-soft-needs-qa-test",
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--quality-profile",
                "soft-photoreal",
                "--examples-dir",
                str(tmp_path / "examples-soft-needs-qa"),
                "--force",
            ]
        )
        print("add_demo_pair_soft_needs_qa_exit_code", add_pair_soft_needs_qa_result.returncode)
        if add_pair_soft_needs_qa_result.returncode != 3:
            print(add_pair_soft_needs_qa_result.stdout)
            print(add_pair_soft_needs_qa_result.stderr, file=sys.stderr)
            return add_pair_soft_needs_qa_result.returncode or 1
        if "requires-visual-qa" not in add_pair_soft_needs_qa_result.stdout:
            print("ERROR soft profile did not require visual QA", file=sys.stderr)
            return 1

        add_pair_soft_pass_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "add_demo_pair.py"),
                "--demo-id",
                "synthetic-soft-pass-test",
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--quality-profile",
                "soft-photoreal",
                "--visual-qa-pass",
                "--visual-qa-note",
                "Synthetic visual QA gate test.",
                "--examples-dir",
                str(tmp_path / "examples-soft-pass"),
                "--force",
            ]
        )
        print("add_demo_pair_soft_pass_exit_code", add_pair_soft_pass_result.returncode)
        if add_pair_soft_pass_result.returncode != 0:
            print(add_pair_soft_pass_result.stdout)
            print(add_pair_soft_pass_result.stderr, file=sys.stderr)
            return add_pair_soft_pass_result.returncode
        if "passed-relaxed-visual-qa" not in add_pair_soft_pass_result.stdout:
            print("ERROR soft profile pass was not marked as visual-QA approved", file=sys.stderr)
            return 1

        add_pair_game_sprite_needs_qa_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "add_demo_pair.py"),
                "--demo-id",
                "synthetic-game-sprite-needs-qa-test",
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--quality-profile",
                "game-sprite",
                "--examples-dir",
                str(tmp_path / "examples-game-sprite-needs-qa"),
                "--force",
            ]
        )
        print("add_demo_pair_game_sprite_needs_qa_exit_code", add_pair_game_sprite_needs_qa_result.returncode)
        if add_pair_game_sprite_needs_qa_result.returncode != 3:
            print(add_pair_game_sprite_needs_qa_result.stdout)
            print(add_pair_game_sprite_needs_qa_result.stderr, file=sys.stderr)
            return add_pair_game_sprite_needs_qa_result.returncode or 1
        if "requires-visual-qa" not in add_pair_game_sprite_needs_qa_result.stdout:
            print("ERROR game-sprite profile did not require visual QA", file=sys.stderr)
            return 1

        add_pair_game_sprite_pass_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "add_demo_pair.py"),
                "--demo-id",
                "synthetic-game-sprite-pass-test",
                "--black",
                str(black),
                "--white",
                str(white_negative_bad),
                "--quality-profile",
                "game-sprite",
                "--visual-qa-pass",
                "--visual-qa-note",
                "Synthetic game-sprite visual QA gate test.",
                "--examples-dir",
                str(tmp_path / "examples-game-sprite-pass"),
                "--force",
            ]
        )
        print("add_demo_pair_game_sprite_pass_exit_code", add_pair_game_sprite_pass_result.returncode)
        if add_pair_game_sprite_pass_result.returncode != 0:
            print(add_pair_game_sprite_pass_result.stdout)
            print(add_pair_game_sprite_pass_result.stderr, file=sys.stderr)
            return add_pair_game_sprite_pass_result.returncode
        if "passed-relaxed-visual-qa" not in add_pair_game_sprite_pass_result.stdout:
            print("ERROR game-sprite profile pass was not marked as visual-QA approved", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
