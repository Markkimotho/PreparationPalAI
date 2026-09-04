import json
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from app.api import app


def test_pull_stream_reports_bytes_and_done():
    response = Mock()
    response.iter_lines.return_value = [json.dumps(dict(status='pulling', completed=10, total=20)), json.dumps(dict(status='success'))]
    with patch('app.api.httpx.stream') as stream:
        stream.return_value.__enter__.return_value = response
        result = TestClient(app).post('/api/models/pull/stream', json=dict(model='glm4:9b'))
    assert '"completed": 10' in result.text
    assert '"total": 20' in result.text
    assert '"done"' in result.text
