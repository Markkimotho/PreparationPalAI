"""Smoke-check a running PreparationPalAI instance that uses the AI gateway.

    python scripts/smoke_gateway.py http://localhost:8000 [--token WORKSPACE_KEY]

Runs four real calls (health, model list, a 2-question quiz, one streamed chat answer)
and exits non-zero if any fail. Each call goes through the gateway, so it spends a few
credits worth of tokens. Check the gateway's /spend/logs/v2 to see the recorded usage.
"""
import argparse
import json
import sys
from dataclasses import dataclass

import httpx


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


def _check(name, fn) -> Result:
    try:
        detail = fn()
        return Result(name, True, detail or 'ok')
    except Exception as exc:  # noqa: BLE001 - a smoke test reports every failure
        return Result(name, False, f'{type(exc).__name__}: {exc}')


def run(client: httpx.Client) -> list[Result]:
    def health():
        body = client.get('/api/health').raise_for_status().json()
        assert body['online'], 'the model gateway is not reachable'
        return f"{body['model_count']} models"

    def models():
        body = client.get('/api/models').raise_for_status().json()
        assert body['catalogue'], 'no models are available to learners'
        return ', '.join(m['id'] for m in body['catalogue'])

    def quiz():
        response = client.post('/api/quiz/generate', json={'topic': "Newton's second law", 'n': 2, 'question_type': 'mcq'})
        response.raise_for_status()
        questions = response.json()
        assert len(questions) >= 1, 'no questions returned'
        return f'{len(questions)} questions'

    def chat():
        response = client.post('/api/chat/stream', json={'question': 'In one sentence, what is Newton\'s second law?'})
        response.raise_for_status()
        frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        errors = [f['message'] for f in frames if f['type'] == 'error']
        assert not errors, errors[0]
        text = ''.join(f.get('text', '') for f in frames if f['type'] == 'token')
        assert text.strip(), 'empty answer'
        return f'{len(text)} characters'

    return [_check('health', health), _check('models', models), _check('quiz', quiz), _check('chat', chat)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('base_url')
    parser.add_argument('--token', help='workspace access key when AUTH_ENABLED=true')
    parser.add_argument('--timeout', type=float, default=240)
    args = parser.parse_args(argv)
    headers = {'Authorization': f'Bearer {args.token}'} if args.token else {}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=args.timeout) as client:
        results = run(client)
    for result in results:
        print(f"{'OK  ' if result.ok else 'FAIL'} {result.name}: {result.detail}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
