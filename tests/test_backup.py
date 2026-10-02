import io
import tarfile
import pytest
from scripts.backup import backup, restore, verify


def test_round_trip_preserves_persistent_state(tmp_path):
    data = tmp_path / 'data'
    (data / 'coach').mkdir(parents=True)
    (data / 'coach' / 'sessions.sqlite3').write_bytes(b'durable study history')
    archive = tmp_path / 'backup.tar.gz'
    backup(data, archive)
    target = tmp_path / 'restored'
    restore(archive, target)
    assert (target / 'coach' / 'sessions.sqlite3').read_bytes() == b'durable study history'
    with pytest.raises(ValueError, match='empty'):
        restore(archive, target)


def test_restore_rejects_path_traversal(tmp_path):
    archive = tmp_path / 'bad.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        entry = tarfile.TarInfo('../outside')
        entry.size = 1
        tar.addfile(entry, io.BytesIO(b'x'))
    with pytest.raises(ValueError, match='Unsafe'):
        verify(archive)
