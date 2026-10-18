"""Network-free v1.5 workflow + citations/provenance adversarial checks."""
import hashlib
import json
import re
import sys
from types import ModuleType, SimpleNamespace

import pytest
from pydantic import ValidationError

from atlas.science_workflow import (
    ResearchWorkflowRequest, _auto_symbolic, _interpret_with_provider,
    _source_index, plan_research, run_scientific_workflow,
)


def request(**kwargs):
    return ResearchWorkflowRequest(question='Compare experimental galaxy rotation data for dark matter', **kwargs)


def mocked_primary():
    excerpt = 'Galaxy rotation curves have been measured in several large samples.'
    sha = hashlib.sha256(excerpt.encode()).hexdigest()
    return {'status':'RESULTS_FOUND','primary_fulltext_count':1,
            'papers':[{'id':1,'title':'Rotation curves in disk galaxies',
                'doi':'10.1234/example.1','doi_url':'https://doi.org/10.1234/example.1',
                'verification':{'status':'CROSSREF_METADATA_MATCH'},
                'primary_source':{'status':'REPOSITORY_FULLTEXT_MATCHED',
                  'source_url':'https://europepmc.org/articles/PMC1234','document_sha256':'b'*64},
                'primary_passages':[{'citation_id':'P1.1','excerpt':excerpt,'excerpt_sha256':sha,
                  'status':'EXACT_SOURCE_EXCERPT','section':'Results','paragraph':2}]}],
            'theory_comparison_v13':{'status':'NO_STRUCTURED_THEORIES','theories':[], 'evidence':[]}}


@pytest.mark.parametrize('field,val', [
    ('literature','everything'),('arxiv','sometimes'),('provider','secret_provider'),
    ('max_papers',4),('arxiv_limit',4),('max_primary_papers',3),
    ('model','bad model name'),('theories',[{'name':'X','predictions':[]}]),
    ('unknown','true'),
])
def test_request_rejects_invalid_budget_and_extra_fields(field,val):
    with pytest.raises(ValidationError):
        request(**{field:val})


def test_rejects_theory_comparison_with_literature_disabled():
    with pytest.raises(ValidationError):
        ResearchWorkflowRequest(question='Compare material models',literature='off', theories=[
            {'name':'Theory A','predictions':[{'observable':'amplitude'}]}])


def test_automatic_math_is_deliberately_narrow():
    tasks, why = _auto_symbolic('Differentiate x**2 + 3*x')
    assert why == 'EXPLICIT_EXPRESSION_PARSED'
    assert tasks[0].operation == 'differentiate'
    assert tasks[0].expression == 'x**2 + 3*x'
    for question in ['What is the derivative of this equation?',
                     'Does dark matter explain gravitational lensing?',
                     'simplify __import__("os")',
                     'Integrate 2**1000',
                     'solve x**2=9']:
        tasks, _ = _auto_symbolic(question)
        assert tasks == []


def test_math_only_skips_all_network_calls():
    req = ResearchWorkflowRequest(question='Differentiate x**2 + 3*x')
    plan, math_tasks = plan_research(req)
    assert [s['tool'] for s in plan['steps']] == ['formal_calculations','report']
    assert plan['max_external_requests_estimate'] == 0
    assert len(math_tasks) == 1


def test_arxiv_is_optional_not_forced_on_all_questions():
    plan,_ = plan_research(ResearchWorkflowRequest(question='How do enzyme reactions compare?'))
    assert [x['tool'] for x in plan['steps']] == ['literature_and_theory','report']
    plan,_ = plan_research(request())
    assert [x['tool'] for x in plan['steps']] == ['literature_and_theory','arxiv_metadata','report']


def test_budgets_are_fixed_even_with_optional_tools():
    plan,_ = plan_research(request(literature='on',arxiv='on',symbolic_tasks=[
        {'operation':'differentiate','expression':'x**2'}]))
    assert len(plan['steps']) == 4
    assert plan['max_external_requests_estimate'] == 1 + 3 + 2*2 + 1


def test_source_ledger_requires_real_hashes_and_exact_anchored_labels():
    source = mocked_primary()
    indexed = _source_index(source)
    assert len(indexed) == 1
    assert indexed[0]['citation_id'] == 'P1.1'
    assert indexed[0]['verification'] == 'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED'
    source['papers'][0]['primary_passages'][0]['excerpt_sha256'] = '0'*64
    assert not _source_index(source)
    source['papers'][0]['primary_passages'][0]['excerpt_sha256'] = hashlib.sha256(
        source['papers'][0]['primary_passages'][0]['excerpt'].encode()).hexdigest()
    source['papers'][0]['primary_passages'][0]['citation_id'] = 'P2.1'
    assert not _source_index(source)
    source['papers'][0]['primary_passages'][0]['citation_id'] = 'P1.1'
    source['papers'][0]['verification']['status'] = 'UNCHECKED'
    assert not _source_index(source)


@pytest.mark.asyncio
async def test_math_only_workflow_is_reproducible_and_offline():
    req = ResearchWorkflowRequest(question='Differentiate x**2 + 3*x')
    async def no_network(*args,**kwargs):
        raise AssertionError('Math-only workflow must not request literature')
    out1 = await run_scientific_workflow(req,literature_runner=no_network,arxiv_runner=no_network)
    out2 = await run_scientific_workflow(req,literature_runner=no_network,arxiv_runner=no_network)
    assert out1 == out2
    assert out1['literature']['status'] == 'NOT_REQUESTED'
    assert out1['calculations']['symbolic_checks'][0]['result'] == '2*x + 3'
    assert out1['report_sha256'] == out2['report_sha256']
    assert len(out1['report_sha256']) == 64


@pytest.mark.asyncio
async def test_discovers_sources_but_does_not_claim_scientific_verdict():
    async def literature(req,client=None):
        assert req.provider == 'demo'
        assert req.interpret_theories is False
        assert req.max_primary_papers == 2
        return mocked_primary()
    async def arxiv(question,limit,client=None):
        return {'status':'RESULTS_FOUND','papers':[{'title':'arXiv candidate'}],
                'verification':'REPOSITORY_METADATA_NOT_FULLTEXT_VERIFIED'}
    out = await run_scientific_workflow(request(),literature_runner=literature,arxiv_runner=arxiv)
    assert len(out['source_index']) == 1
    assert out['model_interpretation']['status'] == 'NOT_REQUESTED'
    assert out['answer_status'] == 'DETERMINISTIC_REPORT_NOT_SCIENTIFIC_VERDICT'
    assert out['arxiv_discovery']['verification'] == 'REPOSITORY_METADATA_NOT_FULLTEXT_VERIFIED'
    assert 'not verified' in out['answer'].lower()
    assert all('tool' in t and 'status' in t for t in out['execution_trace'])


@pytest.mark.asyncio
async def test_abstains_when_publication_is_not_available():
    async def literature(req, client=None):
        return {'status':'DISCOVERY_UNAVAILABLE','papers':[], 'primary_fulltext_count':0}
    out = await run_scientific_workflow(request(arxiv='off'),literature_runner=literature)
    assert not out['source_index']
    assert out['literature']['status'] == 'DISCOVERY_UNAVAILABLE'
    assert 'No independently crosschecked' in out['answer']


@pytest.mark.asyncio
async def test_failed_discovery_does_not_leak_credentials():
    async def fail(req,client=None):
        raise RuntimeError('API_SECRET=abc123')
    out = await run_scientific_workflow(request(arxiv='off'), literature_runner=fail)
    assert out['literature']['status'] == 'LITERATURE_UNAVAILABLE'
    assert 'abc123' not in json.dumps(out)


@pytest.mark.asyncio
async def test_math_results_are_separate_from_papers():
    req = ResearchWorkflowRequest(question='Engineering dimensions',literature='off', arxiv='off',
        dimensional_tasks=[{'expression':'F=m*a','variable_units':{'F':'N','m':'kg','a':'m/s**2'}}],
        numerical_tasks=[{'kind':'kinetic_energy','inputs':{'mass_kg':2,'velocity_m_s':3}}])
    out = await run_scientific_workflow(req)
    assert out['calculations']['dimensional_checks'][0]['status'] == 'DIMENSIONALLY_CONSISTENT'
    assert out['calculations']['numerical_runs'][0]['output']['energy_joules'] == 9
    assert out['source_index'] == []


def fake_provider(monkeypatch, response):
    config = ModuleType('atlas.config')
    config.DEFAULT_MODELS = {'openai': 'model-for-testing'}
    module = ModuleType('atlas.providers')
    class ProviderError(Exception):
        pass
    class Provider:
        def __init__(self, provider): self.provider = provider
        async def complete(self, messages, tools, model):
            assert not tools
            assert 'P1.1' in messages[1]['content']
            return SimpleNamespace(content=json.dumps(response))
    module.NativeProvider = Provider
    module.ProviderError = ProviderError
    monkeypatch.setitem(sys.modules, 'atlas.config', config)
    monkeypatch.setitem(sys.modules, 'atlas.providers', module)


@pytest.mark.asyncio
@pytest.mark.parametrize('text,ids', [
    ('A dubious conclusion [P9.1]', ['P9.1']),
    ('A dubious conclusion [P1.1]', ['P9.1']),
    ('A dubious conclusion without source', ['P1.1']),
    ('A guessed DOI 10.1234/fake [P1.1]', ['P1.1']),
])
async def test_provider_rejects_fabricated_or_noncompliant_citations(monkeypatch,text,ids):
    fake_provider(monkeypatch, {'summary':text,'cited_ids':ids})
    source = _source_index(mocked_primary())
    resp = await _interpret_with_provider(request(provider='openai'), source, [])
    assert resp['status'] == 'MODEL_REJECTED_OR_PROVIDER_UNAVAILABLE'
    assert resp['summary'] is None


@pytest.mark.asyncio
async def test_provider_accepts_valid_source_locator_not_entailment(monkeypatch):
    fake_provider(monkeypatch, {'summary':'The excerpt reports measured curves [P1.1]. This does not establish the underlying theory.', 'cited_ids':['P1.1']})
    resp = await _interpret_with_provider(request(provider='openai'), _source_index(mocked_primary()), [])
    assert resp['status'] == 'MODEL_INTERPRETATION_LOCATORS_CHECKED_NOT_ENTAILMENT'
    assert resp['cited_ids'] == ['P1.1']


@pytest.mark.asyncio
async def test_provider_abstains_with_no_primary_text_even_when_enabled():
    resp = await _interpret_with_provider(request(provider='openai'), [], [])
    assert resp['status'] == 'ABSTAINED_NO_PRIMARY_TEXT'


@pytest.mark.asyncio
async def test_unexpected_synthesis_exception_falls_back_to_deterministic():
    async def bad(req,sources,checks): raise RuntimeError('provider-supplied secret')
    out = await run_scientific_workflow(ResearchWorkflowRequest(question='Differentiate x**2'),synthesis_runner=bad)
    assert 'provider-supplied secret' not in json.dumps(out)
    assert out['answer_status'] == 'DETERMINISTIC_REPORT_NOT_SCIENTIFIC_VERDICT'
