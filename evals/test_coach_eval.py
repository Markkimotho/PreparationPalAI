"""Optional GLM/DeepSeek grading checks against fixed scientific reference answers.

COACH_EVAL_MODELS='glm4:9b,deepseek-r1:7b' pytest evals/test_coach_eval.py -m eval -v
No models are downloaded. Each case can take several minutes on CPU.
"""
import os

import pytest

from app.analysis import get_installed_models
from app.quiz import validate_answer

pytestmark = pytest.mark.eval
MODELS = os.environ.get('COACH_EVAL_MODELS', 'glm4:9b,deepseek-r1:7b').split(',')
CASES = [
    ('A 2 kg mass accelerates at 3 m/s². Find the net force.',
     'F = ma = 2 × 3 = 6 N.', 'The net force is 6 N by Newton’s second law.',
     'The net force is 1.5 joules because force is mass divided by acceleration.'),
    ('How many moles of water form from 2 moles H₂ and excess O₂?',
     '2H₂ + O₂ → 2H₂O, so 2 moles of water form.',
     'The H₂:H₂O molar ratio is 1:1, giving 2 mol water.',
     'Four moles form because the number of hydrogen atoms doubles.'),
    ('For Hardy–Weinberg equilibrium with q=0.2, what fraction is heterozygous?',
     'p=0.8 and 2pq=0.32, so 32%.',
     'p=1−q=0.8; heterozygote frequency 2pq is 0.32.',
     'The heterozygote frequency is q squared, 0.04.'),
    ('For independent measurements with variance 9, what is the variance of the mean of 9 measurements?',
     'Variance of sample mean is sigma squared / n = 9/9 = 1.',
     'Independence gives Var(mean)=9 divided by 9, or 1.',
     'The variance is 81 because variances multiply with sample size.'),
]


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('question,reference,correct,incorrect', CASES)
def test_scientific_rubric_discriminates_answers(model, question, reference, correct, incorrect):
    if model not in get_installed_models():
        pytest.skip(f'{model} is not installed')
    good = validate_answer(question, reference, correct, model=model)
    bad = validate_answer(question, reference, incorrect, model=model)
    assert good['score'] >= 70, good
    assert bad['score'] < 70, bad
    assert good['feedback'] and bad['feedback']
