"""Exercise an ephemeral container against the deterministic Ollama protocol stub."""
import json
import time
import urllib.request


def call(path, body=None, content_type='application/json'):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    request = urllib.request.Request('http://127.0.0.1:8000' + path, data=data,
                                     headers={'Content-Type': content_type})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode()


def main():
    for attempt in range(45):
        try:
            call('/health/live')
            break
        except Exception:
            if attempt == 44:
                raise
            time.sleep(2)
    assert 'Study deeply.' in call('/')
    assert 'id="root"' in call('/prepare')
    # Construct a real, minimal PDF using the runtime's actual parser dependency.
    import fitz
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), 'Newton second law: force equals mass times acceleration. ' * 8)
    pdf = document.tobytes()
    document.close()
    boundary = 'preppal-smoke-boundary'
    multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="smoke.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
                 + pdf + f'\r\n--{boundary}--\r\n'.encode())
    queued = json.loads(call('/api/kb/jobs/upload', multipart, f'multipart/form-data; boundary={boundary}'))
    for _ in range(60):
        result = json.loads(call('/api/kb/jobs/' + queued['jobs'][0]['id']))
        if result['state'] in ('failed', 'completed'):
            break
        time.sleep(2)
    assert result['state'] == 'completed', result
    assert json.loads(call('/api/kb/count'))['count'] > 0
    stream = call('/api/chat/stream', {'question': 'State Newton second law.', 'session_id': 'container-smoke'})
    assert '"type": "token"' in stream and '"type": "done"' in stream
    assert '"type": "error"' not in stream
    assert 'smoke.pdf' in stream
    assert json.loads(call('/health/ready'))['ready']
    print('Container queue/extraction/embedding/SSE/frontend smoke passed (stub inference, not model quality).')


if __name__ == '__main__':
    main()
