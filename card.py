"""
Infographic image cards for Sunny Choby's LinkedIn posts (1080x1350, LinkedIn's 4:5 size).

Style: light, data-dense export infographic. Navy headline with an orange highlight,
numbered boxes / checklist / cost breakdown, a "Key Takeaway" box, a save prompt and a
branded footer with Sunny's photo (assets/photo.jpg or .png, if present).

    from card import make_card
    make_card({
        "template": "grid",            # grid | checklist | breakdown
        "series": "Export Mistakes Series",
        "headline": "5 Mistakes New Exporters Make",
        "highlight": "5 Mistakes",     # words drawn in orange
        "subtitle": "Learn these before your first shipment",
        "items": [{"title": "Wrong Incoterm", "text": "...", "note": "Cost overruns"}],
        "takeaway": "...",
        "cta": "Save this post",
    }, "out.png")

Old cards ({"tag", "headline", "points"}) still work and become a grid.
Original design every time: the agent takes only the idea from popular posts, never their images.
"""

import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1350
NAVY = (14, 42, 82)
NAVY_DARK = (8, 27, 56)
BLUE = (31, 104, 186)
ORANGE = (240, 136, 30)
GOLD = (247, 190, 40)
GREEN = (28, 150, 110)
RED = (190, 45, 40)
INK = (40, 48, 62)
GREY = (92, 104, 122)
BG = (238, 244, 251)
CARD = (255, 255, 255)
LINE = (205, 218, 235)
SOFT_BLUE = (222, 235, 250)
WHITE = (255, 255, 255)

NAME = "Sunny Choby"
ROLE = "Export Consultant  ·  First Export Order"
FOLLOW = "Follow for daily export tips"

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = [os.path.join(HERE, "assets", f) for f in ("photo.jpg", "photo.jpeg", "photo.png")]

_FONTS = {
    "head": [  # condensed bold for big headlines
        "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}
_cache: dict = {}


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    key = (kind, size)
    if key not in _cache:
        for path in _FONTS[kind]:
            if os.path.exists(path):
                _cache[key] = ImageFont.truetype(path, size)
                break
        else:
            raise RuntimeError("No font found for the image card (install fonts-liberation).")
    return _cache[key]


def _wrap(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in str(text).split():
        test = f"{line} {word}".strip()
        if d.textlength(test, font=font) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _clip(lines: list[str], n: int) -> list[str]:
    if len(lines) <= n:
        return lines
    return lines[: n - 1] + [lines[n - 1].rstrip(".,;:") + "…"]


# ---------------------------------------------------------------------------
# Input clean-up
# ---------------------------------------------------------------------------
def _normalise(card: dict) -> dict:
    items = card.get("items")
    if not items:  # old {"tag","headline","points"} cards
        items = [{"title": p} for p in (card.get("points") or [])]
    clean = []
    for it in items:
        if isinstance(it, str):
            it = {"title": it}
        clean.append({
            "title": str(it.get("title") or it.get("label") or "").strip(),
            "text": str(it.get("text") or "").strip(),
            "note": str(it.get("note") or "").strip(),
            "value": str(it.get("value") or "").strip(),
            "amount": it.get("amount"),
        })
    clean = [c for c in clean if c["title"]]
    template = str(card.get("template") or "grid").lower()
    if template not in ("grid", "checklist", "breakdown"):
        template = "grid"
    if template == "breakdown" and not any(_num(c["amount"]) for c in clean):
        template = "grid"
    limit = {"grid": 6, "checklist": 12, "breakdown": 8}[template]
    return {
        "template": template,
        "series": str(card.get("series") or card.get("tag") or "Export Basics Series").strip(),
        "headline": str(card.get("headline") or "").strip(),
        "highlight": str(card.get("highlight") or "").strip(),
        "subtitle": str(card.get("subtitle") or "").strip(),
        "items": clean[:limit],
        "total": str(card.get("total") or "").strip(),
        "takeaway": str(card.get("takeaway") or "").strip(),
        "cta": str(card.get("cta") or "Save this post for later").strip(),
    }


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------
def _background(img: Image.Image) -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(img)
    for y in range(H):  # light blue-white gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG[i] + (250 - BG[i]) * t * 0.6) for i in range(3)))
    for gx in range(30, W, 36):  # faint dotted "world trade" grid, upper right
        for gy in range(30, 420, 36):
            if (gx - W) ** 2 + (gy + 40) ** 2 < 560 ** 2:
                d.ellipse([gx - 2, gy - 2, gx + 2, gy + 2], fill=(212, 225, 242))
    d.rectangle([0, 0, W, 12], fill=NAVY)
    d.rectangle([0, 12, W, 18], fill=ORANGE)
    return d


def _headline(d, text: str, highlight: str, x: int, y: int, width: int, draw: bool) -> int:
    """Headline in navy, the highlight words in orange. Auto-fits up to 3 lines."""
    hl = {w.lower().strip(".,?!:") for w in highlight.split()}
    for size in (86, 78, 70, 64, 58, 52):
        f = _font("head", size)
        lines = _wrap(d, text.upper(), f, width)
        if len(lines) <= 3:
            break
    lines = _clip(lines, 3)
    lh = int(f.size * 1.08)
    if draw:
        for i, line in enumerate(lines):
            cx = x
            for word in line.split():
                colour = ORANGE if word.lower().strip(".,?!:") in hl else NAVY
                d.text((cx, y + i * lh), word, font=f, fill=colour)
                cx += d.textlength(word + " ", font=f)
    return y + lh * len(lines)


def _pill(d, text: str, x: int, y: int, fill, colour, size: int = 26) -> int:
    f = _font("bold", size)
    w = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + w + 44, y + size + 24], radius=(size + 24) // 2, fill=fill)
    d.text((x + 22, y + (size + 24) // 2), text, font=f, fill=colour, anchor="lm")
    return int(x + w + 44)


def _number_badge(d, n: int, x: int, y: int, r: int) -> None:
    d.ellipse([x, y, x + 2 * r, y + 2 * r], fill=GOLD)
    d.text((x + r, y + r), f"{n:02d}", font=_font("head", int(r * 0.95)), fill=NAVY, anchor="mm")


def _check_badge(d, x: int, y: int, r: int) -> None:
    d.ellipse([x, y, x + 2 * r, y + 2 * r], fill=GREEN)
    k = r / 20
    d.line([(x + 10 * k, y + 21 * k), (x + 17 * k, y + 28 * k), (x + 30 * k, y + 13 * k)],
           fill=WHITE, width=max(3, int(4 * k)))


# ---------------------------------------------------------------------------
# Body templates. Each returns the height used; draw=False only measures.
# ---------------------------------------------------------------------------
def _grid(d, items, x, y, width, s, draw) -> int:
    cols = 1 if len(items) <= 3 else 2
    gap = 22
    cw = (width - gap * (cols - 1)) // cols
    r = int(34 * s)
    tf, bf, nf = _font("bold", int(36 * s)), _font("regular", int(27 * s)), _font("bold", int(24 * s))
    inner = cw - 2 * r - 50
    rows = [items[i : i + cols] for i in range(0, len(items), cols)]
    top = y
    for row in rows:
        blocks = []
        for it in row:
            t = _clip(_wrap(d, it["title"], tf, inner), 2)
            b = _clip(_wrap(d, it["text"], bf, inner), 4) if it["text"] else []
            n = _clip(_wrap(d, "→ " + it["note"], nf, inner), 2) if it["note"] else []
            h = len(t) * tf.size * 1.15 + len(b) * bf.size * 1.3 + len(n) * nf.size * 1.3 + 44
            blocks.append((it, t, b, n, max(h, 2 * r + 40)))
        rh = int(max(bl[4] for bl in blocks))
        if draw:
            for c, (it, t, b, n, _) in enumerate(blocks):
                bx = x + c * (cw + gap) if len(row) == cols else x + (width - cw) // 2
                d.rounded_rectangle([bx, y, bx + cw, y + rh], radius=18, fill=CARD, outline=LINE, width=2)
                _number_badge(d, items.index(it) + 1, bx + 18, y + 20, r)
                tx, ty = bx + 2 * r + 34, y + 20
                for line in t:
                    d.text((tx, ty), line, font=tf, fill=NAVY)
                    ty += int(tf.size * 1.15)
                ty += 4
                for line in b:
                    d.text((tx, ty), line, font=bf, fill=INK)
                    ty += int(bf.size * 1.3)
                for line in n:
                    d.text((tx, ty), line, font=nf, fill=RED)
                    ty += int(nf.size * 1.3)
        y += rh + gap
    return y - gap - top


def _checklist(d, items, x, y, width, s, draw) -> int:
    cols = 2 if len(items) > 5 else 1
    gap = 20
    cw = (width - 60 - gap * (cols - 1)) // cols
    r = int(22 * s)
    tf, bf = _font("bold", int(30 * s)), _font("regular", int(24 * s))
    inner = cw - 2 * r - 20
    rows = [items[i : i + cols] for i in range(0, len(items), cols)]
    blocks = []
    for row in rows:
        cells = []
        for it in row:
            t = _clip(_wrap(d, it["title"], tf, inner), 2)
            b = _clip(_wrap(d, it["text"], bf, inner), 2) if it["text"] else []
            cells.append((t, b, len(t) * tf.size * 1.15 + len(b) * bf.size * 1.3))
        blocks.append((cells, int(max(c[2] for c in cells)) + 26))
    total = sum(b[1] for b in blocks) + 50
    if draw:
        d.rounded_rectangle([x, y, x + width, y + total], radius=22, fill=CARD, outline=LINE, width=2)
        cy = y + 30
        for cells, rh in blocks:
            for c, (t, b, _) in enumerate(cells):
                cx = x + 30 + c * (cw + gap)
                _check_badge(d, cx, cy, r)
                tx, ty = cx + 2 * r + 18, cy
                for line in t:
                    d.text((tx, ty), line, font=tf, fill=NAVY)
                    ty += int(tf.size * 1.15)
                for line in b:
                    d.text((tx, ty), line, font=bf, fill=GREY)
                    ty += int(bf.size * 1.3)
            cy += rh
    return total


def _breakdown(d, items, total_text, x, y, width, s, draw) -> int:
    lf, vf, nf = _font("bold", int(30 * s)), _font("bold", int(28 * s)), _font("regular", int(22 * s))
    label_w = int(width * 0.36)
    bar_x = x + 30 + label_w + 16
    bar_max = x + width - 30 - bar_x - 170
    top_amount = max(_num(it["amount"]) for it in items) or 1
    rh = int(68 * s) + (int(nf.size * 1.2) if any(it["text"] for it in items) else 0)
    total = 40 + len(items) * rh + (int(90 * s) if total_text else 0)
    if draw:
        d.rounded_rectangle([x, y, x + width, y + total], radius=22, fill=CARD, outline=LINE, width=2)
        cy = y + 24
        for i, it in enumerate(items):
            amt = _num(it["amount"])
            d.text((x + 30, cy + 4), _clip(_wrap(d, it["title"], lf, label_w), 1)[0], font=lf, fill=NAVY)
            if it["text"]:
                d.text((x + 30, cy + lf.size + 10), _clip(_wrap(d, it["text"], nf, label_w), 1)[0], font=nf, fill=GREY)
            bw = max(14, int(bar_max * amt / top_amount))
            colour = BLUE if i == 0 else ORANGE
            d.rounded_rectangle([bar_x, cy + 4, bar_x + bw, cy + 4 + int(42 * s)], radius=8, fill=colour)
            d.text((bar_x + bw + 14, cy + 4 + int(21 * s)), it["value"] or f"{amt:g}", font=vf, fill=INK, anchor="lm")
            cy += rh
        if total_text:
            d.line([(x + 30, cy + 6), (x + width - 30, cy + 6)], fill=LINE, width=2)
            d.text((x + 30, cy + 22), total_text.upper(), font=_font("head", int(52 * s)), fill=NAVY)
    return total


def _footer_boxes(d, takeaway: str, cta: str, x: int, y: int, width: int, draw: bool) -> int:
    cta_w = 300
    tw = width - cta_w - 20 if cta else width
    hf, bf = _font("bold", 30), _font("regular", 26)
    lines = _clip(_wrap(d, takeaway, bf, tw - 60), 3) if takeaway else []
    h = max(130, 70 + len(lines) * 34 + 20) if takeaway else 130
    if draw:
        if takeaway:
            d.rounded_rectangle([x, y, x + tw, y + h], radius=18, fill=SOFT_BLUE, outline=(178, 205, 236), width=2)
            d.text((x + 30, y + 20), "KEY TAKEAWAY", font=hf, fill=BLUE)
            for i, line in enumerate(lines):
                d.text((x + 30, y + 66 + i * 34), line, font=bf, fill=INK)
        if cta:
            cx = x + width - cta_w if takeaway else x
            cw = cta_w if takeaway else width
            d.rounded_rectangle([cx, y, cx + cw, y + h], radius=18, fill=ORANGE)
            cf = _font("bold", 32)
            cl = _clip(_wrap(d, cta, cf, cw - 70), 3)
            cl[-1] += " →"
            ly = y + h // 2 - len(cl) * 20
            for i, line in enumerate(cl):
                d.text((cx + cw // 2, ly + i * 40 + 20), line, font=cf, fill=WHITE, anchor="mm")
    return h


def _brand_bar(img: Image.Image, d) -> None:
    top = H - 150
    d.rectangle([0, top, W, H], fill=NAVY_DARK)
    d.rectangle([0, top, W, top + 6], fill=ORANGE)
    x, size = 60, 104
    photo = next((p for p in PHOTOS if os.path.exists(p)), None)
    py = top + 6 + (144 - size) // 2
    if photo:
        face = ImageOps.fit(Image.open(photo).convert("RGB"), (size, size), centering=(0.5, 0.35))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        d.ellipse([x - 4, py - 4, x + size + 4, py + size + 4], fill=GOLD)
        img.paste(face, (x, py), mask)
    else:
        d.ellipse([x, py, x + size, py + size], fill=GOLD)
        d.text((x + size // 2, py + size // 2), "SC", font=_font("bold", 44), fill=NAVY, anchor="mm")
    tx = x + size + 28
    d.text((tx, top + 34), NAME, font=_font("bold", 44), fill=WHITE)
    d.text((tx, top + 92), ROLE, font=_font("regular", 25), fill=(190, 206, 228))
    ff = _font("bold", 23)
    fw = d.textlength(FOLLOW, font=ff)
    d.rounded_rectangle([W - 60 - fw - 40, top + 46, W - 60, top + 104], radius=29, outline=GOLD, width=3)
    d.text((W - 60 - fw / 2 - 20, top + 75), FOLLOW, font=ff, fill=GOLD, anchor="mm")


# ---------------------------------------------------------------------------
def make_card(card: dict, path: str) -> str:
    c = _normalise(card)
    img = Image.new("RGB", (W, H), BG)
    d = _background(img)
    x, width = 60, W - 120
    bottom = H - 150 - 40  # space above the brand bar

    y = 52
    _pill(d, c["series"].upper()[:42], x, y, NAVY, WHITE)
    y += 84
    y = _headline(d, c["headline"], c["highlight"], x, y, width, True) + 10
    if c["subtitle"]:
        sf = _font("regular", 32)
        for line in _clip(_wrap(d, c["subtitle"], sf, width), 2):
            d.text((x, y), line, font=sf, fill=GREY)
            y += 42
    y += 28

    foot_h = _footer_boxes(d, c["takeaway"], c["cta"], x, 0, width, False)
    room = bottom - foot_h - 26 - y

    def body(s: float, draw: bool, at: int) -> int:
        if c["template"] == "checklist":
            return _checklist(d, c["items"], x, at, width, s, draw)
        if c["template"] == "breakdown":
            return _breakdown(d, c["items"], c["total"], x, at, width, s, draw)
        return _grid(d, c["items"], x, at, width, s, draw)

    scale = 1.2
    while scale > 0.62 and body(scale, False, y) > room:
        scale -= 0.04
    used = body(scale, False, y)
    body(scale, True, y + max(0, (room - used) // 3))
    _footer_boxes(d, c["takeaway"], c["cta"], x, bottom - foot_h, width, True)
    _brand_bar(img, d)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return path


SAMPLES = {
    "grid": {
        "template": "grid", "series": "Export Mistakes Series",
        "headline": "5 Mistakes That Cost New Exporters Their First Buyer",
        "highlight": "5 Mistakes",
        "subtitle": "Fix these before you send your first quotation",
        "items": [
            {"title": "Quoting without costing", "text": "You add freight later and your margin is gone.", "note": "Price looks cheap, profit is zero"},
            {"title": "Wrong Incoterm", "text": "CIF risk moves at loading, not at delivery.", "note": "Disputes over damage"},
            {"title": "No sample terms", "text": "Free samples to every enquiry drain cash.", "note": "Ask buyer to pay courier"},
            {"title": "Slow replies", "text": "Buyers compare 5 suppliers. Speed wins trust.", "note": "Reply within 24 hours"},
            {"title": "Weak documents", "text": "One wrong HS code holds the whole container.", "note": "Port charges every day"},
        ],
        "takeaway": "Your first order is won on clarity: clear price, clear terms, clear papers.",
        "cta": "Save this post",
    },
    "checklist": {
        "template": "checklist", "series": "Export Documents Series",
        "headline": "10 Documents Before Your Container Moves",
        "highlight": "10 Documents",
        "subtitle": "Tick these off before you call your CHA",
        "items": [{"title": t, "text": s} for t, s in [
            ("IEC", "Import Export Code from DGFT"), ("Commercial Invoice", "Price, quantity, buyer details"),
            ("Packing List", "Weights, boxes, HS code"), ("Shipping Bill", "Filed on ICEGATE"),
            ("Bill of Lading", "Issued by the shipping line"), ("Certificate of Origin", "For duty benefits"),
            ("LUT", "Export without paying IGST"), ("Insurance", "Cover for transit loss"),
            ("Purchase Order", "Buyer's written order"), ("Proforma Invoice", "Approved before production")]],
        "takeaway": "One missing paper can mean days of port charges.",
        "cta": "Screenshot this checklist",
    },
    "breakdown": {
        "template": "breakdown", "series": "Export Costing Series",
        "headline": "Your $500 Freight Quote Is Really $850",
        "highlight": "$850",
        "subtitle": "Example of where the extra charges come from",
        "items": [
            {"title": "Ocean Freight", "text": "Base rate quoted", "amount": 500, "value": "$500"},
            {"title": "BAF", "text": "Fuel surcharge", "amount": 100, "value": "$100"},
            {"title": "THC", "text": "Terminal handling", "amount": 80, "value": "$80"},
            {"title": "Customs", "text": "Clearance fees", "amount": 70, "value": "$70"},
            {"title": "CAF", "text": "Currency surcharge", "amount": 40, "value": "$40"},
            {"title": "Documentation", "text": "B/L and paperwork", "amount": 40, "value": "$40"},
            {"title": "Seal", "text": "Container seal", "amount": 20, "value": "$20"},
        ],
        "total": "Total: $850  (+70%)",
        "takeaway": "Always ask for an all-in quote that lists every charge.",
        "cta": "Save before your next quote",
    },
}

if __name__ == "__main__":
    for name, sample in SAMPLES.items():
        print(make_card(sample, f"drafts/sample_{name}.png"))
