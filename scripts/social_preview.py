"""Generate the bundled 1200x630 social card (Pillow is already a dependency)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate():
    image = Image.new('RGB', (1200, 630), '#f5f6f2')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((850, 100, 1100, 530), radius=40, fill='#194f3c')
    draw.polygon([(975, 180), (1060, 315), (975, 450), (890, 315)], fill='#c9e6bc')
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 66)
        small = ImageFont.truetype('DejaVuSans.ttf', 28)
    except OSError:
        font = ImageFont.load_default(size=66)
        small = ImageFont.load_default(size=28)
    draw.text((70, 80), 'PreparationPalAI', font=small, fill='#194f3c')
    draw.text((65, 200), 'Study deeply.\nPrepare confidently.', font=font, fill='#152b26', spacing=18)
    draw.text((70, 450), 'Exams · Interviews · Local AI', font=small, fill='#53645d')
    target = Path(__file__).resolve().parents[1] / 'frontend/public/social-preview.png'
    image.save(target)


if __name__ == '__main__':
    generate()
