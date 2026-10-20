"""ATLAS 2.3.1: prose never becomes executable mathematics."""
from __future__ import annotations
import asyncio
import pytest

from atlas_conversation_v22 import ChatQuery
from atlas_conversation_v23 import interpret_math_query_v231, run_chat_v23
from atlas_math_v23 import parse_safe


@pytest.mark.parametrize('question,operation,expression', [
    ('Integrate x^2 * sin(x) and explain why integration by parts is necessary.', 'integrate','x^2 * sin(x)'),
    ('Integrate x^2*sin(x) and explain how integration by parts works.', 'integrate','x^2*sin(x)'),
    ('Integrate x^2*sin(x), and explain why we apply integration by parts twice!', 'integrate','x^2*sin(x)'),
    ('Integrate x^2*sin(x); describe why this technique is appropriate', 'integrate','x^2*sin(x)'),
    ('Integrate x^2*sin(x), explain the intuition behind the method', 'integrate','x^2*sin(x)'),
    ('Integrate x^2*sin(x) and discuss how the polynomial degree decreases.', 'integrate','x^2*sin(x)'),
    ('Differentiate x^3+2*x and explain why the power rule is used.', 'differentiate','x^3+2*x'),
    ('Integrate x^2 from 0 to 1 and explain why the bounds matter.', 'definite_integral','x^2'),
    ('Limit of sin(x)/x as x -> 0 and explain why it approaches one', 'limit','sin(x)/x'),
    ('Integrate x^2*sin(x) and explain why repeated integration by parts is necessary and show each step.', 'integrate','x^2*sin(x)'),
    ('Integrate x^2*sin(x) and explain each step', 'integrate','x^2*sin(x)'),
    ('Differentiate x^2 with respect to y and explain how the derivative is computed', 'differentiate','x^2'),
])
def test_trailing_teaching_request_is_separate(question, operation, expression):
    task=interpret_math_query_v231(question)
    assert task is not None
    assert task['operation']==operation
    assert task['expression']==expression
    assert parse_safe(expression) is not None


def test_original_hosted_math_question_passes_without_model(monkeypatch):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    q='Integrate x^2 * sin(x) and explain why integration by parts is necessary.'
    response=asyncio.run(run_chat_v23(ChatQuery(question=q,workspace='math')))
    assert response['answer_status']=='FORMAL_MATH_CHECKED'
    assert response['math']['verification']=='DIFFERENTIATION_CHECKED'
    assert response['math']['result']=='-x**2*cos(x) + 2*x*sin(x) + 2*cos(x) + C'
    assert '2 → 1 → 0' in response['presentation']['why']
    assert '<msup>' in response['presentation']['result_mathml']
    assert response['model_usage']['calls']==0


@pytest.mark.parametrize('untrusted',[
    "__import__('os').system('whoami')",
    "open('/etc/passwd')",
    '(lambda x:x)(2)',
    'x.__class__',
    '2**100000',
])
def test_untrusted_math_is_never_accepted(untrusted,monkeypatch):
    q='Integrate '+untrusted+' and explain why this method is appropriate.'
    task=interpret_math_query_v231(q)
    assert task is not None
    assert task['expression']==untrusted
    with pytest.raises((ValueError,SyntaxError,TypeError)):
        parse_safe(task['expression'])
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    result=asyncio.run(run_chat_v23(ChatQuery(question=q,workspace='math')))
    assert result['answer_status']=='MATH_NOT_CHECKED'


def test_unrecognized_trailing_wording_not_silently_discarded(monkeypatch):
    q='Integrate x^2*sin(x) and publish my private notes'
    task=interpret_math_query_v231(q)
    assert task is not None
    assert 'publish my private notes' in task['expression']
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    result=asyncio.run(run_chat_v23(ChatQuery(question=q,workspace='math')))
    assert result['answer_status']=='MATH_NOT_CHECKED'


def test_science_validator_and_quota_adapter_intact():
    import atlas_conversation_v23 as v23
    assert v23.base._valid_model_science is v23._validated_science_sentences
    assert v23.base._math_subprocess is v23._math_subprocess_v23


def test_legacy_parser_remains_unchanged():
    from atlas_math_v22 import interpret_math_query as original
    before=original('Integrate x^2 * sin(x) and explain why integration by parts is necessary.')
    # Confirm this hotfix doesn't modify the old standalone v2.2 contract;
    # only the hosted v2.3 router recognizes additional explanations.
    assert before['expression'].endswith('why integration by parts is necessary')
