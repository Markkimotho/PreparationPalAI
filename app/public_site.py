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
    title = 'PreparationPalAI — Exam and interview practice with local AI'
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
<link rel="stylesheet" href="/fonts.css"><link rel="stylesheet" href="/landing.css">
</head><body>
<nav aria-label="Main"><a class="brand" href="/">PreparationPalAI</a><div><a href="https://markkimotho.github.io/PreparationPalAI/">User guide</a><a href="/prepare">Open workspace</a></div></nav>
<main>
<section class="hero">
<h1>Practise the questions<br>you need to answer.</h1>
<p>Exam revision and technical interview practice, powered by local AI.</p>
<div class="actions"><a class="primary" href="/prepare">Start a practice session</a><a href="#setup">Set up on your computer</a></div>
</section>
<figure class="workspace"><img src="/workspace-preview.png" width="1440" height="960" alt="The Preparation Coach workspace with topic, study mode, and question settings" fetchpriority="high"><figcaption>The preparation workspace. Choose a topic and start with a short session.</figcaption></figure>
<section class="tools"><div><h2>Bring your notes.<br>Work through the gaps.</h2><p>Use your course material or start with a topic. Review generated answers against your references.</p></div>
<dl>
<div><dt>Exam practice</dt><dd>Answer mixed questions with an optional timer, then review missed topics.</dd></div>
<div><dt>Technical interviews</dt><dd>Explain your approach and work through follow-up questions.</dd></div>
<div><dt>Revision</dt><dd>Ask about your documents, recap a concept, or build a flashcard deck.</dd></div>
</dl></section>
<section class="setup" id="setup"><div><h2>Run it locally.</h2><p>Choose an installed Qwen, GLM, DeepSeek, or another supported Ollama model. Upload PDFs and images when you want document-based practice.</p><p>Inference uses your configured Ollama server. Optional web search contacts external sources.</p></div>
<ol><li><a href="https://github.com/Markkimotho/PreparationPalAI">Clone the repository</a>.</li><li>Run <code>docker compose up --build</code>. The first run downloads the default models.</li><li>Open <code>localhost:8000/prepare</code> and choose a topic.</li></ol></section>
</main><footer><span>PreparationPalAI</span><div><a href="https://markkimotho.github.io/PreparationPalAI/">Documentation</a><a href="https://github.com/Markkimotho/PreparationPalAI">GitHub</a></div></footer>
</body></html>''')


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
