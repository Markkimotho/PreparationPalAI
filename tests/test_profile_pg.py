"""Learner profiles on Postgres: round trip, upsert and per-account isolation."""
import pytest

from app import profile
from app.config import get_base_settings

pytestmark = pytest.mark.usefixtures('pg')


@pytest.fixture(autouse=True)
def postgres_mode(monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'storage_backend', 'postgres')


def test_round_trip_upsert_and_isolation(pg):
    assert profile.load('u-alice').onboarded is False
    profile.save(profile.LearnerProfile(display_name='Alice', subjects=['Physics'], onboarded=True), 'u-alice')
    profile.save(profile.LearnerProfile(display_name='Alice B', subjects=['Maths'], onboarded=True), 'u-alice')
    stored = profile.load('u-alice')
    assert (stored.display_name, stored.subjects, stored.onboarded) == ('Alice B', ['Maths'], True) and stored.updated_at
    assert profile.load('u-bob').display_name == ''
