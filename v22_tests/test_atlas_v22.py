"""Offline regression: no paid provider or live literature required."""
import os
from pathlib import Path
import pytest
from atlas_math_v22 import parse_safe, interpret_math_query, solve_task
from atlas_conversation_v22 import _math_subprocess, _valid_model_science, rank_passages, ModelQuota, BudgetExceeded


@pytest.mark.parametrize('prompt,expected',[
    ('calculate 3+4*2','11'),
    ('solve x^2-4=0','{-2, 2}'),
    ('differentiate x^3+2*x with respect to x','3*x**2 + 2'),
    ('integrate 3*x^2+2*x+1','x**3 + x**2 + x + C'),
    ('integrate x^2 from 0 to 1','1/3'),
    ('limit of sin(x)/x as x -> 0','1'),
    ('gradient of x^2+y^2+z^2','Matrix([[2*x], [2*y], [2*z]])'),
    ('solve ode y\'\' + y=0','Eq(y(x), C1*sin(x) + C2*cos(x))'),
    ('laplace transform of sin(t)','1/(s**2 + 1)'),
])
def test_math_conversational_questions(prompt,expected):
    task=interpret_math_query(prompt)
    assert task is not None
    solved=_math_subprocess(task)
    assert solved['result']==expected
    assert solved['steps'] and solved['verification']


def test_multiple_integrals_vector_calculus_series_systems():
    assert solve_task({'operation':'double_integral','expression':'x+y',
        'bounds':[['x','0','1'],['y','0','2']]})['result']=='3'
    assert solve_task({'operation':'triple_integral','expression':'x*y*z',
        'bounds':[['x','0','1'],['y','0','1'],['z','0','1']]})['result']=='1/8'
    assert solve_task({'operation':'curl','expression':'[y, z, x]'})['result']=='Matrix([[-1], [-1], [-1]])'
    assert 'x**3/6' in solve_task({'operation':'series','expression':'sin(x)','order':6})['result']
    assert solve_task({'operation':'sum','expression':'1/n**2','bounds':[['n','1','oo']]})['result']=='pi**2/6'
    assert solve_task({'operation':'system','expression':'x+y=4; x-y=2'})['verification']=='SUBSTITUTION_CHECKED'


@pytest.mark.parametrize('attack',[
    "__import__('os').system('echo hi')",'(lambda x:x)(2)','foo.bar(3)',
    '2**100000','sin(x, y)','[x for x in range(100)]','x.__class__',
    "open('/etc/passwd')",'x**x**x',
])
def test_no_untrusted_execution(attack):
    with pytest.raises((ValueError,SyntaxError,TypeError)):
        parse_safe(attack)


def test_relevance_diversity_and_abstention():
    source=lambda cid,exc: {'citation_id':cid,'excerpt':exc,'doi':'10.1111/abc','verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED','document_sha256':'0123'}
    records=[source('B.P1.1','Genome editing using CRISPR Cas9 depends on guide RNA binding to a targeted genomic sequence.'),
             source('B.P1.2','This passage concerns gravitational waves and has no connection to the requested topic.'),
             source('B.P1.3','Genome editing using CRISPR Cas9 is examined in cultured cells with an RNA guide.')]
    ranked=rank_passages('CRISPR Cas9 genome editing with RNA guides',records)
    assert ranked and len(ranked)==2
    assert {r['citation_id'] for r in ranked}=={'B.P1.1','B.P1.3'}
    assert not rank_passages('superconductivity',records)


def test_citation_registry_rejects_model_invention():
    selected=[{'citation_id':'B.P1.1','excerpt':'Genome editing research uses CRISPR proteins and guide RNA.'}]
    assert _valid_model_science('The retrieved text discusses CRISPR genome editing and guide RNA. [B.P1.1]',selected)
    assert not _valid_model_science('Some study proves all diseases are cured. [B.P1.9]',selected)
    assert not _valid_model_science('Study proves all diseases cured, with no citation.',selected)


def test_sqlite_pre_call_quotas(monkeypatch,tmp_path):
    monkeypatch.setenv('ATLAS_LLM_BUDGET_DB',str(tmp_path/'budget.db'))
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY','0.03')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL','0.02')
    monkeypatch.setenv('ATLAS_LLM_MAX_CALLS_PER_DAY','2')
    budget=ModelQuota()
    assert budget.reserve(.01)
    assert budget.reserve(.01)
    with pytest.raises(BudgetExceeded):budget.reserve(.01)
    with pytest.raises(BudgetExceeded):budget.reserve(.03)


def test_conversation_uses_science_engine_before_model_and_validates_ids(monkeypatch):
    import asyncio, sys, types
    import atlas_conversation_v22 as conv
    fake_atlas=types.ModuleType('atlas'); fake_science=types.ModuleType('atlas.science_decomposition')
    seen=[]
    class FakeResearchReq:
        def __init__(self,**kwargs):
            seen.append(kwargs)
    async def fake_research(req):
        return {'citation_ledger':[{'citation_id':'B.P1.1','excerpt':'CRISPR Cas9 uses guide RNA to direct genome editing to target sequences.','doi':'10.1234/test','title':'Genome editing evidence','verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED'}],
                'foundation':{'literature':{'papers':[]},'calculations':{'summaries':[]}}, 'answer':'Raw report'}
    fake_science.DecomposedResearchRequest=FakeResearchReq
    fake_science.run_decomposed_research=fake_research
    monkeypatch.setitem(sys.modules,'atlas',fake_atlas)
    monkeypatch.setitem(sys.modules,'atlas.science_decomposition',fake_science)
    monkeypatch.setattr(conv,'_model_enabled',lambda:True)
    monkeypatch.setattr(conv,'_invoke_model',lambda *args,**kwargs:{'text':'The excerpts describe CRISPR guide RNA targeting in genome editing. [B.P1.1]','reservation':'fake','provider':'openai','model':'test-model','estimated_cost_usd':.001,'usage':{}})
    response=asyncio.run(conv.run_chat(conv.ChatQuery(question='How does CRISPR Cas9 guide RNA target genome editing?')))
    assert seen and seen[0]['provider']=='demo'
    assert response['answer_status']=='MODEL_SYNTHESIS_LOCATORS_VALIDATED_NOT_ENTAILMENT'
    assert response['model_usage']['calls']==1
    monkeypatch.setattr(conv,'_invoke_model',lambda *args,**kwargs:{'text':'Made-up statistics from unknown studies [B.P9.9]','reservation':'fake','provider':'openai','model':'test-model','estimated_cost_usd':.001,'usage':{}})
    refused=asyncio.run(conv.run_chat(conv.ChatQuery(question='How does CRISPR Cas9 guide RNA target genome editing?')))
    assert refused['answer_status']=='EVIDENCE_SUMMARY_ABSTENTION'
    assert 'B.P9.9' not in refused['answer']
