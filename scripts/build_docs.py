"""Build two MkDocs portals, then validate their shared project-path deployment."""
import argparse
import functools
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = '/PreparationPalAI/'


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append(attrs[key])


def validate(site):
    pages = {}
    for file in site.rglob('*.html'):
        parser = PageLinks()
        parser.feed(file.read_text())
        pages[file.resolve()] = parser
    failures = []
    for file, page in pages.items():
        if file.name == '404.html':
            continue  # A 404 document can be served at an arbitrary URL depth.
        for href in page.links:
            parsed = urlsplit(href)
            if parsed.scheme and (parsed.scheme not in ('http', 'https') or parsed.hostname != 'markkimotho.github.io'):
                continue
            if parsed.netloc and parsed.hostname != 'markkimotho.github.io':
                continue
            path = unquote(parsed.path)
            if path.startswith(BASE):
                target = site / path[len(BASE):]
            elif path.startswith('/'):
                failures.append(f'{file.relative_to(site)}: URL outside the project base: {href}')
                continue
            else:
                target = file.parent / path if path else file
            target = target.resolve()
            if not target.is_relative_to(site):
                failures.append(f'{file.relative_to(site)}: link escapes output: {href}')
                continue
            if target.is_dir():
                target = target / 'index.html'
            if not target.is_file():
                failures.append(f'{file.relative_to(site)}: missing {href}')
            elif parsed.fragment and target.suffix == '.html' and target in pages:
                if unquote(parsed.fragment) not in pages[target].ids:
                    failures.append(f'{file.relative_to(site)}: missing anchor {href}')
    product = json.loads((site / 'search/search_index.json').read_text())['docs']
    contributors = json.loads((site / 'contribute/search/search_index.json').read_text())['docs']
    if any('AUTH_TOKENS' in entry['text'] for entry in product):
        failures.append('Engineering configuration leaked into learner search')
    if not any('AUTH_TOKENS' in entry['text'] for entry in contributors):
        failures.append('Contributor search is missing the security reference')
    if not product or not contributors:
        failures.append('A portal has no searchable content')
    if failures:
        raise RuntimeError('\n'.join(failures[:30]))
    print(f'Validated {len(pages)} HTML documents, internal links, assets and separate search indexes.')


def build(site):
    site = site.resolve()
    if ROOT.is_relative_to(site) or any(site.is_relative_to(ROOT / d) for d in ('docs', 'engineering', 'docs_theme')):
        raise ValueError('Output must be a generated directory outside documentation sources')
    for config, target in [('mkdocs.yml', site), ('mkdocs-contributors.yml', site / 'contribute')]:
        subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '--strict',
                        '--config-file', str(ROOT / config), '--site-dir', str(target)],
                       cwd=ROOT, check=True)
    (site / '.nojekyll').touch()
    validate(site)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, default=ROOT / 'site')
    parser.add_argument('--preview', action='store_true', help='Serve both portals under /PreparationPalAI/ at port 8088')
    parser.add_argument('--port', type=int, default=8088)
    args = parser.parse_args()
    build(args.site_dir)
    if args.preview:
        with tempfile.TemporaryDirectory(prefix='preppal-docs-preview-') as temp:
            (Path(temp) / 'PreparationPalAI').symlink_to(args.site_dir.resolve(), target_is_directory=True)
            handler = functools.partial(SimpleHTTPRequestHandler, directory=temp)
            print(f'Preview: http://127.0.0.1:{args.port}{BASE}', flush=True)
            ThreadingHTTPServer(('127.0.0.1', args.port), handler).serve_forever()


if __name__ == '__main__':
    main()
