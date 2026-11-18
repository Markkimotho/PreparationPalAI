"""Public marketing HTML renders without JavaScript or an Ollama connection."""
import hashlib
import html
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from app.config import get_settings

router = APIRouter(include_in_schema=False)

_FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'


@lru_cache(maxsize=1)
def stylesheet_version() -> str:
    """A content hash for /landing.css. The service worker serves static files stale-while-revalidate,
    so an unversioned URL pairs new HTML with the old stylesheet on the first visit after a deploy."""
    for candidate in (_FRONTEND / 'dist' / 'landing.css', _FRONTEND / 'public' / 'landing.css'):
        if candidate.exists():
            return hashlib.sha256(candidate.read_bytes()).hexdigest()[:12]
    return 'dev'


def base_url() -> str:
    value = get_settings().public_base_url.rstrip('/')
    parsed = urlsplit(value)
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''


@router.get('/', response_class=HTMLResponse)
def landing():
    base = base_url()
    title = 'PreparationPalAI — Study deeply. Prepare confidently.'
    description = 'Exam revision and interview practice built from your own notes: answers with sources, quizzes that explain, flashcards and a coach. Pay only for what you use; 500 free credits to start.'
    image = get_settings().social_image
    image = image if image.startswith('https://') else base + '/' + image.lstrip('/')
    canonical = f'<link rel="canonical" href="{html.escape(base)}/">' if base else '<meta name="robots" content="noindex, nofollow">'
    schema = json.dumps({'@context': 'https://schema.org', '@type': 'SoftwareApplication',
        'name': 'PreparationPalAI', 'applicationCategory': 'EducationalApplication',
        'operatingSystem': 'macOS, Linux, Windows', 'description': description,
        **({'url': base + '/'} if base else {})}).replace('<', '\\u003c')
    return HTMLResponse(f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{description}">{canonical}
<meta property="og:title" content="{title}"><meta property="og:description" content="{description}">
<meta property="og:type" content="website"><meta property="og:url" content="{html.escape(base)}/">
<meta property="og:image" content="{html.escape(image)}"><meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{html.escape(image)}"><link rel="icon" href="/favicon.svg">
<meta name="theme-color" content="#fbfaf6">
<link rel="manifest" href="/manifest.webmanifest"><script type="application/ld+json">{schema}</script>
<link rel="stylesheet" href="/fonts.css"><link rel="stylesheet" href="/landing.css?v={stylesheet_version()}">
</head><body>
<div class="glow glow-a" aria-hidden="true"></div><div class="glow glow-b" aria-hidden="true"></div>
<nav aria-label="Main">
  <a class="brand" href="/"><span class="mark" aria-hidden="true"></span>PreparationPalAI</a>
  <div class="links"><a href="#how">How it works</a><a href="#pricing">Pricing</a><a href="https://markkimotho.github.io/PreparationPalAI/">Guide</a>
  <a class="ghost" href="/prepare">Sign in</a><a class="cta" href="/prepare">Start free</a></div>
</nav>
<main>
<section class="hero">
  <div class="hero-copy">
    <p class="pill"><span aria-hidden="true">✦</span> 500 free credits to start</p>
    <h1>Study deeply.<br><span class="grad">Prepare confidently.</span></h1>
    <p class="lead">Exam revision and interview practice built from your own notes: answers with sources, quizzes that explain, flashcards that stick, and a coach that scores you.</p>
    <div class="actions"><a class="cta big" href="/prepare">Start free <span aria-hidden="true">→</span></a><a class="ghost big" href="#how">See how it works</a></div>
    <p class="fine">Pay only for what you use. Open models first; Claude, GPT and Grok when you want them.</p>
  </div>
  <div class="scene" aria-hidden="true">
    <div class="orb orb-1"></div><div class="orb orb-2"></div>
    <div class="phone">
      <div class="notch"></div>
      <div class="screen">
        <div class="ph-head"><span class="ph-av">A</span><span><b>Good evening, Amani</b><small>12 of 20 today</small></span></div>
        <div class="flip"><div class="flip-in">
          <div class="face front"><span class="tag">Question</span><b>What makes most of a cell’s ATP?</b><small>Tap to flip</small></div>
          <div class="face back"><span class="tag">Answer</span><b>The mitochondria</b></div>
        </div></div>
        <div class="ph-buttons"><span class="rb amber">↺</span><span class="rb white">⟳</span><span class="rb green">✓</span></div>
      </div>
    </div>
    <div class="float notes"><div class="sheet s3"></div><div class="sheet s2"></div><div class="sheet s1"><i></i><i></i><i class="hl"></i><i></i></div></div>
    <div class="float quiz"><span class="opt">A <em>Binary search</em></span><span class="opt ok">✓ <em>O(log n)</em></span></div>
    <div class="float medal"><div class="coin"><span class="cf">A+</span><span class="cb">92%</span></div></div>
    <div class="float streak">🔥 <b>7-day streak</b></div>
    <span class="spark k1">✦</span><span class="spark k2">✦</span><span class="spark k3">✦</span>
  </div>
</section>

<section class="how" id="how">
  <h2>From notes to know-it-cold<br>in three steps.</h2>
  <ol class="steps">
    <li class="step blue"><div class="art art-notes" aria-hidden="true"><div class="sheet s3"></div><div class="sheet s2"></div><div class="sheet s1"><i></i><i class="hl"></i><i></i></div></div>
      <span class="num">1</span><h3>Add your notes</h3><p>Upload PDFs or photos, or start from a topic. Ask anything and get answers with the sources they came from.</p></li>
    <li class="step amber"><div class="art art-flip" aria-hidden="true"><div class="mini-flip"><div class="mf-in"><div class="mf f">Q</div><div class="mf b">A</div></div></div></div>
      <span class="num">2</span><h3>Practise</h3><p>Quizzes that explain every answer and flashcards you flip and throw. Your streak and daily goal keep you going.</p></li>
    <li class="step coral"><div class="art art-coach" aria-hidden="true"><div class="bubble q">Explain a hash collision.</div><div class="bubble a">Two keys, one slot…</div><div class="score">86</div></div>
      <span class="num">3</span><h3>Get coached</h3><p>Exam, interview and recap practice scored like the real thing, with feedback on what to do next.</p></li>
  </ol>
</section>

<section class="features" aria-labelledby="features-title">
  <h2 id="features-title">Everything you need to prepare.</h2>
  <div class="grid">
    <article class="tile blue"><span class="ic" aria-hidden="true">✦</span><h3>Study from your notes</h3><p>A tutor that knows your material, plus coding help for technical prep.</p></article>
    <article class="tile amber"><span class="ic" aria-hidden="true">?</span><h3>Quizzes that explain</h3><p>Multiple choice and short answers, marked instantly with the reasoning.</p></article>
    <article class="tile green"><span class="ic" aria-hidden="true">▤</span><h3>Flashcards that stick</h3><p>Made from your notes in seconds; study offline on your phone.</p></article>
    <article class="tile coral"><span class="ic" aria-hidden="true">◎</span><h3>A coach for the real thing</h3><p>Mock exams and interviews with scores, hints and follow-ups.</p></article>
  </div>
</section>

<section class="personal">
  <div class="avatars" aria-hidden="true"><span class="av v1">A</span><span class="av v2">K</span><span class="av v3">M</span><span class="av v4">S</span><span class="av v5">L</span></div>
  <div><h2>Made for you, not for everyone.</h2>
  <p>Tell PrepPal your subjects, your level and what you are preparing for. Every answer, quiz and practice session is pitched to you, in your language, and your own colour and avatar follow you to every device.</p></div>
</section>

<section class="pricing" id="pricing" aria-labelledby="pricing-title">
  <h2 id="pricing-title">Pay for what you use. Nothing more.</h2>
  <p class="sub">No subscription. Credits cover the AI and hosting, with a small margin to keep the lights on.</p>
  <div class="plans">
    <div class="plan"><span class="big-n">500</span><h3>free credits</h3><p>When you confirm your email. Enough for dozens of quizzes on open models.</p></div>
    <div class="plan featured"><span class="big-n">$5</span><h3>and up</h3><p>Top up 5,000 credits or more, only when you need them. One credit is a tenth of a cent.</p><a class="cta" href="/prepare">Start free</a></div>
    <div class="plan"><span class="big-n">≈14</span><h3>credits a quiz</h3><p>Open models (Qwen, GLM) cost the least; premium models are there when you want them.</p></div>
  </div>
  <p class="devices">On the web today. iPhone and Android apps are coming soon, with the same account and balance.</p>
</section>

<section class="setup" id="setup"><div><h2>Prefer to run it yourself?</h2><p>PreparationPalAI is open source. Run it on your computer with your own Ollama models, free and unmetered.</p></div>
<ol><li><a href="https://github.com/Markkimotho/PreparationPalAI">Clone the repository</a>.</li><li>Run <code>docker compose up --build</code>. The first run downloads the default models.</li><li>Open <code>localhost:8000/prepare</code> and choose a topic.</li></ol></section>
</main>
<footer><span class="brand"><span class="mark" aria-hidden="true"></span>PreparationPalAI</span><div><a href="https://markkimotho.github.io/PreparationPalAI/">Documentation</a><a href="https://github.com/Markkimotho/PreparationPalAI">GitHub</a></div></footer>
</body></html>""")


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
