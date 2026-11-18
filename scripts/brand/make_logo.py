"""Draw the brand logo as PNGs: the diamond mark (deep green with a mint square, as in the apps)
beside "PreparationPalAI" in Manrope ExtraBold. Used where SVG text cannot load our font, such as
the sign-in page (Logto). Deterministic: same inputs, same pixels.

    .venv/bin/python scripts/brand/make_logo.py
writes frontend/public/brand/logo.png (dark text), logo-dark.png (light text) and mark.png.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / 'mobile/node_modules/@expo-google-fonts/manrope/800ExtraBold/Manrope_800ExtraBold.ttf'
OUT = ROOT / 'frontend/public/brand'
BRAND, MINT = (25, 79, 60, 255), (201, 230, 188, 255)
SCALE = 2                                   # draw at 2x for sharp screens


def mark(size: int) -> Image.Image:
    """The diamond: a rounded square rotated 45 degrees, with a mint square inside."""
    big = size * 4                          # supersample, then shrink for smooth edges
    tile = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    inset = int(big * 0.15)
    d.rounded_rectangle((inset, inset, big - inset, big - inset), radius=int(big * 0.2), fill=BRAND)
    inner = int(big * 0.34)
    d.rounded_rectangle((inner, inner, big - inner, big - inner), radius=int(big * 0.07), fill=MINT)
    return tile.rotate(45, resample=Image.BICUBIC).resize((size, size), Image.LANCZOS)


def logo(text_colour: tuple[int, int, int, int]) -> Image.Image:
    height = 48 * SCALE
    font = ImageFont.truetype(str(FONT), int(26 * SCALE))
    label = 'PreparationPalAI'
    left, top, right, bottom = font.getbbox(label)
    m = mark(height)
    width = height + int(12 * SCALE) + (right - left) + int(4 * SCALE)
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    image.alpha_composite(m, (0, 0))
    ImageDraw.Draw(image).text((height + int(12 * SCALE) - left, (height - (bottom - top)) // 2 - top), label, font=font, fill=text_colour)
    return image


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    logo((31, 38, 43, 255)).save(OUT / 'logo.png', optimize=True)
    logo((238, 241, 244, 255)).save(OUT / 'logo-dark.png', optimize=True)
    mark(128).save(OUT / 'mark.png', optimize=True)
    for name in ('logo.png', 'logo-dark.png', 'mark.png'):
        print(name, Image.open(OUT / name).size)
