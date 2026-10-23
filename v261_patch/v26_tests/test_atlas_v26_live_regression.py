"""v2.6.1 regression tests for the real 2026-10-23 dark-matter run.
Network and paid provider calls are mocked, not live scientific verification.
"""
import asyncio
import json
import httpx
import pytest

import atlas_retrieval_v26 as retriever
import atlas_conversation_v26 as chat
from atlas_conversation_v22 import ChatQuery

CIB_TITLE = 'Planck early results. XVIII. The power spectrum of cosmic infrared background anisotropies'
CIB_ID = '1101.2028'
CMB_TITLE = 'Planck 2018 results. V. CMB power spectra and likelihoods'
CMB_ID = '1907.12875'
ALTERNATIVE_TITLE = 'CMB polarization power spectra from observational measurements'
ALTERNATIVE_ID = '2501.00001'


def _entry(identifier, title):
    return {'id':'https://openalex.org/W'+identifier, 'title':title,'type':'article',
            'locations':[{'landing_page_url':'https://arxiv.org/abs/'+identifier}]}


def test_cib_is_not_cmb_even_with_planck_and_power_spectrum():
    assert not retriever._observational_title({'title':CIB_TITLE},'cmb')
    assert retriever._observational_title({'title':CMB_TITLE},'cmb')
    assert retriever._support_score('Planck cosmic infrared background anisotropies power spectrum measurements.',
           {'category':'cmb','anchors':retriever.DARK_MATTER['cmb'][1]},CMB_TITLE)<0


def test_cmb_fallback_search_replaces_actual_wrong_planck_paper(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    requests=[]
    def route(request):
        if request.url.host=='api.openalex.org':
            term=request.url.params.get('search.title_and_abstract','')
            requests.append(str(term))
            results=([_entry(CIB_ID,CIB_TITLE)] if '2018 CMB power' in term else
                     [_entry(CMB_ID,CMB_TITLE)] if '2018 results V' in term else [])
            return httpx.Response(200,json={'results':results})
        if request.url.host=='arxiv.org':
            aid=request.url.path.split('/')[-1]
            assert aid != CIB_ID  # CIB must be rejected before downloading
            if aid!=CMB_ID:return httpx.Response(404)
            paragraph=('We measure Planck cosmic microwave background temperature anisotropy and '
                      'polarization CMB power spectra using the observed sky maps. '
                      'The CMB acoustic peak measurements constrain cosmological models.')
            html='<html><article><h1>'+CMB_TITLE+'</h1><p>'+paragraph*5+'</p></article></html>'
            return httpx.Response(200,content=html.encode('utf-8'),headers={'content-type':'text/html'})
        raise AssertionError('Unexpected mock request')
    objective={'category':'cmb','query':retriever.DARK_MATTER['cmb'][0],
               'anchors':retriever.DARK_MATTER['cmb'][1]}
    monkeypatch.setattr(retriever,'plan',lambda *_args,**_kwargs:[objective])
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            return await retriever.gather('CMB dark matter',client=client)
    result=asyncio.run(collect())
    assert result['diagnostics']['categories_missing']==[]
    assert result['diagnostics']['rejected_metadata']['cmb']==1
    assert len(requests)==2  # first planned query + bounded category-specific fallback
    assert result['diagnostics']['fulltext_retrieved']==1
    assert all(x['arxiv_id']==CMB_ID for x in result['citation_ledger'])
    assert all('cosmic infrared' not in x['excerpt'].lower() for x in result['citation_ledger'])


def test_category_retries_when_first_fetched_paper_has_no_cmb_passage(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    def route(request):
        if request.url.host=='api.openalex.org':
            return httpx.Response(200,json={'results':[_entry(CMB_ID,CMB_TITLE),_entry(ALTERNATIVE_ID,ALTERNATIVE_TITLE)]})
        if request.url.host=='arxiv.org':
            aid=request.url.path.split('/')[-1]
            title= CMB_TITLE if aid==CMB_ID else ALTERNATIVE_TITLE
            paragraph=('An instrument engineering note reports calibration of cables and bolometer mount temperatures. '
                       'It describes thermal stability of hardware but includes no sky data or cosmology.'
                       if aid==CMB_ID else
                       'We measure cosmic microwave background polarization anisotropies in observed sky maps. '
                       'These cosmic microwave background measurements constrain models.')
            return httpx.Response(200,content=('<html><h1>'+title+'</h1><p>'+paragraph*8+'</p></html>').encode('utf-8'),
                                  headers={'content-type':'text/html'})
        raise AssertionError('Unexpected mock request')
    objective={'category':'cmb','query':retriever.DARK_MATTER['cmb'][0],
               'anchors':retriever.DARK_MATTER['cmb'][1]}
    monkeypatch.setattr(retriever,'plan',lambda *_args,**_kwargs:[objective])
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            return await retriever.gather('CMB measurements',client=client)
    result=asyncio.run(collect())
    assert result['diagnostics']['fulltext_attempts'] == 2
    assert result['diagnostics']['rejected_passages']['cmb'] == 1
    assert result['diagnostics']['categories_covered']==['cmb']
    assert all(x['arxiv_id']==ALTERNATIVE_ID for x in result['citation_ledger'])


def test_explicit_model_disabled_status_not_claimed_as_rejected(monkeypatch):
    excerpt='Planck CMB temperature anisotropy measurements identified acoustic peaks in the observed power spectrum.'
    async def fake(*a,**k):return {'citation_ledger':[{'citation_id':'A.P1','evidence_category':'cmb',
        'title':CMB_TITLE,'excerpt':excerpt,'source_locator':'arXiv HTML passage 3'}],
        'papers':[],'status':'PASSAGES_LOCATED','diagnostics':{'categories_requested':['cmb'],
        'categories_missing':[],'fulltext_retrieved':1}}
    monkeypatch.setattr(chat.retrieval,'gather',fake)
    monkeypatch.setattr(chat.llm,'model_configuration',lambda:{'enabled':False,'status':'DISABLED'})
    monkeypatch.setattr(chat.previous.core,'_invoke_model',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Should not call')))
    result=asyncio.run(chat.run_chat_v26(ChatQuery(question='CMB dark matter evidence?',workspace='research')))
    assert result['answer_status']=='SOURCE_TEXT_LOCATED_MODEL_DISABLED'
    assert result['research_diagnostics']['model_configuration_status']=='DISABLED'
    assert result['research_diagnostics']['model_attempted'] is False
    assert result['model_usage']['synthesis_status']=='DISABLED'


def test_provider_error_is_sanitized_not_disguised_as_disabled(monkeypatch):
    async def fake(*a,**k):return {'citation_ledger':[{'citation_id':'A.P1','evidence_category':'cmb',
        'title':CMB_TITLE,'excerpt':'We measure CMB temperature anisotropies in observations.',
        'source_locator':'arXiv HTML passage 3'}], 'papers':[],'status':'PASSAGES_LOCATED',
        'diagnostics':{'categories_requested':['cmb'],'categories_missing':[],'fulltext_retrieved':1}}
    monkeypatch.setattr(chat.retrieval,'gather',fake)
    monkeypatch.setattr(chat.llm,'model_configuration',lambda:{'enabled':True,'status':'READY_TO_ATTEMPT'})
    def exploding(*a,**k):raise RuntimeError('PRIVATE_KEY_DO_NOT_LEAK')
    monkeypatch.setattr(chat.previous.core,'_invoke_model',exploding)
    result=asyncio.run(chat.run_chat_v26(ChatQuery(question='CMB dark matter evidence?',workspace='research')))
    assert result['answer_status']=='MODEL_CALL_UNAVAILABLE'
    assert result['model_usage']['synthesis_status']=='PROVIDER_OR_BUDGET_UNAVAILABLE'
    assert result['model_usage']['error_type']=='RuntimeError'
    assert 'PRIVATE_KEY_DO_NOT_LEAK' not in json.dumps(result)


def test_coherent_excerpt_windows_do_not_start_in_the_middle_of_words():
    paragraph=('A study of Bullet Cluster mass measurements uses X-ray gas and weak lensing '
               'observations to compare spatial positions of the different components. ')*14
    excerpts=retriever._coherent_excerpts('<garbage>\\n\\n'.replace('\\n','\n')+paragraph)
    assert len(excerpts)>1
    assert all(len(x['text'])<=500 for x in excerpts)
    assert all(x['text'][0].isalpha() for x in excerpts)
    assert all(x['text'].split()[0] in paragraph.split() for x in excerpts)
