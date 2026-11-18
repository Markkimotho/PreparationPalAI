import json
from pathlib import Path

import yaml

from billing.api import app

CONTRACT = Path(__file__).resolve().parents[3] / 'contracts' / 'billing.yaml'


def test_checked_in_contract_matches_the_running_api():
    """Regenerate with: python -m billing.api --dump-openapi > ../../contracts/billing.yaml"""
    assert yaml.safe_load(CONTRACT.read_text()) == json.loads(json.dumps(app.openapi()))
