"""Draws the level card: a dark dashboard-style image with a few panels (level, XP earned, daily average,
top members and top channels). Needs Pillow; callers fall back to a plain embed when it isn't installed."""
import io
import os

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except Exception:  # pragma: no cover - depends on the host
    HAVE_PIL = False

W, H = 1300, 680
BG = (15, 15, 18)
PANEL = (23, 23, 27)
EDGE = (40, 40, 47)
CHIP = (34, 34, 40)
WHITE = (255, 255, 255)
MUTED = (139, 139, 150)
PINK = (255, 176, 236)
DIM_PINK = (110, 78, 104)

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
FALLBACKS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf", "/Library/Fonts/Arial Bold.ttf"]
_fonts = {}


def font(size, bold=True):
    key = (size, bold)
    if key not in _fonts:
        candidates = [os.path.join(FONT_DIR, "Poppins-Bold.ttf" if bold else "Poppins-Medium.ttf")] + FALLBACKS
        loaded = None
        for path in candidates:
            try:
                loaded = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
        _fonts[key] = loaded or ImageFont.load_default(size)
    return _fonts[key]


def clean(text):
    """Swap characters the font can't draw (emoji, other scripts) so the card never shows empty boxes."""
    return "".join(c if 0x20 <= ord(c) <= 0x24F or 0x2010 <= ord(c) <= 0x203A else "?" for c in str(text))


def fit(draw, text, fnt, width):
    text = clean(text)
    if draw.textlength(text, font=fnt) <= width:
        return text
    while text and draw.textlength(text + "...", font=fnt) > width:
        text = text[:-1]
    return text.rstrip() + "..."


def short(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return f"{n:,}"


def round_image(img, size, radius=None):
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius if radius is not None else size // 2, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def panel(draw, box, title, icon=None):
    draw.rounded_rectangle(box, radius=16, fill=PANEL, outline=EDGE, width=1)
    draw.text((box[0] + 16, box[1] + 12), title, font=font(18), fill=WHITE)
    if icon:
        icon(draw, box[2] - 30, box[1] + 22)


# Small drawn icons in the accent colour (so no emoji font is needed).
def icon_clock(d, x, y):
    d.ellipse((x - 9, y - 9, x + 9, y + 9), outline=PINK, width=2)
    d.line((x, y, x, y - 5), fill=PINK, width=2)
    d.line((x, y, x + 4, y + 2), fill=PINK, width=2)


def icon_bars(d, x, y):
    for i, h in enumerate((6, 11, 16)):
        d.rectangle((x - 9 + i * 7, y + 8 - h, x - 5 + i * 7, y + 8), fill=PINK)


def icon_trend(d, x, y):
    d.line((x - 9, y + 8, x + 8, y - 8), fill=PINK, width=2)
    d.polygon([(x + 9, y - 9), (x + 1, y - 8), (x + 8, y - 1)], fill=PINK)


def icon_hash(d, x, y):
    for dx in (-3, 4):
        d.line((x + dx + 2, y - 9, x + dx - 2, y + 9), fill=PINK, width=2)
    for dy in (-3, 4):
        d.line((x - 9, y + dy, x + 9, y + dy), fill=PINK, width=2)


def icon_chat(d, x, y):
    d.rounded_rectangle((x - 10, y - 8, x + 10, y + 5), radius=4, outline=PINK, width=2)
    d.polygon([(x - 4, y + 5), (x - 4, y + 11), (x + 2, y + 5)], fill=PINK)


def stat_rows(draw, box, rows, unit):
    top = box[1] + 52
    step = (box[3] - top - 6) / 3
    for i, (label, value) in enumerate(rows):
        cy = int(top + step * i + step / 2)
        chip_w = int(draw.textlength(label, font=font(15))) + 20
        draw.rounded_rectangle((box[0] + 16, cy - 14, box[0] + 16 + chip_w, cy + 14), radius=8, fill=CHIP)
        draw.text((box[0] + 26, cy), label, font=font(15), fill=WHITE, anchor="lm")
        x = box[0] + 90
        text = short(value)
        draw.text((x, cy), text, font=font(28), fill=PINK, anchor="lm")
        draw.text((x + draw.textlength(text, font=font(28)) + 10, cy + 3), unit, font=font(14), fill=MUTED, anchor="lm")


def render(data, member_avatar=None, guild_icon=None):
    """data: name, guild_name, level, xp, goal, start, rank, xp_days (1d, 7d, 30d), avg_days (1d, 7d, 30d),
    top_members [(name, level, xp, is_me)], top_channels [(name, messages)]. Returns PNG bytes."""
    image = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(image)

    # header
    if guild_icon:
        image.paste(round_image(guild_icon, 48, 10), (24, 12), round_image(guild_icon, 48, 10))
    else:
        d.rounded_rectangle((24, 12, 72, 60), radius=10, fill=CHIP)
        d.text((48, 36), clean(data["guild_name"])[:1].upper() or "?", font=font(24), fill=PINK, anchor="mm")
    d.text((86, 8), "Level", font=font(32), fill=WHITE)
    d.text((86, 46), fit(d, data["name"], font(19), 700), font=font(19), fill=MUTED)
    if member_avatar:
        av = round_image(member_avatar, 40)
        image.paste(av, (1236, 16), av)

    # row one
    b1, b2, b3 = (24, 96, 334, 336), (358, 96, 748, 336), (772, 96, 1276, 336)
    panel(d, b1, "Your Level", icon_clock)
    if member_avatar:
        av = round_image(member_avatar, 72, 14)
        image.paste(av, (143, 138), av)
    d.text((179, 240), f"Level {data['level']}", font=font(36), fill=WHITE, anchor="mm")
    d.text((179, 270), f"{data['xp']:,} / {data['goal']:,} XP", font=font(15), fill=MUTED, anchor="mm")
    span = max(1, data["goal"] - data["start"])
    fill = max(0.0, min(1.0, (data["xp"] - data["start"]) / span))
    d.rounded_rectangle((52, 296, 306, 306), radius=5, fill=CHIP)
    if fill > 0:
        d.rounded_rectangle((52, 296, 52 + max(10, int(254 * fill)), 306), radius=5, fill=PINK)
    d.text((179, 322), f"Rank #{data['rank']}" if data["rank"] else "Unranked", font=font(14), fill=MUTED, anchor="mm")

    panel(d, b2, "XP Earned", icon_bars)
    stat_rows(d, b2, list(zip(("1d", "7d", "30d"), data["xp_days"])), "xp earned")
    panel(d, b3, "Daily Average", icon_trend)
    stat_rows(d, b3, list(zip(("1d", "7d", "30d"), data["avg_days"])), "xp / day")

    # row two
    b4, b5 = (24, 360, 638, 620), (662, 360, 1276, 620)
    panel(d, b4, "Top Members", icon_hash)
    members = data["top_members"][:5]
    if members:
        for i, (name, level, xp, me) in enumerate(members):
            y = 410 + i * 40
            if me:
                d.rounded_rectangle((34, y - 4, 628, y + 30), radius=9, fill=CHIP)
            d.text((50, y + 13), f"{i + 1}", font=font(16), fill=PINK, anchor="lm")
            d.text((84, y + 13), fit(d, name, font(16), 300), font=font(16), fill=WHITE, anchor="lm")
            d.text((614, y + 13), f"Lvl {level}  -  {short(xp)} XP", font=font(14), fill=MUTED, anchor="rm")
    else:
        d.text(((b4[0] + b4[2]) // 2, 500), "No data yet", font=font(18), fill=MUTED, anchor="mm")

    panel(d, b5, "Top Channels", icon_chat)
    channels = data["top_channels"][:5]
    if channels:
        most = max(c for _, c in channels) or 1
        for i, (name, count) in enumerate(channels):
            y = 410 + i * 40
            d.text((678, y + 8), fit(d, "#" + name, font(16), 330), font=font(16), fill=WHITE, anchor="lm")
            d.text((1262, y + 8), f"{short(count)} msgs", font=font(14), fill=MUTED, anchor="rm")
            d.rounded_rectangle((678, y + 20, 1262, y + 25), radius=3, fill=CHIP)
            d.rounded_rectangle((678, y + 20, 678 + max(6, int(584 * count / most)), y + 25), radius=3, fill=PINK if i == 0 else DIM_PINK)
    else:
        d.text(((b5[0] + b5[2]) // 2, 500), "No data yet", font=font(18), fill=MUTED, anchor="mm")

    # footer
    d.text((24, 662), "XP and messages: last 30 days  -  Timezone: UTC", font=font(14), fill=MUTED, anchor="lm")
    d.text((1276, 662), "Powered by Risk", font=font(14), fill=MUTED, anchor="rm")

    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def render_board(title, subtitle, rows, footer, guild_icon=None, guild_name=""):
    """Leaderboard picture. rows: [(rank, name, avatar_image_or_None, value_text, small_text, is_me)]. Returns PNG bytes."""
    width, top, step = 1000, 96, 96
    height = top + max(1, len(rows)) * step + 70
    image = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(image)
    if guild_icon:
        icon = round_image(guild_icon, 48, 10)
        image.paste(icon, (24, 12), icon)
    else:
        d.rounded_rectangle((24, 12, 72, 60), radius=10, fill=CHIP)
        d.text((48, 36), clean(guild_name)[:1].upper() or "?", font=font(24), fill=PINK, anchor="mm")
    d.text((86, 8), clean(title), font=font(32), fill=WHITE)
    d.text((86, 46), fit(d, subtitle, font(19), 800), font=font(19), fill=MUTED)
    d.rounded_rectangle((24, top - 8, width - 24, top + max(1, len(rows)) * step), radius=16, fill=PANEL, outline=EDGE, width=1)
    if not rows:
        d.text((width // 2, top + 30), "No data yet", font=font(18), fill=MUTED, anchor="mm")
    for i, (rank, name, avatar, value, lines, me) in enumerate(rows):
        y = top + i * step
        if isinstance(lines, str):
            lines = [lines] if lines else []
        if me:
            d.rounded_rectangle((34, y - 2, width - 34, y + step - 4), radius=10, fill=CHIP)
        mid = y + (step - 12) // 2
        d.text((72, mid), f"#{rank}", font=font(24 if rank <= 3 else 19), fill=PINK if rank <= 3 else MUTED, anchor="mm")
        if avatar:
            av = round_image(avatar, 56)
            image.paste(av, (116, mid - 28), av)
        else:
            d.ellipse((116, mid - 28, 172, mid + 28), fill=EDGE)
        d.text((192, y + 6), fit(d, name, font(20), 520), font=font(20), fill=WHITE)
        for n, line in enumerate(lines[:3]):
            d.text((192, y + 36 + n * 18), fit(d, line, font(13), 560), font=font(13), fill=MUTED)
        d.text((width - 52, mid), clean(value), font=font(24), fill=PINK if rank <= 3 else WHITE, anchor="rm")
    d.text((24, height - 24), clean(footer), font=font(14), fill=MUTED, anchor="lm")
    d.text((width - 24, height - 24), "Powered by Risk", font=font(14), fill=MUTED, anchor="rm")
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def open_image(data):
    if not data or not HAVE_PIL:
        return None
    try:
        return Image.open(io.BytesIO(data))
    except Exception:
        return None
