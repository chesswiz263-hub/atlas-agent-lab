"""Regression tests for expression-vs-instruction separation and checked IBP."""
import asyncio

import pytest

from atlas_math_v22 import interpret_math_query, solve_task, parse_safe
from atlas_conversation_v22 import ChatQuery, run_chat


@pytest.mark.parametrize('question,operation,expression', [
    ('Integrate x^2 * sin(x) and explain each step.', 'integrate', 'x^2 * sin(x)'),
    ('Integrate x^2 * sin(x). Show steps.', 'integrate', 'x^2 * sin(x)'),
    ('Integrate x^2 * sin(x), showing every step.', 'integrate', 'x^2 * sin(x)'),
    ('Integrate x^2 * sin(x) with respect to x and explain each step.', 'integrate', 'x^2 * sin(x)'),
    ('Integrate x^2 * sin(x) step-by-step', 'integrate', 'x^2 * sin(x)'),
    ('Differentiate x^3+2*x with respect to x and explain every step.', 'differentiate','x^3+2*x'),
    ('Factor x^2-9 and show your work.', 'factor','x^2-9'),
    ('Integrate x^2 from 0 to 1 and show each step.', 'definite_integral','x^2'),
    ('Limit of sin(x)/x as x -> 0 and explain each step.', 'limit','sin(x)/x'),
])
def test_explanatory_language_not_interpreted_as_math(question,operation,expression):
    task=interpret_math_query(question)
    assert task is not None
    assert task['operation']==operation
    assert task['expression']==expression
    result=solve_task(task)
    assert result['steps']


def test_verified_repeated_integration_by_parts():
    task=interpret_math_query('Integrate x^2 * sin(x) and explain each step.')
    result=solve_task(task)
    assert result['result']=='-x**2*cos(x) + 2*x*sin(x) + 2*cos(x) + C'
    assert result['verification']=='DIFFERENTIATION_CHECKED'
    explanations=[step['explanation'].lower() for step in result['steps']]
    assert sum('integration by parts' in text for text in explanations)>=2
    assert len(result['steps'])>=6
    import sympy as sp
    x=sp.Symbol('x')
    antiderivative=sp.integrate(x**2*sp.sin(x),x)
    assert sp.simplify(sp.diff(antiderivative,x)-x**2*sp.sin(x))==0


def test_math_chat_route_works_without_paid_model(monkeypatch):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    response=asyncio.run(run_chat(ChatQuery(question='Integrate x^2 * sin(x) and explain each step.')))
    assert response['answer_status'].startswith('FORMAL_MATH_')
    assert 'integration by parts' in response['answer'].lower()
    assert '2*cos(x)' in response['answer']
    assert response['model_usage']['calls']==0


def test_dangerous_expression_is_still_not_executable():
    task=interpret_math_query("Integrate __import__('os').system('whoami') and explain each step")
    assert task is not None
    with pytest.raises((ValueError,TypeError,SyntaxError)):
        parse_safe(task['expression'])
