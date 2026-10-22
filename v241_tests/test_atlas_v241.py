"""Regression tests for the failures reported from the hosted v2.4 system."""
from __future__ import annotations
import asyncio
import pytest

from atlas_conversation_v22 import ChatQuery
from atlas_conversation_v241 import (
    _extended_task,_rewrite_indefinite_integral,_extended_subprocess,
    _discovery_diagnostics,run_chat_v241,
)


def run(question:str):
    return asyncio.run(run_chat_v241(ChatQuery(question=question,workspace='math')))


def test_long_tutor_math_prompt():
    prompt=('Evaluate the indefinite integral of x^3 * e^x. Explain why integration by parts is appropriate, '
            'show every application of the method, explain why the polynomial degree decreases, '
            'and verify the antiderivative by differentiation.')
    assert _rewrite_indefinite_integral(prompt)=='Integrate x^3 * exp(x)'
    result=run(prompt)
    assert result['answer_status']=='FORMAL_MATH_CHECKED'
    assert 'exp(x)' in result['math']['result']
    assert result['math']['verification']=='DIFFERENTIATION_CHECKED'
    assert result['presentation']['result_mathml']
    assert len(result['presentation']['steps'])>=2


def test_stationary_points_and_hessian():
    question=('Find and classify all stationary points of f(x,y)=x^3-3*x+y^2-4*y. '
              'Explain the gradient, solve for stationary points, apply the Hessian test, and verify the classification.')
    parsed=_extended_task(question)
    assert parsed['operation']=='stationary_points_2d'
    result=run(question)
    assert result['answer_status']=='FORMAL_MATH_CHECKED'
    assert result['math']['result']=='(-1, 2): saddle point; (1, 2): local minimum'
    assert 'local minimum' in result['presentation']['result_mathml']


def test_initial_value_ode():
    question=("Solve the differential equation y'' + 4*y = 0 subject to y(0)=2 and y'(0)=0. "
              'Explain the characteristic equation, how the initial conditions determine the constants, '
              'and verify the solution by substitution.')
    parsed=_extended_task(question)
    assert parsed['operation']=='ode_ivp_2nd'
    result=run(question)
    assert result['answer_status']=='FORMAL_MATH_CHECKED'
    assert result['math']['result']=='Eq(y(x), 2*cos(2*x))'
    assert 'INITIAL_CONDITIONS' in result['math']['verification']


@pytest.mark.parametrize('unsafe',["__import__('os').system('id')",'open(1)','x**100000',
    'x.__class__','foo.bar(1)'])
def test_rejects_unsafe_stationary_expressions(unsafe):
    task={'operation':'stationary_points_2d','expression':unsafe}
    with pytest.raises((ValueError,TypeError,SyntaxError)):
        _extended_subprocess(task)


@pytest.mark.parametrize('unsafe',["__import__('os').system('id')",'x'' + foo.bar(1) = 0',"y'' + x*y = 0"])
def test_rejects_unsafe_ivps(unsafe):
    with pytest.raises((ValueError,TypeError,SyntaxError)):
        _extended_subprocess({'operation':'ode_ivp_2nd','expression':unsafe,'initial_y':'2','initial_dy':'0'})


def test_research_status_reports_missing_fulltext_without_claims():
    example={'answer_status':'EVIDENCE_SUMMARY_ABSTENTION','foundation':{
        'literature':{'status':'NO_RESULTS','papers':[{'title':'Paper'}]},
        'arxiv_discovery':{'status':'RESULTS_FOUND','papers':[{'title':'Preprint'}]}},
        'decomposition':{'strategy':'NO_CONFIDENT_DECOMPOSITION'},
        'passage_selection':{'source_count':0,'topically_ranked_count':0},
        'citation_ledger':[], 'model_usage':{'calls':0}}
    report=_discovery_diagnostics(example)
    assert report['phase']=='NO_SOURCE_TEXT_LOCATED'
    assert report['publication_metadata_count']==1
    assert report['arxiv_metadata_status']=='RESULTS_FOUND'
    assert report['model_attempted'] is False


def test_source_text_ranking_gap_diagnostic():
    report=_discovery_diagnostics({'passage_selection':{'source_count':3,'topically_ranked_count':0}})
    assert report['phase']=='SOURCE_TEXT_NOT_TOPICALLY_SELECTED'


def test_gateway_contains_v241_router():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    assert 'from atlas_conversation_v241 import run_chat_v241 as run_chat' in (root/'atlas_hosted_beta_v241.reference.py').read_text(encoding='utf-8')
