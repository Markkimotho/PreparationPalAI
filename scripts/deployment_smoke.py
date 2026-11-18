"""Read-only deployment probes plus opt-in workspace test ingestion/chat.

Set SMOKE_BASE_URL and SMOKE_ACCESS_KEY (environment only; never printed).
Use a disposable workspace for --exercise. The test material remains visible there.
"""
import argparse
import os
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exercise', action='store_true')
    args = parser.parse_args()
    base = os.environ.get('SMOKE_BASE_URL', 'http://127.0.0.1:8000')
    key = os.environ.get('SMOKE_ACCESS_KEY', '')
    headers = {'Authorization': f'Bearer {key}'} if key else {}
    with httpx.Client(base_url=base, headers=headers, timeout=180) as client:
        assert client.get('/health/live').status_code == 200
        assert client.get('/health/ready').status_code == 200, 'Deployment is not ready'
        assert 'Study deeply.' in client.get('/').text
        assert client.get('/api/kb/sources').status_code == 200
        assert client.get('/prepare').status_code == 200
        if args.exercise:
            # The queue path exercises API connectivity, worker and embeddings.
            queued = client.post('/api/kb/jobs/scrape', json={'topic': 'Newton second law force mass acceleration'})
            queued.raise_for_status()
            job = queued.json()['jobs'][0]['id']
            for _ in range(180):
                result = client.get(f'/api/kb/jobs/{job}').json()
                if result['state'] in ('failed', 'completed'):
                    break
                time.sleep(2)
            assert result['state'] == 'completed', 'Ingestion did not complete'
            with client.stream('POST', '/api/chat/stream', json={'question': 'State Newton’s second law.', 'session_id': 'deployment-smoke'}) as response:
                response.raise_for_status()
                frames = list(response.iter_lines())
            assert any('"type": "token"' in line for line in frames)
            assert any('"type": "done"' in line for line in frames)
            assert not any('"type": "error"' in line for line in frames)
    print('Deployment smoke checks passed')


if __name__ == '__main__':
    main()
