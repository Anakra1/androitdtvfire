from pathlib import Path
import math
from PIL import Image, ImageDraw

root = Path(__file__).parent / 'skin.crimsonbloodrequiem'
source_art = Path(__file__).parent / 'plugin.video.stremio.bridge' / 'resources' / 'art'
media = root / 'media'
backgrounds = media / 'backgrounds'
media.mkdir(exist_ok=True)
backgrounds.mkdir(exist_ok=True)

Image.open(source_art / 'crb-fanart.jpg').convert('RGB').save(backgrounds / 'crb-space.jpg', quality=94)
Image.open(source_art / 'crb-icon.png').convert('RGBA').save(root / 'resources' / 'icon.png', optimize=True)
Image.open(source_art / 'crb-fanart.jpg').convert('RGB').save(root / 'resources' / 'fanart.jpg', quality=92)

PAPER = (250, 225, 230, 255)
CRIMSON = (205, 38, 62, 255)
SHADOW = (15, 4, 9, 230)

def save_icon(name, draw_icon):
    image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((15, 15, 241, 241), fill=SHADOW, outline=(118, 21, 39, 255), width=7)
    draw_icon(draw, 128)
    image.save(media / ('crb-' + name + '.png'), optimize=True)

def search(draw, c):
    draw.ellipse((c - 56, c - 62, c + 35, c + 29), outline=PAPER, width=13)
    draw.line((c + 29, c + 24, c + 87, c + 82), fill=CRIMSON, width=16)

def movie(draw, c):
    draw.ellipse((c - 77, c - 77, c + 77, c + 77), outline=PAPER, width=12)
    draw.ellipse((c - 31, c - 31, c + 31, c + 31), outline=CRIMSON, width=11)
    for angle in range(0, 360, 60):
        x = c + round(53 * math.cos(math.radians(angle)))
        y = c + round(53 * math.sin(math.radians(angle)))
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=PAPER)

def series(draw, c):
    draw.rounded_rectangle((c - 82, c - 58, c + 82, c + 48), radius=15, outline=PAPER, width=12)
    draw.line((c, c + 49, c, c + 77), fill=CRIMSON, width=12)
    draw.line((c - 41, c + 79, c + 41, c + 79), fill=PAPER, width=12)
    draw.line((c - 55, c - 36, c - 55, c + 24), fill=CRIMSON, width=8)
    draw.line((c + 55, c - 36, c + 55, c + 24), fill=CRIMSON, width=8)

def live(draw, c):
    draw.line((c, c + 72, c, c - 14), fill=PAPER, width=12)
    draw.ellipse((c - 14, c - 39, c + 14, c - 11), fill=CRIMSON)
    draw.line((c - 50, c + 78, c + 50, c + 78), fill=PAPER, width=11)
    draw.arc((c - 66, c - 107, c + 66, c + 25), 220, 320, fill=CRIMSON, width=10)
    draw.arc((c - 104, c - 145, c + 104, c + 63), 220, 320, fill=PAPER, width=9)

def wizard(draw, c):
    draw.polygon(((c, c - 88), (c + 74, c - 10), (c, c + 68), (c - 74, c - 10)), outline=PAPER)
    draw.line((c - 45, c + 78, c + 45, c + 78), fill=CRIMSON, width=11)
    draw.ellipse((c - 11, c - 100, c + 11, c - 78), fill=CRIMSON)

for n, fn in [('search', search), ('movies', movie), ('series', series), ('live', live), ('wizard', wizard)]:
    save_icon(n, fn)

print('Generated CRB skin art and menu icons.')
