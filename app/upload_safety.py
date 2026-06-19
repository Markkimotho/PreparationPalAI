"""Upload signature validation and optional operator-supplied scanner."""
import subprocess
from pathlib import Path

from app.config import get_settings


def validate_upload(data: bytes, name: str, content_type: str):
    settings = get_settings()
    if len(data) > settings.upload_max_bytes:
        raise ValueError('File exceeds UPLOAD_MAX_BYTES')
    ext = Path(name).suffix.lower()
    signatures = {
        '.pdf': (b'%PDF-',), '.png': (b'\x89PNG',), '.jpg': (b'\xff\xd8\xff',),
        '.jpeg': (b'\xff\xd8\xff',), '.gif': (b'GIF87a', b'GIF89a'),
        '.tiff': (b'II*\x00', b'MM\x00*'), '.tif': (b'II*\x00', b'MM\x00*'),
        '.bmp': (b'BM',), '.webp': (b'RIFF',),
    }
    if ext not in signatures or not any(data.startswith(s) for s in signatures[ext]):
        raise ValueError('File signature does not match its extension')
    expected = 'application/pdf' if ext == '.pdf' else 'image/'
    if not content_type.startswith(expected) and content_type != 'application/octet-stream':
        raise ValueError('Unsupported upload content type')
    if ext == '.webp' and data[8:12] != b'WEBP':
        raise ValueError('Invalid WebP signature')


def scan(path: Path):
    command = get_settings().scanner_command
    if command:
        result = subprocess.run([*command, str(path)], capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise ValueError('Upload rejected by configured content scanner')
