#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any


def image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def find_generated_images(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "image_generation_call":
            result = value.get("result")
            if isinstance(result, str) and result:
                found.append(result)
        for child in value.values():
            found.extend(find_generated_images(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_generated_images(child))
    return found


def run_request(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "openai SDK is required. Run with `uv run --with openai python` or install openai."
        ) from exc

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set.")

    client = OpenAI()
    response = client.responses.create(
        model=args.response_model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": args.prompt,
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url(args.reference_image),
                        "detail": args.detail,
                    },
                ],
            }
        ],
        tools=[
            {
                "type": "image_generation",
                "action": "generate",
                "model": args.image_model,
                "size": args.size,
                "quality": args.quality,
                "background": "opaque",
                "output_format": "png",
            }
        ],
        max_tool_calls=1,
    )
    response_data = response.model_dump()
    images = find_generated_images(response_data)
    if not images:
        raise SystemExit("Responses image_generation returned no image_generation_call result.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(base64.b64decode(images[0]))
    return {
        "out": str(args.out),
        "reference_image": str(args.reference_image),
        "response_model": args.response_model,
        "image_model": args.image_model,
        "size": args.size,
        "quality": args.quality,
        "detail": args.detail,
        "response_id": response_data.get("id"),
        "image_count": len(images),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an image with a reference image via Responses image_generation."
    )
    parser.add_argument("--reference-image", required=True, type=Path)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--response-model", default=os.environ.get("ALPHAKIT_RESPONSE_MODEL", "gpt-5.4"))
    parser.add_argument("--image-model", default=os.environ.get("ALPHAKIT_IMAGE_MODEL", "gpt-image-1.5"))
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"])
    parser.add_argument("--detail", default="high", choices=["low", "high", "auto", "original"])
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.reference_image = args.reference_image.resolve()
    args.out = args.out.resolve()
    if not args.reference_image.exists():
        raise SystemExit(f"Reference image not found: {args.reference_image}")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "endpoint": "/v1/responses",
                    "tool": "image_generation",
                    "action": "generate",
                    "reference_image": str(args.reference_image),
                    "out": str(args.out),
                    "response_model": args.response_model,
                    "image_model": args.image_model,
                    "size": args.size,
                    "quality": args.quality,
                    "detail": args.detail,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    report = run_request(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
