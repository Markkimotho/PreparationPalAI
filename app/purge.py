"""Delete everything stored for one workspace. Each store registers a deleter.

`purge_workspace` is idempotent. One failing store never stops the others; the failures are
reported together so the learner can retry. The workspace name is validated because it becomes
part of file paths.
"""
import re
import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

from app.config import get_base_settings

SAFE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
_stores: dict[str, Callable[[str], int]] = {}


class PurgeIncomplete(Exception):
    def __init__(self, failed: list[str]):
        super().__init__('Some stored data could not be removed yet')
        self.failed = failed


def register(name: str, deleter: Callable[[str], int]) -> None:
    _stores[name] = deleter


def purge_workspace(workspace: str) -> dict[str, int]:
    if workspace == 'local' or not SAFE.fullmatch(workspace or ''):
        raise ValueError('Refusing to purge this workspace')
    report: dict[str, int] = {}
    failed: list[str] = []
    for name, deleter in list(_stores.items()):
        try:
            report[name] = deleter(workspace)
        except Exception:  # noqa: BLE001 - keep going; report which stores need a retry
            failed.append(name)
    if failed:
        raise PurgeIncomplete(failed)
    return report


def _remove_tree(path: Path) -> int:
    if not path.exists():
        return 0
    count = sum(1 for p in path.rglob('*') if p.is_file())
    shutil.rmtree(path)
    return count


def _flashcards(workspace: str) -> int:
    from app import db
    if db.enabled():
        with db.transaction() as conn:
            return conn.execute('DELETE FROM app.flashcard_decks WHERE workspace = %s', (workspace,)).rowcount
    return _remove_tree(Path(get_base_settings().flashcards_dir) / 'workspaces' / workspace)


def _vectors(workspace: str) -> int:
    from app import vectorstore
    vectorstore._workspace_stores.pop(workspace, None)
    removed = _remove_tree(Path(get_base_settings().chroma_persist_dir) / 'workspaces' / workspace)
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()      # forget handles to the deleted folder
    except Exception:  # noqa: BLE001
        pass
    return removed


def _vectors_postgres(workspace: str) -> int:
    from app import db
    if not db.enabled():
        return 0
    with db.transaction() as conn:
        return conn.execute('DELETE FROM app.chunks WHERE workspace = %s', (workspace,)).rowcount


def _coach(workspace: str) -> int:
    """Coach sessions and drawing submissions share this workspace folder."""
    return _remove_tree(Path(get_base_settings().coach_db).parent / 'workspaces' / workspace)


def _jobs(workspace: str) -> int:
    from app.jobs import store
    return store().purge(workspace) + _remove_tree(Path(get_base_settings().jobs_dir) / 'files' / workspace)


def _usage(workspace: str) -> int:
    from app import db
    if db.enabled():
        with db.transaction() as conn:
            return conn.execute('DELETE FROM app.usage_events WHERE workspace = %s', (workspace,)).rowcount
    path = Path(get_base_settings().usage_db)
    if not path.exists():
        return 0
    conn = sqlite3.connect(path, timeout=10)
    try:
        with conn:
            return conn.execute('DELETE FROM usage WHERE workspace = ?', (workspace,)).rowcount
    except sqlite3.OperationalError:                 # table not created yet
        return 0
    finally:
        conn.close()


def _chat_memory(workspace: str) -> int:
    """Conversation history and agent checkpoints are keyed `<workspace>:<thread>`."""
    from app import code_assistant, memory, quiz_agent
    prefix, removed = f'{workspace}:', 0
    for key in [k for k in memory._histories if k.startswith(prefix)]:
        memory._histories.pop(key, None)
        removed += 1
    for saver in (code_assistant._checkpointer, quiz_agent._checkpointer):
        for thread in [t for t in list(saver.storage) if t.startswith(prefix)]:
            saver.delete_thread(thread)
            removed += 1
    return removed


for _name, _fn in (('flashcards', _flashcards), ('vectors', _vectors), ('vectors_postgres', _vectors_postgres), ('coach', _coach),
                   ('jobs', _jobs), ('usage', _usage), ('chat_memory', _chat_memory)):
    register(_name, _fn)
