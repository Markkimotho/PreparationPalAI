"""Public marketing HTML renders without JavaScript or an Ollama connection."""
import html
import json
from urllib.parse import urlsplit

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from app.config import get_settings

router = APIRouter(include_in_schema=False)


def base_url() -> str:
    value = get_settings().public_base_url.rstrip('/')
    parsed = urlsplit(value)
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''


@router.get('/', response_class=HTMLResponse)
def landing():
    base = base_url()
    title = 'PreparationPalAI — Study deeply. Prepare confidently.'
    description = 'Prepare for science exams and technical interviews with local AI: adaptive practice, document study, mock interviews, and flashcards.'
    image = get_settings().social_image
    image = image if image.startswith('https://') else base + '/' + image.lstrip('/')
    canonical = f'<link rel="canonical" href="{html.escape(base)}/">' if base else '<meta name="robots" content="noindex, nofollow">'
    schema = json.dumps({'@context': 'https://schema.org', '@type': 'SoftwareApplication',
        'name': 'PreparationPalAI', 'applicationCategory': 'EducationalApplication',
        'operatingSystem': 'macOS, Linux, Windows', 'description': description,
        **({'url': base + '/'} if base else {})}).replace('<', '\\u003c')
    return HTMLResponse(f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{description}">{canonical}
<meta property="og:title" content="{title}"><meta property="og:description" content="{description}">
<meta property="og:type" content="website"><meta property="og:url" content="{html.escape(base)}/">
<meta property="og:image" content="{html.escape(image)}"><meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{html.escape(image)}"><link rel="icon" href="/favicon.svg">
<link rel="manifest" href="/manifest.webmanifest"><script type="application/ld+json">{schema}</script>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f6f2;color:#152b26;font:16px/1.7 system-ui,sans-serif}}
a{{color:inherit}}nav,main,footer{{max-width:1120px;margin:auto;padding:24px}}
nav{{display:flex;align-items:center;justify-content:space-between;gap:20px}}nav a{{text-decoration:none;font-weight:700}}
.hero{{padding:70px 0 50px;max-width:840px}}.tag{{font-size:12px;letter-spacing:.16em;color:#336c57;font-weight:700}}
h1{{font-size:clamp(40px,7vw,82px);line-height:1.08;letter-spacing:-.055em;margin:24px 0}}
.intro{{font-size:clamp(18px,2.3vw,23px);max-width:700px;color:#53645d}}.cta{{display:inline-block;background:#194f3c;color:white;border-radius:9px;padding:14px 23px;text-decoration:none;margin:20px 14px 12px 0;min-height:44px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:30px 0 60px}}
article{{background:white;padding:28px;border:1px solid #dce4db;border-radius:16px}}h2{{font-size:30px;line-height:1.25}}h3{{font-size:21px}}code{{overflow-wrap:anywhere}}:focus-visible{{outline:3px solid #348159;outline-offset:4px}}
footer{{border-top:1px solid #dce4db;color:#53645d}}@media(max-width:600px){{.grid{{grid-template-columns:1fr}}.hero{{padding-top:32px}}nav{{flex-wrap:wrap}}}}
</style></head><body><nav aria-label="Main"><a href="/">◆ PreparationPalAI</a><a href="/prepare">Open study workspace →</a></nav>
<main><section class="hero"><p class="tag">LOCAL AI. LASTING UNDERSTANDING.</p>
<h1>Study deeply.<br>Prepare confidently.</h1><p class="intro">From a difficult physics exam to a demanding technical interview: turn your notes, questions, and curiosity into deliberate practice.</p>
<a class="cta" href="/prepare">Start preparing →</a><a href="#setup">Set up locally</a>
<p>Powered by your local Ollama models. Choose Qwen, GLM, DeepSeek, and more.</p></section>
<h2>A study partner for the hard questions.</h2><section class="grid" aria-label="Study modes">
<article><h3>Learn & recap</h3><p>Build understanding through recall, worked reasoning, and focused practice across science, mathematics, engineering, and more.</p></article>
<article><h3>Practise under pressure</h3><p>Try mixed-format exam sessions with optional time limits. See where your understanding holds up and where to revise.</p></article>
<article><h3>Defend your reasoning</h3><p>Practise technical interviews one question at a time, with follow-ups that probe your approach and assumptions.</p></article>
<article><h3>Close the gaps</h3><p>Return to weak topics, review feedback, and create flashcards from your study material.</p></article></section>
<section><h2>Your material. Your machine.</h2><p>Upload PDFs or images, including scanned notes. Ask document questions with source references, or practise any topic using clearly labelled general model knowledge. Inference runs through your configured Ollama server; web search contacts external sources when you choose it.</p></section>
<section id="setup"><h2>Start locally in three steps.</h2><ol><li>Clone the <a href="https://github.com/Markkimotho/PreparationPalAI">GitHub repository</a>.</li><li>Run <code>docker compose up --build</code>. The first run downloads the default models.</li><li>Open <code>http://localhost:8000/prepare</code>, choose a topic, and begin.</li></ol><a class="cta" href="/prepare">Open preparation coach →</a></section>
</main><footer>PreparationPalAI · Learn with curiosity. Practise with purpose. <a href="/guide">User guide</a></footer></body></html>''')


@router.get('/robots.txt')
def robots():
    base = base_url()
    content = ('User-agent: *\nAllow: /$\nDisallow: /api/\n' +
               ''.join(f'Disallow: /{route}\n' for route in ('prepare', 'quiz', 'agent', 'chat', 'code', 'flashcards', 'guide')) +
               f'Sitemap: {base}/sitemap.xml\n') if base else 'User-agent: *\nDisallow: /\n'
    return Response(content, media_type='text/plain')


@router.get('/sitemap.xml')
def sitemap():
    base = base_url()
    entry = f'<url><loc>{html.escape(base)}/</loc></url>' if base else ''
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entry}</urlset>', media_type='application/xml')


@router.get('/manifest.webmanifest')
def manifest():
    return Response(json.dumps(dict(name='PreparationPalAI', short_name='PrepPal',
        start_url='/prepare', display='standalone', background_color='#f5f6f2',
        theme_color='#194f3c', icons=[dict(src='/favicon.svg', sizes='any', type='image/svg+xml')])),
        media_type='application/manifest+json')
