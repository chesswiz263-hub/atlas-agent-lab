"""v2.5 offline deterministic tests; no external network/API charges."""
import asyncio
import copy
import importlib
import json
from pathlib import Path
import re
import httpx
import pytest
from atlas_conversation_v22 import ChatQuery
import atlas_conversation_v25 as v25
import atlas_retrieval_v25 as r

ROOT=Path(__file__).resolve().parents[1]


def sample():
    work={'id':'https://openalex.org/W123','title':'Observations of galaxy rotation curves and dark matter',
          'doi':'https://doi.org/10.1234/example1',
          'locations':[{'landing_page_url':'https://arxiv.org/abs/2101.12345'}]}
    text=('Observations of galaxy rotation curves and dark matter demonstrate a discrepancy in the rotation '
          'curves of spiral galaxies under a chosen dynamical model. The observational signal is the velocity '
          'distribution as a function of distance. Interpreting that distribution requires assumptions about '
          'stellar mass and galaxy dynamics. ')*6
    html='<html><article><h1>'+work['title']+'</h1><p>'+text+'</p></article></html>'
    return work,html.encode('utf-8')


def fake_transport():
    work,raw=sample()
    def responder(req:httpx.Request):
        if req.url.host=='api.openalex.org':
            return httpx.Response(200,json={'results':[work]})
        if req.url.host=='arxiv.org' and req.url.path=='/html/2101.12345':
            return httpx.Response(200,headers={'content-type':'text/html'},content=raw)
        raise AssertionError('Unexpected network host/path '+str(req.url))
    return httpx.MockTransport(responder)


def test_anchored_decomposition():
    q='What evidence supports dark matter? Discuss galaxy rotation curves, the Bullet Cluster, and cosmic microwave background measurements.'
    plan=r.plan_questions(q)
    assert len(plan)==4 and any('Bullet Cluster' in p for p in plan)
    assert 'strongest' not in ' '.join(plan).lower()
    assert len(r.plan_questions('How do acoustic oscillations inform cosmology?')) <=4


def test_allowlisted_arxiv_and_metadata_not_evidence():
    good={'locations':[{'pdf_url':'https://arxiv.org/pdf/2101.12345v1'}]}
    assert r.arxiv_identifiers(good)==['2101.12345v1']
    evil={'locations':[{'pdf_url':'https://evil.example.com/pdf/2101.12345'},
                       {'pdf_url':'https://arxiv.org.evil.com/pdf/2101.12345'}]}
    assert r.arxiv_identifiers(evil)==[]
    assert r.normalize_doi('https://doi.org/10.1234/ab.c')=='10.1234/ab.c'


def test_bounded_source_retrieval_and_citations(monkeypatch):
    monkeypatch.setenv('ATLAS_V25_RETRIEVAL_ENABLED','1')
    async def run():
        async with httpx.AsyncClient(transport=fake_transport()) as client:
            return await r.gather('Explain dark matter observations from galaxy rotation curves.',client=client)
    result=asyncio.run(run())
    assert result['status']=='PASSAGES_LOCATED'
    assert result['diagnostics']['fulltext_retrieved']==1
    assert len(result['citation_ledger'])>=1
    assert all(x['verification']=='SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED' for x in result['citation_ledger'])
    assert result['citation_ledger'][0]['document_sha256']
    assert result['citation_ledger'][0]['source_url']=='https://arxiv.org/html/2101.12345'


def test_metadata_is_not_citable(monkeypatch):
    fake={'id':'https://openalex.org/W1','title':'Dark matter galaxy rotation curves',
          'locations':[{'landing_page_url':'https://example.org/not-arxiv'}]}
    def resp(req):return httpx.Response(200,json={'results':[fake]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(resp)) as client:
            return await r.gather('dark matter galaxy rotation curves',client=client)
    result=asyncio.run(run())
    assert result['citation_ledger']==[]
    assert result['status']=='NO_ARXIV_OPENALEX_CANDIDATES'


def test_reject_redirect_and_oversized_stream():
    def resp(req):
        if req.url.path.endswith('/redirect'):return httpx.Response(302,headers={'location':'https://evil.example/'})
        return httpx.Response(200,content=b'a'*1024)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(resp)) as client:
            with pytest.raises(ValueError,match='Redirect'):await r._bounded_get(client,'https://arxiv.org/redirect')
            with pytest.raises(ValueError,match='byte budget'):await r._bounded_get(client,'https://arxiv.org/big',limit=100)
    asyncio.run(run())


def test_false_characteristic_equation_fixed():
    task={'operation':'ode_ivp_2nd','expression':"y''+4*y=0",'initial_y':'2','initial_dy':'0'}
    answer=v25._solve_extended_v25(task)
    assert answer['status']=='CHECKED'
    characteristic=next(x for x in answer['steps'] if 'characteristic' in x['explanation'].lower())
    assert characteristic['expression']!='False'
    assert 'r' in characteristic['expression']
    assert '2*cos(2*x)' in answer['result']


def test_clear_hessian_explanation():
    answer=v25._solve_extended_v25({'operation':'stationary_points_2d','expression':'x^3-3*x+y^2-4*y'})
    view=v25._enhance_math_view(__import__('atlas_conversation_v23').math_presentation(answer),answer)
    assert any('holding the other' in x['explanation'] for x in view['steps'])
    assert 'local minimum' in answer['result'] and 'saddle' in answer['result']


def test_science_abstains_without_source(monkeypatch):
    monkeypatch.setenv('ATLAS_V25_LEGACY_FALLBACK','0')
    async def empty(_):return {'citation_ledger':[],'papers':[], 'status':'FULLTEXT_UNAVAILABLE',
       'diagnostics':{'fulltext_retrieved':0,'search_queries':['dark matter']}}
    monkeypatch.setattr(v25.retriever,'gather',empty)
    result=asyncio.run(v25.run_chat_v25(ChatQuery(question='What observational data establishes dark matter?')))
    assert result['answer_status']=='EVIDENCE_SUMMARY_ABSTENTION'
    assert result['model_usage']['calls']==0


def test_science_synthesis_only_cites_actual_passages(monkeypatch):
    record={'citation_id':'A.P1','excerpt':'Rotation curves of spiral galaxies showed a discrepancy in measured velocities and luminous matter models.',
            'title':'Dark matter rotation curve observations','doi':'10.1234/example','source_url':'https://arxiv.org/html/2101.12345',
            'verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED'}
    async def gathered(_):return {'citation_ledger':[record],'papers':[],'status':'PASSAGES_LOCATED',
                                    'diagnostics':{'fulltext_retrieved':1}}
    monkeypatch.setattr(v25.retriever,'gather',gathered)
    monkeypatch.setattr(v25.llm,'model_configuration',lambda:{'enabled':True,'status':'READY_TO_ATTEMPT'})
    monkeypatch.setattr(v25.core,'_invoke_model',lambda *a,**k:{'text':'The paper describes a discrepancy between observed galaxy rotation curves and luminous matter models. [A.P1]',
                                                               'reservation':'fixed-test-token','model':'mock'})
    result=asyncio.run(v25.run_chat_v25(ChatQuery(question='What is observational evidence for dark matter?')))
    assert result['answer_status']=='MODEL_SYNTHESIS_LOCATORS_VALIDATED_NOT_ENTAILMENT'
    assert result['model_usage']['calls']==1
    monkeypatch.setattr(v25.core,'_invoke_model',lambda *a,**k:{'text':'An unrelated claim is proven by the made-up study. [A.P9]',
                                                               'reservation':'fixed-test-token'})
    bad=asyncio.run(v25.run_chat_v25(ChatQuery(question='What is observational evidence for dark matter?')))
    assert bad['answer_status']=='SOURCE_TEXT_LOCATED_MODEL_NOT_USED'
    assert bad['model_usage']['synthesis_status']=='CITATIONS_FORMAT_OR_NUMERICAL_CLAIMS_NOT_VALIDATED'


def test_math_no_network(monkeypatch):
    async def no_network(_):raise AssertionError('Math must not access literature network')
    monkeypatch.setattr(v25.retriever,'gather',no_network)
    result=asyncio.run(v25.run_chat_v25(ChatQuery(question="Solve the differential equation y''+4*y=0 subject to y(0)=2 and y'(0)=0. Explain the method.",workspace='math')))
    assert result['answer_status']=='FORMAL_MATH_CHECKED'


def test_versioned_gateway_and_safe_assets():
    gateway=(ROOT/'atlas_hosted_beta_v25.reference.py').read_text(encoding='utf-8')
    assert 'from atlas_conversation_v25 import run_chat_v25 as run_chat' in gateway
    assert "csrf_for(token)" in gateway
    assert "atlas-chat-v25.html" in gateway
    js=(ROOT/'v25_assets/atlas-chat-v25.js').read_text(encoding='utf-8')
    assert 'atlas-chat-v25' in js or 'atlas-chat-v24' not in js
    assert 'innerHTML' not in js


def test_research_title_identity_check():
    work,raw=sample()
    def resp(req):
        if req.url.host=='api.openalex.org':return httpx.Response(200,json={'results':[work]})
        return httpx.Response(200,headers={'content-type':'text/html'},content=b'<h1>Completely unrelated document about geology</h1><p>wrong content</p>')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(resp)) as client:
            return await r.gather('dark matter galaxy rotation curves',client=client)
    result=asyncio.run(run())
    assert result['citation_ledger']==[]
    assert result['diagnostics']['fulltext_retrieved']==0
