"""Run document parsers in a child process with a hard elapsed-time deadline."""
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from langchain_core.documents import Document
from app.config import get_settings
from app.upload_safety import scan


def extract(path, source_name=None):
    import json
    path = Path(path)
    scan(path)
    with tempfile.TemporaryDirectory(prefix='preppal-extract-') as temp:
        output = Path(temp) / 'documents.json'
        process = subprocess.Popen([sys.executable, '-m', 'app.extract_worker', str(path),
            source_name or path.name, str(output)], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            process.wait(timeout=get_settings().extract_timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise ValueError('Document extraction timed out') from None
        if process.returncode or not output.exists():
            raise ValueError('Document could not be safely extracted')
        return [Document(**d) for d in json.loads(output.read_text())]
