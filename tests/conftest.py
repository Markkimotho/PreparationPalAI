import pytest
from app.config import get_base_settings


@pytest.fixture(autouse=True)
def isolated_usage_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'usage_db', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(get_base_settings(), 'jobs_dir', str(tmp_path / 'jobs'))
    monkeypatch.setattr(get_base_settings(), 'embedded_worker', False)
