"""A stand-in for Paddle's transactions API: records what billing asked for, returns a transaction id."""
import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RECORD = sys.argv[2]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        txn = f'txn_{uuid.uuid4().hex[:12]}'
        with open(RECORD, 'a') as f:
            f.write(json.dumps({'id': txn, 'request': body, 'auth': self.headers.get('Authorization', '')[:12]}) + '\n')
        data = json.dumps({'data': {'id': txn}}).encode()
        self.send_response(201)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
