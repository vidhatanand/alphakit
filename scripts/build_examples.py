#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow is required. Use the bundled Codex Python runtime or install Pillow "
            "for this interpreter."
        ) from exc
    return Image, ImageDraw, ImageFilter, ImageFont


Image, ImageDraw, ImageFilter, ImageFont = require_pillow()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "transparent"
PROMPTS = ROOT / "examples" / "prompts.json"
SCALE = 4


def canvas(width: int, height: int):
    return Image.new("RGBA", (width * SCALE, height * SCALE), (0, 0, 0, 0))


def finish(image):
    width = image.width // SCALE
    height = image.height // SCALE
    return image.resize((width, height), Image.Resampling.LANCZOS)


def sc_rect(box):
    return tuple(int(v * SCALE) for v in box)


def sc_points(points):
    return [(int(x * SCALE), int(y * SCALE)) for x, y in points]


def font(size: int, bold: bool = False):
    names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default(size=size * SCALE)


def soft_shadow(base, shape_layer, blur=18, alpha=95, offset=(0, 10)):
    shadow = shape_layer.getchannel("A").filter(ImageFilter.GaussianBlur(blur * SCALE))
    tint = Image.new("RGBA", base.size, (9, 17, 31, alpha))
    shifted = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shifted.paste(tint, (offset[0] * SCALE, offset[1] * SCALE), shadow)
    base.alpha_composite(shifted)


def rounded_layer(size, box, radius, fill, outline=None, width=1):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(sc_rect(box), radius=radius * SCALE, fill=fill, outline=outline, width=width * SCALE)
    return layer


def star(cx, cy, outer, inner, points=4, rotation=-math.pi / 2):
    coords = []
    for index in range(points * 2):
        radius = outer if index % 2 == 0 else inner
        angle = rotation + index * math.pi / points
        coords.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return coords


def draw_icon_sprite_sheet():
    image = canvas(512, 128)
    draw = ImageDraw.Draw(image)
    colors = [
        (21, 184, 166, 228),
        (99, 102, 241, 230),
        (244, 184, 64, 238),
        (236, 72, 153, 226),
    ]
    for idx, cx in enumerate([64, 192, 320, 448]):
        halo = rounded_layer(image.size, (cx - 42, 22, cx + 42, 106), 24, (*colors[idx][:3], 38))
        image.alpha_composite(halo)

    draw.polygon(sc_points(star(64, 64, 34, 11, 4)), fill=(21, 184, 166, 245))
    draw.ellipse(sc_rect((93, 33, 102, 42)), fill=(255, 255, 255, 180))
    draw.ellipse(sc_rect((31, 86, 39, 94)), fill=(255, 255, 255, 145))

    draw.polygon(sc_points([(192, 28), (224, 43), (217, 83), (192, 101), (167, 83), (160, 43)]), fill=(79, 70, 229, 240))
    draw.line(sc_points([(177, 62), (188, 75), (210, 51)]), fill=(255, 255, 255, 225), width=6 * SCALE, joint="curve")

    draw.polygon(sc_points([(327, 24), (292, 71), (318, 69), (306, 104), (350, 51), (324, 54)]), fill=(245, 158, 11, 245))
    draw.line(sc_points([(327, 24), (292, 71), (318, 69), (306, 104)]), fill=(255, 255, 255, 80), width=3 * SCALE)

    draw.polygon(sc_points([(426, 28), (481, 70), (455, 76), (468, 102), (453, 109), (440, 83), (421, 101)]), fill=(219, 39, 119, 242))
    draw.line(sc_points([(426, 28), (481, 70), (455, 76)]), fill=(255, 255, 255, 130), width=4 * SCALE, joint="curve")
    return finish(image)


def draw_glass_navigation_element():
    image = canvas(720, 220)
    panel = rounded_layer(image.size, (55, 58, 665, 154), 34, (255, 255, 255, 74), (255, 255, 255, 155), 2)
    soft_shadow(image, panel, blur=22, alpha=48, offset=(0, 14))
    image.alpha_composite(panel)
    draw = ImageDraw.Draw(image)
    for x, width, color in [
        (92, 88, (21, 184, 166, 220)),
        (208, 116, (15, 23, 42, 150)),
        (352, 94, (15, 23, 42, 110)),
        (476, 116, (15, 23, 42, 110)),
    ]:
        draw.rounded_rectangle(sc_rect((x, 89, x + width, 123)), radius=15 * SCALE, fill=color)
    draw.rounded_rectangle(sc_rect((594, 82, 632, 130)), radius=18 * SCALE, fill=(236, 72, 153, 210))
    draw.line(sc_points([(610, 96), (624, 106), (610, 116)]), fill=(255, 255, 255, 235), width=4 * SCALE)
    draw.line(sc_points([(94, 74), (627, 74)]), fill=(255, 255, 255, 90), width=2 * SCALE)
    return finish(image)


def draw_launch_badge():
    image = canvas(512, 512)
    badge = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    points = star(256, 256, 182, 148, 18, -math.pi / 2)
    draw.polygon(sc_points(points), fill=(15, 23, 42, 246))
    soft_shadow(image, badge, blur=20, alpha=90, offset=(0, 14))
    image.alpha_composite(badge)
    draw = ImageDraw.Draw(image)
    draw.polygon(sc_points(star(256, 256, 140, 116, 18, -math.pi / 2)), fill=(20, 184, 166, 232))
    draw.ellipse(sc_rect((159, 157, 353, 353)), fill=(255, 255, 255, 38), outline=(255, 255, 255, 115), width=3 * SCALE)
    title_font = font(82, bold=True)
    sub_font = font(28, bold=True)
    for text, y, fnt, color in [
        ("AI", 202, title_font, (15, 23, 42, 245)),
        ("LAUNCH", 294, sub_font, (15, 23, 42, 205)),
    ]:
        bbox = draw.textbbox((0, 0), text, font=fnt)
        draw.text(sc_rect(((512 - (bbox[2] - bbox[0]) / SCALE) / 2, y))[:2], text, font=fnt, fill=color)
    return finish(image)


def draw_bird_over_globe_100km():
    image = canvas(640, 640)
    globe = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(globe)
    draw.ellipse(sc_rect((160, 212, 480, 532)), fill=(16, 118, 191, 232), outline=(255, 255, 255, 110), width=4 * SCALE)
    for y in [260, 318, 376, 434, 492]:
        draw.arc(sc_rect((164, y - 128, 476, y + 128)), 0, 360, fill=(255, 255, 255, 60), width=2 * SCALE)
    for x in [224, 320, 416]:
        draw.arc(sc_rect((x - 92, 214, x + 92, 532)), 82, 278, fill=(255, 255, 255, 58), width=2 * SCALE)
    land = (55, 171, 113, 232)
    draw.polygon(sc_points([(241, 286), (291, 262), (330, 298), (309, 339), (253, 333)]), fill=land)
    draw.polygon(sc_points([(371, 362), (427, 340), (455, 393), (418, 451), (356, 425)]), fill=land)
    draw.polygon(sc_points([(214, 415), (278, 404), (300, 459), (242, 489)]), fill=land)
    soft_shadow(image, globe, blur=22, alpha=70, offset=(0, 12))
    image.alpha_composite(globe)
    draw = ImageDraw.Draw(image)
    draw.ellipse(sc_rect((294, 187, 346, 230)), fill=(15, 23, 42, 244))
    draw.polygon(sc_points([(320, 204), (114, 139), (258, 246), (310, 232)]), fill=(15, 23, 42, 238))
    draw.polygon(sc_points([(326, 204), (536, 142), (384, 246), (336, 232)]), fill=(15, 23, 42, 238))
    draw.polygon(sc_points([(344, 197), (383, 185), (352, 214)]), fill=(244, 184, 64, 246))
    draw.line(sc_points([(154, 151), (254, 214), (320, 204), (394, 214), (500, 154)]), fill=(255, 255, 255, 72), width=5 * SCALE)
    return finish(image)


def draw_hero_swoosh_divider():
    image = canvas(960, 260)
    draw = ImageDraw.Draw(image)
    bands = [
        ([(0, 177), (170, 104), (344, 134), (510, 74), (700, 118), (960, 58), (960, 139), (694, 194), (501, 159), (345, 216), (166, 185), (0, 242)], (15, 23, 42, 226)),
        ([(0, 149), (198, 83), (375, 103), (556, 42), (759, 82), (960, 35), (960, 91), (755, 144), (553, 103), (376, 169), (196, 145), (0, 212)], (20, 184, 166, 212)),
        ([(0, 197), (226, 136), (400, 153), (599, 103), (778, 128), (960, 89), (960, 128), (779, 181), (599, 151), (399, 205), (224, 184), (0, 235)], (236, 72, 153, 172)),
    ]
    for pts, color in bands:
        draw.polygon(sc_points(pts), fill=color)
    draw.line(sc_points([(55, 158), (310, 111), (512, 80), (742, 112), (908, 78)]), fill=(255, 255, 255, 104), width=5 * SCALE, joint="curve")
    return finish(image)


def draw_realistic_product_set():
    image = canvas(900, 520)
    draw = ImageDraw.Draw(image)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    for box in [(116, 407, 316, 455), (350, 430, 554, 476), (600, 410, 797, 458)]:
        sdraw.ellipse(sc_rect(box), fill=(7, 12, 24, 65))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10 * SCALE)))

    products = [
        (170, 110, 88, 300, (236, 72, 153), "serum"),
        (410, 72, 112, 350, (20, 184, 166), "mist"),
        (660, 125, 92, 282, (99, 102, 241), "cream"),
    ]
    for x, y, width, height, color, label in products:
        body = rounded_layer(image.size, (x, y, x + width, y + height), 24, (*color, 66), (255, 255, 255, 150), 2)
        image.alpha_composite(body)
        draw.rounded_rectangle(sc_rect((x + width * 0.18, y + 18, x + width * 0.42, y + height - 18)), radius=8 * SCALE, fill=(255, 255, 255, 78))
        draw.rounded_rectangle(sc_rect((x + width * 0.16, y - 34, x + width * 0.84, y + 14)), radius=12 * SCALE, fill=(16, 24, 39, 238))
        draw.rounded_rectangle(sc_rect((x + width * 0.22, y + height * 0.52, x + width * 0.78, y + height * 0.74)), radius=10 * SCALE, fill=(255, 255, 255, 210))
        draw.text(sc_rect((x + width * 0.28, y + height * 0.58))[:2], label, font=font(15, bold=True), fill=(15, 23, 42, 210))
        draw.arc(sc_rect((x + width * 0.08, y + 22, x + width * 0.92, y + height - 20)), 255, 292, fill=(255, 255, 255, 95), width=4 * SCALE)
    return finish(image)


def draw_realistic_food_set():
    image = canvas(820, 470)
    draw = ImageDraw.Draw(image)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse(sc_rect((128, 360, 410, 420)), fill=(7, 12, 24, 58))
    sdraw.ellipse(sc_rect((438, 350, 725, 424)), fill=(7, 12, 24, 60))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9 * SCALE)))

    draw.rounded_rectangle(sc_rect((185, 140, 345, 365)), radius=28 * SCALE, fill=(245, 245, 240, 246), outline=(230, 224, 214, 255), width=3 * SCALE)
    draw.ellipse(sc_rect((179, 117, 351, 175)), fill=(236, 230, 219, 255), outline=(255, 255, 255, 220), width=3 * SCALE)
    draw.ellipse(sc_rect((203, 128, 327, 163)), fill=(99, 58, 34, 240))
    draw.arc(sc_rect((322, 198, 420, 302)), -74, 82, fill=(245, 245, 240, 248), width=20 * SCALE)
    for x in [226, 260, 294]:
        draw.arc(sc_rect((x, 62, x + 46, 156)), 230, 292, fill=(255, 255, 255, 82), width=5 * SCALE)

    draw.ellipse(sc_rect((470, 178, 696, 352)), fill=(190, 121, 62, 255))
    draw.ellipse(sc_rect((494, 195, 674, 334)), fill=(219, 151, 82, 255))
    draw.arc(sc_rect((512, 205, 654, 324)), 18, 342, fill=(122, 74, 43, 170), width=13 * SCALE)
    for cx, cy in [(535, 232), (610, 222), (650, 275), (565, 306)]:
        draw.ellipse(sc_rect((cx - 8, cy - 5, cx + 8, cy + 5)), fill=(91, 52, 31, 190))
    draw.line(sc_points([(508, 185), (548, 162), (612, 163), (680, 196)]), fill=(255, 244, 214, 155), width=5 * SCALE)
    return finish(image)


def draw_web_animation_sprite_strip():
    image = canvas(1120, 180)
    draw = ImageDraw.Draw(image)
    for frame in range(8):
        left = frame * 140
        progress = frame / 7
        draw.rounded_rectangle(sc_rect((left + 20, 62, left + 120, 118)), radius=20 * SCALE, fill=(15, 23, 42, 210), outline=(255, 255, 255, 80), width=2 * SCALE)
        draw.rounded_rectangle(sc_rect((left + 33, 77, left + 107, 103)), radius=10 * SCALE, fill=(20, 184, 166, 165))
        x = left + 22 + progress * 96
        draw.line(sc_points([(x - 18, 58), (x + 14, 122)]), fill=(255, 255, 255, 205), width=6 * SCALE)
        draw.ellipse(sc_rect((left + 52 - 16 * progress, 34, left + 88 + 16 * progress, 70)), fill=(236, 72, 153, int(34 + 70 * progress)))
        draw.ellipse(sc_rect((left + 58 - 20 * progress, 112, left + 82 + 20 * progress, 136)), fill=(20, 184, 166, int(68 - 30 * progress)))
    return finish(image)


def draw_particle_burst_animation():
    image = canvas(960, 160)
    draw = ImageDraw.Draw(image)
    colors = [(20, 184, 166), (236, 72, 153), (244, 184, 64), (99, 102, 241)]
    for frame in range(8):
        cx = frame * 120 + 60
        cy = 80
        radius = 10 + frame * 7
        alpha = max(36, 230 - frame * 24)
        draw.ellipse(sc_rect((cx - radius, cy - radius, cx + radius, cy + radius)), outline=(255, 255, 255, alpha), width=3 * SCALE)
        for index in range(12):
            angle = (math.tau / 12) * index + frame * 0.16
            dist = radius + index % 3 * 6
            x = cx + math.cos(angle) * dist
            y = cy + math.sin(angle) * dist
            color = colors[index % len(colors)]
            dot = 2 + (index + frame) % 4
            draw.ellipse(sc_rect((x - dot, y - dot, x + dot, y + dot)), fill=(*color, alpha))
    return finish(image)


def draw_game_assets_sprite_sheet():
    image = canvas(640, 320)
    draw = ImageDraw.Draw(image)
    cell = 80
    palette = {
        "ink": (15, 23, 42, 255),
        "skin": (245, 180, 125, 255),
        "shirt": (20, 184, 166, 255),
        "pants": (79, 70, 229, 255),
        "gold": (245, 158, 11, 255),
        "wood": (151, 91, 48, 255),
    }
    for frame in range(4):
        ox = frame * cell
        bob = 3 if frame % 2 else 0
        draw.rectangle(sc_rect((ox + 30, 20 + bob, ox + 50, 42 + bob)), fill=palette["skin"])
        draw.rectangle(sc_rect((ox + 25, 42 + bob, ox + 55, 69 + bob)), fill=palette["shirt"])
        draw.rectangle(sc_rect((ox + 27, 69 + bob, ox + 39, 78 + bob)), fill=palette["pants"])
        draw.rectangle(sc_rect((ox + 42, 69 + bob, ox + 54, 78 + bob)), fill=palette["pants"])
        draw.rectangle(sc_rect((ox + 25, 17 + bob, ox + 55, 25 + bob)), fill=palette["ink"])
    for index, x in enumerate([330, 410, 490, 570]):
        y = 36
        draw.ellipse(sc_rect((x - 20, y - 20, x + 20, y + 20)), fill=palette["gold"])
        draw.ellipse(sc_rect((x - 10, y - 14, x + 10, y + 14)), outline=(255, 255, 255, 170), width=4 * SCALE)
    for row, y in enumerate([126, 206]):
        for col, x in enumerate([40, 120, 200, 280, 360, 440, 520]):
            if row == 0:
                draw.rectangle(sc_rect((x - 24, y - 20, x + 24, y + 20)), fill=palette["wood"])
                draw.line(sc_points([(x - 22, y - 3), (x + 22, y - 3)]), fill=(101, 59, 32, 255), width=4 * SCALE)
                draw.line(sc_points([(x - 7, y - 18), (x - 7, y + 18)]), fill=(101, 59, 32, 255), width=4 * SCALE)
            else:
                draw.polygon(sc_points(star(x, y, 23, 11, 5)), fill=(236, 72, 153, 235))
    return finish(image)


def draw_game_effects_sprite_sheet():
    image = canvas(768, 192)
    draw = ImageDraw.Draw(image)
    for frame in range(8):
        cx = frame * 96 + 48
        cy = 96
        radius = 12 + frame * 6
        alpha = max(42, 235 - frame * 22)
        draw.ellipse(sc_rect((cx - radius, cy - radius, cx + radius, cy + radius)), fill=(244, 184, 64, alpha))
        draw.ellipse(sc_rect((cx - radius * 0.65, cy - radius * 0.65, cx + radius * 0.65, cy + radius * 0.65)), fill=(236, 72, 153, max(35, alpha - 28)))
        draw.polygon(sc_points(star(cx, cy, radius * 1.2, radius * 0.45, 8, frame * 0.2)), fill=(255, 255, 255, max(25, alpha - 85)))
        smoke_alpha = max(18, 120 - frame * 10)
        draw.ellipse(sc_rect((cx - radius * 1.4, cy + radius * 0.4, cx - radius * 0.2, cy + radius * 1.3)), fill=(15, 23, 42, smoke_alpha))
        draw.ellipse(sc_rect((cx + radius * 0.15, cy + radius * 0.35, cx + radius * 1.35, cy + radius * 1.2)), fill=(15, 23, 42, smoke_alpha))
    return finish(image)


EXAMPLES = [
    {
        "id": "icon-sprite-sheet",
        "title": "Icon sprite sheet",
        "category": "icon sprites",
        "prompt": "A compact transparent PNG sprite sheet with four polished app icons: sparkle, shield, lightning bolt, and cursor pointer, crisp vector-like edges, no background.",
        "factory": draw_icon_sprite_sheet,
    },
    {
        "id": "glass-navigation-element",
        "title": "Glass navigation element",
        "category": "transparent web page design element",
        "prompt": "A transparent PNG website navigation component with frosted glass pill, subtle border, tab indicators, and no page background.",
        "factory": draw_glass_navigation_element,
    },
    {
        "id": "launch-badge",
        "title": "Launch badge",
        "category": "transparent badge",
        "prompt": "A transparent PNG launch badge for a modern AI tool, layered sticker shape, subtle shadow, clean edges, no background.",
        "factory": draw_launch_badge,
    },
    {
        "id": "bird-over-globe-100km",
        "title": "Bird over globe at 100 km",
        "category": "transparent illustration",
        "prompt": "A stylized bird flying above a globe at 100 km altitude, clean editorial illustration, isolated subject, pure transparent background.",
        "factory": draw_bird_over_globe_100km,
    },
    {
        "id": "hero-swoosh-divider",
        "title": "Hero swoosh divider",
        "category": "transparent web page design element",
        "prompt": "A transparent PNG hero-section swoosh divider with layered teal, coral, and ink ribbons, soft highlights, no background.",
        "factory": draw_hero_swoosh_divider,
    },
    {
        "id": "realistic-product-set",
        "title": "Realistic product cutout set",
        "category": "photorealistic transparent image set",
        "prompt": "A photorealistic transparent PNG product cutout set with three premium cosmetic bottles, glass reflections, soft contact shadows, isolated subject, no background.",
        "factory": draw_realistic_product_set,
    },
    {
        "id": "realistic-food-set",
        "title": "Realistic cafe cutout set",
        "category": "photorealistic transparent image set",
        "prompt": "A photorealistic transparent PNG cafe cutout set with a ceramic coffee cup, espresso surface, steam wisps, and a pastry, isolated subject, no background.",
        "factory": draw_realistic_food_set,
    },
    {
        "id": "web-animation-button-glint",
        "title": "Web animation button glint",
        "category": "transparent web animation sprite strip",
        "prompt": "A transparent PNG sprite strip for a website CTA hover animation: eight frames of a frosted button glint, glow pulse, and clean alpha edges.",
        "factory": draw_web_animation_sprite_strip,
    },
    {
        "id": "web-animation-particle-burst",
        "title": "Web animation particle burst",
        "category": "transparent web animation sprite strip",
        "prompt": "A transparent PNG sprite strip for a webpage success animation: eight frames of colorful particles expanding outward, clean alpha, no background.",
        "factory": draw_particle_burst_animation,
    },
    {
        "id": "game-platformer-assets",
        "title": "Game platformer asset sheet",
        "category": "transparent game assets",
        "prompt": "A transparent PNG game asset sprite sheet for a platformer: player idle frames, coins, crates, and collectible stars, crisp edges, no background.",
        "factory": draw_game_assets_sprite_sheet,
    },
    {
        "id": "game-effects-sprite-sheet",
        "title": "Game effects sprite sheet",
        "category": "transparent game assets",
        "prompt": "A transparent PNG game effects sprite sheet with eight explosion and magic-burst frames, smoke puffs, bright highlights, clean alpha, no background.",
        "factory": draw_game_effects_sprite_sheet,
    },
]


def save_example(example: dict[str, object]) -> dict[str, str]:
    image = example["factory"]()
    png = OUT / f"{example['id']}.png"
    webp = OUT / f"{example['id']}.webp"
    image.save(png, format="PNG")
    image.save(webp, format="WEBP", lossless=True, method=6)
    return {
        "id": str(example["id"]),
        "title": str(example["title"]),
        "category": str(example["category"]),
        "prompt": str(example["prompt"]),
        "png": str(png.relative_to(ROOT)),
        "webp": str(webp.relative_to(ROOT)),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    records = [save_example(example) for example in EXAMPLES]
    PROMPTS.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    for record in records:
        print(f"wrote {record['png']} and {record['webp']}")
    print(f"wrote {PROMPTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
