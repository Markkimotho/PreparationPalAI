"""Isolated extraction entrypoint. Its stdout is a bounded IPC JSON file."""
import json
import sys
from pathlib import Path


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
        if sys.platform == 'linux':
            resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    except (ImportError, ValueError, OSError):
        pass
    from app.ingestion import load_and_chunk_pdf, load_and_chunk_image
    path, name, output = sys.argv[1:]
    loader = load_and_chunk_pdf if Path(path).suffix == '.pdf' else load_and_chunk_image
    docs = loader(path, source_name=name)
    serialized = json.dumps([dict(page_content=d.page_content, metadata=d.metadata) for d in docs])
    if len(serialized.encode()) > 10 * 1024 * 1024:
        raise ValueError('Extracted content exceeds limit')
    Path(output).write_text(serialized)


if __name__ == '__main__':
    main()
