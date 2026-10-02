from unittest.mock import Mock, patch
from app.quiz import validate_answer, _extract_json


def test_rubric_drives_total_and_pass_threshold():
    model = Mock()
    model.invoke.return_value.content = '{"score":100,"feedback":"Check units", "rubric":{"reasoning":20,"accuracy":10,"clarity":10}}'
    with patch('app.quiz._get_llm', return_value=model):
        result = validate_answer('Calculate force', '6 N', '6 J')
    assert result['score'] == 40
    assert not result['is_correct']
    assert result['rubric']['accuracy'] == 10


def test_reasoning_text_is_not_json_evidence():
    assert _extract_json('<think>[invented]</think> {"score": 80}') == {'score': 80}
