from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).parent
ART = ROOT / 'plugin.video.stremio.bridge' / 'resources' / 'art'
SOURCE = ROOT / 'crb_space_source.png'
FONT = Path(r'C:\Windows\Fonts\arialbd.ttf')
FONT_REG = Path(r'C:\Windows\Fonts\arial.ttf')


def font(size, bold=False):
    path = FONT if bold else FONT_REG
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def fit_cover(image, size, anchor=(0.62, 0.5)):
    width, height = size
    scale = max(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = round((image.width - width) * anchor[0])
    top = round((image.height - height) * anchor[1])
    return image.crop((left, top, left + width, top + height))


def make_card(base, title, subtitle, symbol):
    card = fit_cover(base, (400, 600)).filter(ImageFilter.GaussianBlur(2)).convert('RGBA')
    card.alpha_composite(Image.new('RGBA', card.size, (13, 3, 8, 190)))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((19, 20, 381, 580), radius=22, outline=(118, 25, 43, 230), width=2)
    draw.text((40, 43), 'CRB', font=font(27, True), fill=(244, 222, 224, 255))
    draw.text((40, 79), 'CRIMSON BLOOD REQUIEM', font=font(12, True), fill=(221, 60, 79, 255))
    draw.line((40, 109, 360, 109), fill=(111, 26, 39, 230), width=2)
    cx, cy = 200, 268
    if symbol == 'search':
        draw.ellipse((cx - 52, cy - 55, cx + 45, cy + 42), outline=(248, 226, 226, 255), width=9)
        draw.line((cx + 37, cy + 36, cx + 100, cy + 99), fill=(218, 44, 65, 255), width=11)
    elif symbol == 'settings':
        for y, knob in ((cy - 44, cx - 35), (cy, cx + 30), (cy + 44, cx - 8)):
            draw.line((cx - 85, y, cx + 85, y), fill=(239, 222, 224, 255), width=7)
            draw.ellipse((knob - 12, y - 12, knob + 12, y + 12), fill=(218, 44, 65, 255))
    elif symbol == 'catalogues':
        for row in range(2):
            for col in range(3):
                x, y = cx - 76 + col * 55, cy - 53 + row * 64
                draw.rounded_rectangle((x, y, x + 39, y + 47), radius=5,
                                       outline=(241, 222, 224, 255), width=5)
                draw.line((x + 9, y + 34, x + 30, y + 34), fill=(218, 44, 65, 255), width=4)
    elif symbol == 'movies':
        draw.ellipse((cx - 76, cy - 76, cx + 76, cy + 76), outline=(241, 222, 224, 255), width=9)
        draw.ellipse((cx - 33, cy - 33, cx + 33, cy + 33), outline=(218, 44, 65, 255), width=8)
        for angle in range(0, 360, 60):
            import math
            x = cx + round(54 * math.cos(math.radians(angle)))
            y = cy + round(54 * math.sin(math.radians(angle)))
            draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(241, 222, 224, 255))
    elif symbol == 'series':
        draw.rounded_rectangle((cx - 94, cy - 66, cx + 94, cy + 53), radius=14,
                               outline=(241, 222, 224, 255), width=9)
        draw.line((cx, cy + 55, cx, cy + 82), fill=(218, 44, 65, 255), width=9)
        draw.line((cx - 42, cy + 84, cx + 42, cy + 84), fill=(241, 222, 224, 255), width=9)
        draw.line((cx - 60, cy - 41, cx - 60, cy + 27), fill=(218, 44, 65, 255), width=6)
        draw.line((cx + 60, cy - 41, cx + 60, cy + 27), fill=(218, 44, 65, 255), width=6)
    elif symbol == 'live':
        draw.line((cx, cy + 72, cx, cy - 25), fill=(241, 222, 224, 255), width=9)
        draw.ellipse((cx - 13, cy - 38, cx + 13, cy - 12), fill=(218, 44, 65, 255))
        draw.line((cx - 49, cy + 79, cx + 49, cy + 79), fill=(241, 222, 224, 255), width=8)
        draw.arc((cx - 59, cy - 96, cx + 59, cy + 24), 220, 320, fill=(218, 44, 65, 255), width=8)
        draw.arc((cx - 96, cy - 133, cx + 96, cy + 61), 220, 320, fill=(241, 222, 224, 255), width=8)
    else:
        draw.rounded_rectangle((cx - 78, cy - 52, cx + 78, cy + 52), radius=14,
                               outline=(241, 222, 224, 255), width=8)
        for y in range(cy - 30, cy + 31, 26):
            draw.rectangle((cx - 66, y - 7, cx - 54, y + 7), fill=(218, 44, 65, 255))
            draw.rectangle((cx + 54, y - 7, cx + 66, y + 7), fill=(218, 44, 65, 255))
        draw.polygon(((cx - 13, cy - 29), (cx + 32, cy), (cx - 13, cy + 29)), fill=(241, 222, 224, 255))
    draw.text((40, 439), title, font=font(33, True), fill=(248, 239, 240, 255))
    draw.text((40, 485), subtitle, font=font(19), fill=(210, 190, 195, 255))
    draw.line((40, 540, 124, 540), fill=(220, 43, 65, 255), width=5)
    return card.convert('RGB')


ART.mkdir(parents=True, exist_ok=True)
source = Image.open(SOURCE).convert('RGB')

# Kodi backdrop: retain the full cinematic fleet image and a clean left-side text area.
fanart = fit_cover(source, (1920, 1080), (0.5, 0.5))
fanart.save(ART / 'crb-fanart.jpg', quality=93, optimize=True)

# Readable CRB thumbnail: use the ship-and-nebula region under a dark red veil.
icon = fit_cover(source, (512, 512), (0.9, 0.5)).convert('RGBA')
icon.alpha_composite(Image.new('RGBA', icon.size, (26, 2, 9, 138)))
draw = ImageDraw.Draw(icon)
draw.rounded_rectangle((18, 18, 494, 494), radius=42, outline=(174, 33, 52, 255), width=5)
draw.line((96, 132, 416, 132), fill=(210, 41, 61, 220), width=3)
draw.text((256, 231), 'CRB', anchor='mm', font=font(142, True), fill=(252, 235, 236, 255), stroke_width=2, stroke_fill=(63, 7, 17, 255))
draw.text((256, 307), 'CRIMSON BLOOD REQUIEM', anchor='mm', font=font(23, True), fill=(239, 83, 99, 255))
draw.line((96, 356, 416, 356), fill=(210, 41, 61, 220), width=3)
icon.convert('RGB').save(ART / 'crb-icon.png', optimize=True)

base = fit_cover(source, (400, 600), (0.64, 0.5))
poster = make_card(base, 'MOVIES + SERIES', 'Channels / sports / cinema', 'film')
poster.save(ART / 'crb-poster.png', optimize=True)
make_card(base, 'SEARCH', 'Find films and channels', 'search').save(ART / 'crb-search.png', optimize=True)
make_card(base, 'MOVIES', 'Browse films and genres', 'movies').save(ART / 'crb-movies.png', optimize=True)
make_card(base, 'TV SERIES', 'Browse shows and episodes', 'series').save(ART / 'crb-series.png', optimize=True)
make_card(base, 'LIVE TV', 'Channels and live sports', 'live').save(ART / 'crb-live.png', optimize=True)
make_card(base, 'COLLECTIONS', 'Browse movies and genres', 'catalogues').save(ART / 'crb-catalogues.png', optimize=True)
make_card(base, 'SETTINGS', 'Sources and playback', 'settings').save(ART / 'crb-settings.png', optimize=True)
make_card(base, 'MY MOVIES', 'Your Kodi library', 'film').save(ART / 'crb-library.png', optimize=True)
print('Created CRB icon, fanart and matching crimson category and search cards.')
