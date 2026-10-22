"""Offline v2.4 tests: no real API credentials, network or model charges."""
import asyncio
import json
from pathlib import Path
import sys
import types

import pytest
import atlas_conversation_v22 as core
import atlas_conversation_v23 as v23
import atlas_conversation_v24 as v24


def src(cid='B.P1.1', excerpt='CRISPR Cas9 genome editing uses guide RNA to target a genomic sequence in a cell.'):
    return {'citation_id': cid, 'excerpt': excerpt, 'doi': '10.1234/test',
            'title': 'Guide RNA source text',
            'verification': 'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED'}


def test_config_never_echoes_credentials(monkeypatch,tmp_path):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','1')
    monkeypatch.setenv('OPENAI_API_KEY','SECRET_NEVER_PRINT')
    monkeypatch.setenv('ATLAS_LLM_MODEL','gpt-4o-mini')
    monkeypatch.setenv('ATLAS_LLM_INPUT_USD_PER_1M','0.15')
    monkeypatch.setenv('ATLAS_LLM_OUTPUT_USD_PER_1M','0.60')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY','0.25')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL','0.025')
    monkeypatch.setenv('ATLAS_LLM_MAX_CALLS_PER_DAY','30')
    monkeypatch.setenv('ATLAS_LLM_BUDGET_DB', str(tmp_path/'quota.sqlite'))
    status=v24.model_configuration()
    assert status=={'enabled':True,'status':'READY_TO_ATTEMPT'}
    assert 'SECRET_NEVER_PRINT' not in repr(status)
    monkeypatch.delenv('ATLAS_LLM_BUDGET_DB')
    assert v24.model_configuration()['enabled'] is False
    monkeypatch.setenv('ATLAS_LLM_BUDGET_DB','relative/quota.sqlite')
    assert v24.model_configuration()['enabled'] is False


@pytest.mark.parametrize('bad', [
    'Researchers reported a 99 percent treatment effect. [B.P1.1]',
    'The observations are discussed in depth. [B.P9.9]',
    'This is an example with a reference in the middle [B.P1.1] and unsupported text.',
    'Studies describe gene editing in a cell.',
    'The source describes editing. [B.P1.1] More evidence exists.',
    '<script>alert(1)</script> Researchers observed gene editing. [B.P1.1]',
    'Researchers found a new method [B.P1.1] [INVENTED-REF].',
])
def test_model_output_abstains_on_invalid_claims(bad):
    assert not v24.validate_science_synthesis(bad,[src()])


def test_source_attributed_conversational_answer_accepted():
    text='The located source discusses CRISPR Cas9 guide RNA and genome editing in cells. [B.P1.1]'
    assert v24.validate_science_synthesis(text,[src()])
    assert v24.validate_science_synthesis('The source states 42 participants were observed. [B.P1.2]',
               [src('B.P1.2','The source states 42 participants were observed in a trial.')])


def test_math_keeps_sympy_authority(monkeypatch):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    r=asyncio.run(v24.run_chat_v24(core.ChatQuery(
        question='Integrate x^2 * sin(x) and explain why integration by parts is necessary.',workspace='math')))
    assert r['math']['result'].startswith('-x**2*cos(x)')
    assert r['presentation']['kind']=='mathematics'
    assert 'x^{2}' in r['presentation']['result_latex']
    assert r['synthesis_status']=='MATH_SYMPY_AUTHORITY'
    assert r['model_usage']['calls']==0


def test_research_model_invocation_and_citation_guard(monkeypatch):
    fake_science = types.ModuleType('atlas.science_decomposition')
    observed=[]
    class FakeReq:
        def __init__(self,**kwargs):observed.append(kwargs)
    async def fake_engine(_req):
        return {'citation_ledger':[src()], 'foundation':{'literature':{'papers':[]}, 'calculations':{'summaries':[]}}}
    fake_science.DecomposedResearchRequest=FakeReq
    fake_science.run_decomposed_research=fake_engine
    monkeypatch.setitem(sys.modules,'atlas.science_decomposition',fake_science)
    monkeypatch.setenv('ATLAS_LLM_ENABLED','1')
    fake_text={'text':'The located source discusses CRISPR Cas9 guide RNA and genome editing in cells. [B.P1.1]',
               'reservation':'fake', 'provider':'openai','model':'test-model', 'usage':{'input_tokens':100,'output_tokens':40},'estimated_cost_usd':.0005}
    invoked=[]
    monkeypatch.setattr(core,'_invoke_model',lambda *args,**kwargs:(invoked.append(args),fake_text)[1])
    response=asyncio.run(v24.run_chat_v24(core.ChatQuery(question='How does CRISPR Cas9 guide RNA affect genome editing?')))
    assert observed and observed[0]['provider']=='demo'
    assert invoked and 'only' in invoked[0][0].lower()
    assert response['answer_status']=='MODEL_SYNTHESIS_LOCATORS_VALIDATED_NOT_ENTAILMENT'
    assert response['synthesis_status'].startswith('SOURCE_LINKED')
    assert response['presentation']['source_count']==1
    monkeypatch.setattr(core,'_invoke_model',lambda *args,**kwargs:{**fake_text,'text':'A 99 percent success rate was achieved. [B.P1.1]'})
    rejected=asyncio.run(v24.run_chat_v24(core.ChatQuery(question='How does CRISPR Cas9 guide RNA affect genome editing?')))
    assert rejected['answer_status']=='EVIDENCE_SUMMARY_ABSTENTION'
    assert '99 percent' not in rejected['answer']


def test_research_no_sources_no_paid_call(monkeypatch):
    fake_science=types.ModuleType('atlas.science_decomposition')
    class FakeReq:
        def __init__(self,**kwargs):pass
    async def fake_engine(_req):
        return {'citation_ledger':[], 'foundation':{'literature':{'papers':[]},'calculations':{'summaries':[]}}}
    fake_science.DecomposedResearchRequest=FakeReq
    fake_science.run_decomposed_research=fake_engine
    monkeypatch.setitem(sys.modules,'atlas.science_decomposition',fake_science)
    monkeypatch.setenv('ATLAS_LLM_ENABLED','1')
    monkeypatch.setattr(core,'_invoke_model', lambda *a,**kw:(_ for _ in ()).throw(AssertionError('No source, no model call')))
    output=asyncio.run(v24.run_chat_v24(core.ChatQuery(question='What does a new physics paper establish?')))
    assert output['citation_ledger']==[]
    assert output['model_usage']['calls']==0
    assert output['synthesis_status']=='RESEARCH_FALLBACK_OR_ABSTENTION'


def test_base_quota_reserves_before_provider(monkeypatch,tmp_path):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','1')
    monkeypatch.setenv('OPENAI_API_KEY','fake-key-for-test')
    monkeypatch.setenv('ATLAS_LLM_MODEL','gpt-4o-mini')
    monkeypatch.setenv('ATLAS_LLM_INPUT_USD_PER_1M','0.15')
    monkeypatch.setenv('ATLAS_LLM_OUTPUT_USD_PER_1M','0.60')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL','0.025')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY','0.001')
    monkeypatch.setenv('ATLAS_LLM_MAX_CALLS_PER_DAY','1')
    monkeypatch.setenv('ATLAS_LLM_BUDGET_DB',str(tmp_path/'model-budget.db'))
    class FakeResponse:
        output_text='A valid explanatory answer. [B.P1.1]'
        usage=types.SimpleNamespace(input_tokens=100,output_tokens=50)
    counter=[]
    class FakeClient:
        def __init__(self,**kwargs):pass
        class responses:
            @staticmethod
            def create(**kwargs):counter.append(kwargs);return FakeResponse()
    monkeypatch.setitem(sys.modules,'openai',types.SimpleNamespace(OpenAI=FakeClient))
    first=core._invoke_model('source boundaries',{'excerpt':'testing'},max_output_tokens=90)
    assert first['reservation'] and len(counter)==1
    with pytest.raises(core.BudgetExceeded):
        core._invoke_model('source boundaries',{'excerpt':'testing'},max_output_tokens=90)
    assert len(counter)==1
    assert counter[0]['store'] is False


def test_gateway_and_ui_are_versioned():
    root=Path(__file__).resolve().parents[1]
    if not (root/'atlas_hosted_beta_v24.reference.py').exists():return
    gateway=(root/'atlas_hosted_beta_v24.reference.py').read_text()
    assert 'run_chat_v24 as run_chat' in gateway
    assert 'csrf_for(token)' in gateway
    assert 'atlas-chat-v24.html' in gateway
    js=(root/'v24_assets/atlas-chat-v24.js').read_text()
    assert 'atlas-source-' in js
    assert 'textContent' in js


def test_incomplete_configuration_blocks_provider_call_before_network(monkeypatch):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','1')
    monkeypatch.setenv('OPENAI_API_KEY','fake-test-key')
    monkeypatch.setenv('ATLAS_LLM_MODEL','gpt-4o-mini')
    monkeypatch.setenv('ATLAS_LLM_INPUT_USD_PER_1M','0.15')
    monkeypatch.setenv('ATLAS_LLM_OUTPUT_USD_PER_1M','0.60')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY','0.10')
    monkeypatch.setenv('ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL','0.01')
    monkeypatch.setenv('ATLAS_LLM_MAX_CALLS_PER_DAY','20')
    monkeypatch.delenv('ATLAS_LLM_BUDGET_DB',raising=False)
    with pytest.raises(core.BudgetExceeded,match='configuration'):
        core._invoke_model('system instructions',{'question':'test'},max_output_tokens=50)
