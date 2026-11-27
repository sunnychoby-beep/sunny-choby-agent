"""
Branded image card for Sunny Choby's LinkedIn posts (1080x1350, LinkedIn's 4:5 size).

    from card import make_card
    make_card({"tag": "EXPORT MISTAKE", "headline": "...", "points": ["...", "..."]}, "out.png")

Original design every time: the agent takes only the idea from popular posts, never their images.
"""

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
NAVY = (11, 37, 69)
NAVY_2 = (19, 64, 116)
GOLD = (242, 165, 65)
WHITE = (255, 255, 255)
SOFT = (196, 212, 232)

NAME = "Sunny Choby"
ROLE = "Export Consultant  |  Your First Export Order"
PROGRAM = "6-Month Hand-Hold  ·  Only Live Workshops"

_FONTS = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
}


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in _FONTS[kind]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError("No font found for the image card (install fonts-dejavu-core).")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit(draw, text, kind, width, max_lines, sizes):
    """Largest font size from `sizes` that fits `text` in `max_lines` lines."""
    for size in sizes:
        f = _font(kind, size)
        lines = _wrap(draw, text, f, width)
        if len(lines) <= max_lines:
            return f, lines
    f = _font(kind, sizes[-1])
    return f, _wrap(draw, text, f, width)[:max_lines]


def make_card(card: dict, path: str) -> str:
    tag = (card.get("tag") or "EXPORT TIP").upper()[:28]
    headline = (card.get("headline") or "").strip()
    points = [p.strip() for p in (card.get("points") or []) if p.strip()][:4]

    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # Background: soft vertical gradient + faint globe lines (export = world trade).
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(NAVY[i] + (NAVY_2[i] - NAVY[i]) * t) for i in range(3)))
    cx, cy, r = W + 60, 260, 420
    for k in range(6):
        rr = r - k * 70
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(36, 82, 135), width=2)
    for k in range(-3, 4):
        d.arc([cx - r + abs(k) * 120, cy - r, cx + r - abs(k) * 120, cy + r], 90, 270,
              fill=(36, 82, 135), width=2)

    x, maxw = 90, W - 180

    def body(y0: int, draw: bool) -> int:
        """Tag, headline, divider and points from y0. Returns the y where it ends."""
        y = y0
        tf = _font("bold", 30)
        tw = d.textlength(tag, font=tf)
        if draw:
            d.rounded_rectangle([x, y, x + tw + 48, y + 60], radius=30, fill=GOLD)
            d.text((x + 24, y + 30), tag, font=tf, fill=NAVY, anchor="lm")
        y += 115
        hf, hlines = _fit(d, headline, "bold", maxw, 5, [84, 76, 68, 60, 54])
        for line in hlines:
            if draw:
                d.text((x, y), line, font=hf, fill=WHITE)
            y += int(hf.size * 1.18)
        y += 30
        if draw:
            d.rectangle([x, y, x + 120, y + 8], fill=GOLD)
        y += 60
        pf = _font("regular", 42)
        for p in points:
            plines = _wrap(d, p, pf, maxw - 70)[:3]
            need = len(plines) * 54 + 30
            if y + need > H - 260:
                break
            if draw:
                d.ellipse([x, y + 4, x + 40, y + 44], fill=GOLD)
                d.line([(x + 10, y + 25), (x + 18, y + 33), (x + 31, y + 16)], fill=NAVY, width=5)
                for i, pl in enumerate(plines):
                    d.text((x + 70, y + i * 54), pl, font=pf, fill=WHITE)
            y += need
        return y

    # Centre the content between the top edge and the brand bar.
    height = body(0, False)
    body(max(90, (H - 220 - height) // 2), True)

    # Bottom brand bar
    d.rectangle([0, H - 220, W, H], fill=(7, 26, 50))
    d.rectangle([0, H - 220, W, H - 212], fill=GOLD)
    d.ellipse([x, H - 175, x + 110, H - 65], fill=GOLD)
    d.text((x + 55, H - 120), "SC", font=_font("bold", 46), fill=NAVY, anchor="mm")
    d.text((x + 140, H - 165), NAME, font=_font("bold", 48), fill=WHITE)
    d.text((x + 140, H - 105), ROLE, font=_font("regular", 28), fill=SOFT)
    d.text((x + 140, H - 65), PROGRAM, font=_font("regular", 26), fill=GOLD)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return path


if __name__ == "__main__":
    make_card({
        "tag": "First export order",
        "headline": "Why most new exporters never get their first order",
        "points": ["They chase buyers before fixing their product price",
                   "They skip the paperwork until a buyer asks",
                   "They try to learn everything alone from videos"],
    }, "drafts/sample_card.png")
    print("drafts/sample_card.png")
