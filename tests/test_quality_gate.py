from scripts.quality_gate import run, evidence


def test_versioned_golden_contract():
    report = run()
    assert report['passed'] and report['dataset_version'] == '1.0'
    assert report['mode'] == 'offline-contract'
    assert report['prompt_version'] == 'study-v1'
    assert len(report['prompt_sha256']) == 64


def test_bad_citations_and_hallucinations_fail():
    case = dict(source='science.txt', terms=['6'], forbidden=['6 joules'])
    assert evidence(case, '6 joules (madeup.txt)', ['science.txt']) == dict(citation=False, grounded=False)
    assert evidence(case, '6 N (science.txt)', ['science.txt']) == dict(citation=True, grounded=True)
