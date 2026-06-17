"""Public-web GET with validated, pinned DNS and bounded response bodies."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit


def public_address(url: str) -> tuple[str, int, str]:
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only public HTTP(S) URLs without credentials are allowed')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    if port not in (80, 443):
        raise ValueError('Only web ports 80 and 443 are allowed')
    host = parsed.hostname.encode('idna').decode()
    addresses = {r[4][0] for r in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('Private, loopback, reserved and metadata destinations are blocked')
    return host, port, sorted(addresses)[0]


def fetch_text(url: str, timeout: float = 20, max_bytes: int = 2_000_000) -> str:
    deadline = time.monotonic() + timeout
    for _ in range(6):
        host, port, ip = public_address(url)
        parsed = urlsplit(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Download timed out')
        connection = http.client.HTTPConnection(host, port, timeout=remaining)
        raw = socket.create_connection((ip, port), timeout=remaining)
        try:
            # Host remains the original name for Host and TLS; connection uses the
            # validated IP directly, so a second DNS answer cannot rebind it.
            connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host) if parsed.scheme == 'https' else raw
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            connection.request('GET', path, headers={'User-Agent': 'PreparationPalAI/1.0', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    raise ValueError('Redirect has no destination')
                url = urljoin(url, location)
                continue  # Every redirect is resolved, validated, and pinned anew.
            if response.status != 200:
                raise ValueError('Remote server rejected the request')
            content_type = response.getheader('Content-Type', '').split(';')[0].lower()
            if content_type not in ('text/html', 'application/xhtml+xml', 'text/plain'):
                raise ValueError('Unsupported remote content type')
            if response.getheader('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Compressed responses are not accepted')
            if int(response.getheader('Content-Length', '0')) > max_bytes:
                raise ValueError('Download is too large')
            content = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Download timed out')
                chunk = response.read1(min(65536, max_bytes - len(content) + 1))
                if not chunk:
                    return content.decode('utf-8', errors='replace')
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise ValueError('Download is too large')
        finally:
            connection.close()
            raw.close()
    raise ValueError('Too many redirects')
