"""Alert and dashboard expressions must name metrics the services really export."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ALERTS = yaml.safe_load((ROOT / 'monitoring' / 'alerts.yml').read_text())
DASHBOARD = json.loads((ROOT / 'monitoring' / 'grafana' / 'dashboards' / 'tayarishe.json').read_text())
BILLING_METRICS = (ROOT / 'services' / 'billing' / 'billing' / 'metrics.py').read_text()


def exported_billing_names() -> set[str]:
    names = set()
    for kind, name in re.findall(r"(Counter|Gauge)\('(billing_[a-z_]+)'", BILLING_METRICS):
        names.add(name + '_total' if kind == 'Counter' else name)
    return names


def billing_names_in(expression: str) -> set[str]:
    return set(re.findall(r'\bbilling_[a-z_]+', expression))


def test_every_billing_alert_names_an_exported_metric():
    exported = exported_billing_names()
    rules = [r for g in ALERTS['groups'] if g['name'] == 'billing' for r in g['rules']]
    assert len(rules) >= 6
    for rule in rules:
        used = billing_names_in(rule['expr'])
        assert used <= exported or not used, (rule['alert'], used - exported)
        assert 'summary' in rule['annotations']


def test_dashboard_billing_panels_use_exported_metrics_only():
    exported = exported_billing_names()
    panels = [p for p in DASHBOARD['panels'] if p['title'].startswith('Billing')]
    assert len(panels) >= 5
    for panel in panels:
        for target in panel['targets']:
            assert billing_names_in(target['expr']) <= exported, (panel['title'], target['expr'])


def test_prometheus_scrapes_billing():
    config = yaml.safe_load((ROOT / 'monitoring' / 'prometheus.yml').read_text())
    assert 'billing:8100' in [t for j in config['scrape_configs'] if j['job_name'] == 'billing' for s in j['static_configs'] for t in s['targets']]
