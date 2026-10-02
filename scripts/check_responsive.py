"""Optional browser smoke test. Run the built app on :8018 first.

Install test tooling: pip install playwright && playwright install chromium
Uses mocked AI/KB responses; never downloads or invokes a model.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    base = os.environ.get('CHECK_BASE_URL', 'http://127.0.0.1:8018')
    output = Path(os.environ.get('CHECK_OUTPUT', '/tmp/preparationpal-screenshots'))
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get('CHECK_BROWSER') or None)
        page = browser.new_page()

        def api(route):
            path = route.request.url.split('/api/', 1)[1]
            body = {'health': dict(online=False, model_count=0),
                    'auth/status': dict(enabled=False),
                    'models': dict(supported=['glm4:9b', 'deepseek-r1:7b'], installed=[]),
                    'kb/count': dict(count=0), 'kb/sources': dict(sources=[]), 'kb/jobs': dict(jobs=[]),
                    'flashcards': dict(decks=[])}.get(path, dict(sessions=[], weak_topics=[]))
            route.fulfill(content_type='application/json', body=json.dumps(body))

        page.route('**/api/**', api)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for width in (320, 375, 768, 1440):
            page.set_viewport_size(dict(width=width, height=900))
            for route in ('prepare', 'quiz', 'agent', 'code', 'chat', 'flashcards', 'guide'):
                page.goto(f'{base}/{route}')
                page.get_by_role('main').wait_for()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, route)
                small = page.evaluate('''() => [...document.querySelectorAll('button')].filter(e =>
                    e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0 &&
                    e.checkVisibility() && e.getBoundingClientRect().height < 43.9).map(e =>
                    ({text:e.textContent, height:e.getBoundingClientRect().height, class:e.className}))''')
                assert not small, (width, route, small)
                if route == 'prepare':
                    page.screenshot(path=str(output / f'coach-{width}.png'), full_page=True)
            if width < 768:
                page.goto(f'{base}/prepare')
                trigger = page.get_by_role('button', name='Open menu')
                trigger.click()
                page.get_by_role('button', name='Close menu').wait_for()
                page.keyboard.press('Escape')
                assert trigger.evaluate('(el) => el === document.activeElement')
        page.goto(base)
        page.get_by_role('heading', name='Study deeply. Prepare confidently.').wait_for()
        page.screenshot(path=str(output / 'landing.png'), full_page=True)
        assert not errors, errors
        browser.close()
    print(f'Responsive smoke checks passed; screenshots: {output}')


if __name__ == '__main__':
    main()
