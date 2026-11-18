"""In-process OpenAI-compatible server for gateway-mode tests. A protocol stub, never a quality judge."""
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOpenAI:
    """Configure behaviour through attributes; inspect `requests` afterwards."""

    def __init__(self):
        self.requests: list[dict] = []
        self.gets: list[str] = []               # GET paths, for cache assertions
        self.replies: list[str] = []          # consumed first-in-first-out, then default_reply
        self.default_reply = 'hello'
        self.usage: dict | None = {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}
        self.status: int | None = None          # force an HTTP error for chat calls
        self.models = ['open-default', 'open-fast', 'guard', 'embed-default']
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                outer.gets.append(self.path)
                if self.path.endswith('/models'):
                    self.send(200, {'object': 'list', 'data': [{'id': m, 'object': 'model'} for m in outer.models]})
                else:
                    self.send(200, {'ok': True})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])) or b'{}')
                outer.requests.append(dict(path=self.path, body=body, auth=self.headers.get('Authorization')))
                if outer.status:
                    return self.send(outer.status, {'error': {'message': 'boom', 'type': 'server_error'}})
                if self.path.endswith('/embeddings'):
                    inputs = body['input'] if isinstance(body['input'], list) else [body['input']]
                    usage = {'prompt_tokens': 5 * len(inputs), 'total_tokens': 5 * len(inputs)} if outer.usage else None
                    payload = {'object': 'list', 'model': body['model'],
                               'data': [{'object': 'embedding', 'index': i, 'embedding': [.1] * 8} for i, _ in enumerate(inputs)]}
                    if usage:
                        payload['usage'] = usage
                    return self.send(200, payload)
                schema = ((body.get('response_format') or {}).get('json_schema') or {}).get('schema') or {}
                if 'safe' in schema.get('properties', {}):
                    content = '{"safe": true}'
                else:
                    content = outer.replies.pop(0) if outer.replies else outer.default_reply
                payload = {'id': f'chatcmpl-{uuid.uuid4().hex}', 'object': 'chat.completion', 'created': 0,
                           'model': body['model'],
                           'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': content}}]}
                if outer.usage:
                    payload['usage'] = outer.usage
                self.send(200, payload)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)

    @property
    def url(self) -> str:
        return f'http://127.0.0.1:{self.server.server_address[1]}'

    def chat_requests(self, alias: str | None = None) -> list[dict]:
        return [r['body'] for r in self.requests
                if r['path'].endswith('/chat/completions') and (alias is None or r['body']['model'] == alias)]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
