"""Each learner's profile: who they are, how the app looks for them, and what the tutor tailors to.

One profile per workspace (account). Stored in Postgres (hosted) or one JSON file per workspace
(self-hosted). The learning half maps onto `PromptProfile`, so every AI request that does not send
its own profile is pitched to the learner's subjects, level, goal and language (see `tailor`).
Account deletion removes the profile (registered with `app.purge`).
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import db, purge
from app.config import get_base_settings
from app.prompt_library import PromptProfile
from app.workspace import workspace_id

Accent = Literal['blue', 'amber', 'green', 'coral']
Goal = Literal['exam', 'interview', 'understand']
Subject = Annotated[str, Field(min_length=1, max_length=60)]

GOAL_OBJECTIVES = {
    'exam': 'Prepare for an exam: recall, exam-style questions and timing.',
    'interview': 'Prepare for interviews: explain clearly, reason out loud, handle follow-ups.',
    'understand': 'Understand the subject deeply: intuition first, then detail.',
}


class LearnerProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    display_name: str = Field(default='', max_length=40)
    avatar_seed: str = Field(default='', max_length=32, pattern=r'^[A-Za-z0-9_-]*$')
    accent: Accent = 'blue'
    goal: Goal = 'understand'
    subjects: list[Subject] = Field(default_factory=list, max_length=6)
    level: Literal['beginner', 'intermediate', 'advanced'] = 'intermediate'
    exam_context: str = Field(default='', max_length=200)
    language: str = Field(default='English', min_length=1, max_length=60)
    daily_goal: int = Field(default=10, ge=1, le=200)
    onboarded: bool = False

    @field_validator('subjects')
    @classmethod
    def _distinct(cls, subjects: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for s in subjects:
            seen.setdefault(s.casefold(), s)
        return list(seen.values())


class StoredProfile(LearnerProfile):
    updated_at: str | None = None


def prompt_profile(profile: LearnerProfile) -> PromptProfile:
    """The tutor's view of the learner: their first subject leads, the goal becomes an objective."""
    objectives = [GOAL_OBJECTIVES[profile.goal]] + [f'Cover {s}.' for s in profile.subjects[1:5]]
    return PromptProfile(discipline=profile.subjects[0] if profile.subjects else 'general', level=profile.level,
                         objectives=objectives, language=profile.language, exam_context=profile.exam_context)


def tailor(requested: PromptProfile | None) -> PromptProfile | None:
    """Use the learner's stored profile unless the request brought its own (anything but defaults)."""
    if requested is not None and requested != PromptProfile():
        return requested
    stored = load()
    return prompt_profile(stored) if stored.onboarded else requested


# ---- storage ---------------------------------------------------------------------------------

def _file(workspace: str) -> Path:
    return Path(get_base_settings().profiles_dir) / f'{workspace}.json'


def load(workspace: str | None = None) -> StoredProfile:
    workspace = workspace or workspace_id.get()
    if db.enabled():
        with db.transaction() as conn:
            row = conn.execute('SELECT body, updated_at FROM app.learner_profiles WHERE workspace = %s', (workspace,)).fetchone()
        return StoredProfile(**row['body'], updated_at=row['updated_at'].isoformat()) if row else StoredProfile()
    path = _file(workspace)
    if not path.exists():
        return StoredProfile()
    try:
        return StoredProfile(**json.loads(path.read_text()))
    except (ValueError, TypeError):
        return StoredProfile()                       # a damaged file must not lock the learner out


def save(profile: LearnerProfile, workspace: str | None = None) -> StoredProfile:
    workspace = workspace or workspace_id.get()
    body = LearnerProfile.model_validate(profile.model_dump()).model_dump()
    now = datetime.now(timezone.utc)
    if db.enabled():
        with db.transaction() as conn:
            conn.execute("""INSERT INTO app.learner_profiles (workspace, body, updated_at) VALUES (%s, %s, %s)
                            ON CONFLICT (workspace) DO UPDATE SET body = EXCLUDED.body, updated_at = EXCLUDED.updated_at""",
                         (workspace, json.dumps(body), now))
    else:
        path = _file(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        with os.fdopen(fd, 'w') as f:                   # write then rename: never a half-written profile
            json.dump({**body, 'updated_at': now.isoformat()}, f)
        os.replace(tmp, path)
    return StoredProfile(**body, updated_at=now.isoformat())


def _purge(workspace: str) -> int:
    if db.enabled():
        with db.transaction() as conn:
            return conn.execute('DELETE FROM app.learner_profiles WHERE workspace = %s', (workspace,)).rowcount
    path = _file(workspace)
    if path.exists():
        path.unlink()
        return 1
    return 0


purge.register('profile', _purge)
