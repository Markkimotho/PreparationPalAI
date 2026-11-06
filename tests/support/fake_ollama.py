"""Deterministic protocol stub for container plumbing tests, never a quality judge."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, body, ndjson=False):
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson' if ndjson else 'application/json')
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        if self.path == '/api/tags':
            self.respond(json.dumps({'models': [{'name': name, 'digest': 'smoke-stub'} for name in ('qwen2.5:7b', 'nomic-embed-text')]}))
        else:
            self.respond(json.dumps({'version': 'smoke-stub'}))

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path in ('/api/embed', '/api/embeddings'):
            inputs = body.get('input', body.get('prompt', ''))
            inputs = inputs if isinstance(inputs, list) else [inputs]
            self.respond(json.dumps({'embeddings': [[.1] * 8 for _ in inputs], 'embedding': [.1] * 8}))
            return
        # Exercise the moderation protocol as well as generation plumbing. This
        # is a stub response, never evidence that a real model judged correctly.
        checking = 'safe' in body.get('format', {}).get('properties', {}) if isinstance(body.get('format'), dict) else False
        content = '{"safe": true}' if checking else 'Force equals mass times acceleration. (source: smoke.pdf, page 0)'
        message = dict(model='qwen2.5:7b', message=dict(role='assistant', content=content), done=False)
        done = dict(model='qwen2.5:7b', message=dict(role='assistant', content=''), done=True, eval_count=10, prompt_eval_count=20)
        self.respond(json.dumps(message) + '\n' + json.dumps(done) + '\n', ndjson=True)


if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 11434), Handler).serve_forever()
