"""Identify one person's mailbox so the free starter allowance is granted once per person."""
import hashlib
import unicodedata
from functools import lru_cache
from pathlib import Path

GMAIL = {'gmail.com', 'googlemail.com'}
DISPOSABLE_FILE = Path(__file__).parent / 'disposable_domains.txt'


def _split(email: str) -> tuple[str, str] | None:
    text = unicodedata.normalize('NFKC', email or '').strip().casefold()
    if text.count('@') != 1 or ' ' in text:
        return None
    local, domain = text.split('@')
    return (local, domain) if local and '.' in domain and not domain.startswith('.') and not domain.endswith('.') else None


def is_valid(email: str) -> bool:
    return _split(email) is not None


def email_key(email: str) -> str:
    """Stable key for the mailbox behind an address: case, `+tag` and (at Gmail) dots do not matter."""
    parts = _split(email)
    if parts is None:
        raise ValueError('not an email address')
    local, domain = parts
    local = local.split('+', 1)[0]
    if domain in GMAIL:
        local, domain = local.replace('.', ''), 'gmail.com'
    return hashlib.sha256(f'{local}@{domain}'.encode()).hexdigest()


@lru_cache
def _disposable() -> frozenset[str]:
    lines = (line.strip().casefold() for line in DISPOSABLE_FILE.read_text().splitlines())
    return frozenset(line for line in lines if line and not line.startswith('#'))


def is_disposable(email: str) -> bool:
    parts = _split(email)
    if parts is None:
        return False
    labels = parts[1].split('.')
    return any('.'.join(labels[i:]) in _disposable() for i in range(len(labels) - 1))
