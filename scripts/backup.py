"""Quiesced data backup and verified restore into a new, empty destination."""
import argparse
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def backup(data_dir: Path, archive: Path):
    data_dir = data_dir.resolve()
    archive = archive.resolve()
    if not data_dir.is_dir() or archive.exists() or archive.is_relative_to(data_dir):
        raise ValueError('Use an existing data directory and a new archive outside it')
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in data_dir.rglob('*') if p.is_file())
    if any(p.is_symlink() for p in data_dir.rglob('*')):
        raise ValueError('Data directory must not contain symbolic links')
    manifest = {str(p.relative_to(data_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    if 'backup-manifest.json' in manifest:
        raise ValueError('Reserved backup manifest filename')
    with tempfile.NamedTemporaryFile(dir=archive.parent, suffix='.part', delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with tarfile.open(temporary_path, 'w:gz') as tar:
            for file in files:
                tar.add(file, arcname=str(file.relative_to(data_dir)), recursive=False)
            raw = json.dumps(dict(version=1, files=manifest)).encode()
            entry = tarfile.TarInfo('backup-manifest.json')
            entry.size = len(raw)
            tar.addfile(entry, io.BytesIO(raw))
        # Re-read/check all files before publishing the archive.
        verify(temporary_path)
        temporary_path.rename(archive)
    finally:
        temporary_path.unlink(missing_ok=True)


def verify(archive: Path):
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or sum(m.size for m in members) > 20 * 1024**3:
            raise ValueError('Invalid archive size or duplicate members')
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not member.isfile():
                raise ValueError('Unsafe archive entry')
        manifest = json.load(tar.extractfile('backup-manifest.json'))
        if manifest.get('version') != 1 or set(names) != {*manifest['files'], 'backup-manifest.json'}:
            raise ValueError('Invalid manifest')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(tar.extractfile(name).read()).hexdigest() != digest:
                raise ValueError('Backup integrity check failed')
        return manifest


def restore(archive: Path, destination: Path):
    manifest = verify(archive)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Restore destination must be empty; existing data is never overwritten')
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as tar:
        for name in manifest['files']:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output, tar.extractfile(name) as source:
                shutil.copyfileobj(source, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['backup', 'restore', 'verify'])
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--quiesced', action='store_true', help='Confirm API and ingestion worker have been stopped')
    args = parser.parse_args()
    if args.operation == 'backup':
        if not args.quiesced:
            parser.error('Stop the API/worker and pass --quiesced for a consistent snapshot')
        backup(args.data_dir, args.archive)
    elif args.operation == 'restore':
        restore(args.archive, args.data_dir)
    else:
        verify(args.archive)
    print(f'{args.operation} completed')


if __name__ == '__main__':
    main()
