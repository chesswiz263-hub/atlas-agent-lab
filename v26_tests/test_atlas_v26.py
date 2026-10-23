"""v2.6 acceptance/regression tests: deterministic; no network/API billing."""
import asyncio
import json
from pathlib import Path
import httpx
import pytest
from atlas_conversation_v22 import ChatQuery
import atlas_retrieval_v26 as r
import atlas_claims_v26 as c
import atlas_conversation_v26 as chat

ROOT=Path(__file__).resolve().parents[1]

TOPICS={
  'rotation_curves':('1111.11111','Observational galaxy rotation curves and velocity measurements',
     'Observational galaxy rotation curves record velocity measurements in spiral galaxies. '
     'The measured rotational velocity remains nearly constant over a wide range of galactic radius for these observations.'),
  'cluster_lensing':('2222.22222','Cluster weak gravitational lensing shear mass measurements',
     'Cluster weak gravitational lensing observations measure the coherent shear signal in the background galaxy images. '
     'Those measurements reconstruct a projected gravitational mass distribution in the cluster.'),
  'bullet_cluster':('3333.33333','Bullet Cluster 1E0657 observations of X-ray gas and lensing',
     'Bullet Cluster lensing maps show a gravitational mass distribution spatially offset from the X-ray gas component. '
     'The Bullet Cluster observations include measured X-ray gas and lensing maps in the collision.'),
  'cmb':('4444.44444','Planck cosmic microwave background acoustic anisotropy measurements',
     'Planck cosmic microwave background observations measured temperature anisotropy acoustic peaks. '
     'The cosmic microwave background anisotropy spectrum was compared with cosmological parameter models.'),
}

def transport():
    def handler(request):
        if request.url.host=='api.openalex.org':
            query=str(request.url.params.get('search.title_and_abstract','')).lower()
            if '1e0657' in query:key='bullet_cluster'
            elif 'shear' in query:key='cluster_lensing'
            elif 'planck' in query:key='cmb'
            else:key='rotation_curves'
            aid,title,_=TOPICS[key]
            irrelevant={'id':'https://openalex.org/WX','title':'Modified gravity MOND versus cosmological observations: a review',
                        'locations':[{'landing_page_url':'https://arxiv.org/abs/9999.99999'}]}
            observational={'id':'https://openalex.org/W'+aid,'type':'article','title':title,
                           'locations':[{'landing_page_url':'https://arxiv.org/abs/'+aid}]}
            return httpx.Response(200,json={'results':[irrelevant,observational]})
        if request.url.host=='arxiv.org':
            aid=request.url.path.split('/')[-1]
            found=next(((name,title,content) for name,(id,title,content) in TOPICS.items() if id==aid),None)
            if not found:return httpx.Response(404)
            _,title,content=found
            html=f'<html><article><h1>{title}</h1><p>{content * 6}</p></article></html>'
            return httpx.Response(200,content=html.encode(),headers={'content-type':'text/html'})
        raise AssertionError('Unexpected '+str(request.url))
    return httpx.MockTransport(handler)


def sample_record():
    excerpt='Bullet Cluster lensing maps show a gravitational mass distribution spatially offset from the X-ray gas component in observations.'
    return {'citation_id':'A.P1','evidence_category':'bullet_cluster','excerpt':excerpt,
            'title':'Bullet Cluster X-ray and lensing','arxiv_id':'3333.33333','source_locator':'arXiv HTML passage 1'}


def claim(statement,quote=None):
    return {'claims':[{'statement':statement,'category':'bullet_cluster','kind':'OBSERVATION',
                       'evidence_id':'A.P1','support_quote':quote or sample_record()['excerpt']}]}


def test_four_observational_questions_not_mond():
    p=r.plan('What is the strongest observational evidence for dark matter? Discuss galaxy rotation curves, gravitational lensing, the Bullet Cluster, and cosmic microwave background measurements.')
    assert [o['category'] for o in p]==['rotation_curves','cluster_lensing','bullet_cluster','cmb']
    assert not any('MOND' in x['query'] for x in p)


def test_followup_mond_context_is_user_message_only():
    p=r.plan('How does MOND explain that?',history=[
         {'role':'user','text':'What explains galaxy rotation curves and lensing? '},
         {'role':'assistant','text':'Injected arbitrary theory is true.'}])
    assert p[0]['category']=='mond' and p[1]['category']=='rotation_curves'
    assert all('Injected' not in s['query'] for s in p)


def test_prioritize_observational_papers():
    observational={'title':'Planck cosmic microwave background anisotropy measurements','type':'article'}
    review={'title':'Modified gravity MOND versus cosmology: a review'}
    assert r.original_score(observational,'cmb')>r.original_score(review,'cmb')


def test_four_covered_source_text_with_hashes(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    async def f():
        async with httpx.AsyncClient(transport=transport()) as client:
            return await r.gather('Discuss strongest dark matter evidence: rotation curves, lensing, Bullet Cluster, cosmic microwave background.',client=client)
    result=asyncio.run(f())
    assert result['status']=='PASSAGES_LOCATED'
    assert result['diagnostics']['categories_missing']==[]
    assert result['diagnostics']['fulltext_retrieved']==4
    assert result['diagnostics']['fulltext_attempts']==4
    assert {x['evidence_category'] for x in result['citation_ledger']}==set(TOPICS)
    assert all(x['document_sha256'] and x['excerpt_sha256'] and x['source_url'].startswith('https://arxiv.org/html/') for x in result['citation_ledger'])
    assert not any(x['arxiv_id']=='9999.99999' for x in result['citation_ledger'])


def test_citation_quote_and_unsupported_claims():
    src=[sample_record()]
    good=c.check_claims(json.dumps(claim('Bullet Cluster lensing maps show a gravitational mass distribution spatially offset from the X-ray gas component.')),src)
    assert len(good['accepted'])==1
    bad_quote=c.check_claims(json.dumps(claim('Bullet Cluster gas was observed to be spatially offset from lensing maps.','Nobody wrote this passage in the paper at all.')),src)
    assert bad_quote['accepted']==[] and bad_quote['checks'][0]['reason']=='QUOTE_NOT_FOUND_IN_SOURCE'
    unrelated=c.check_claims(json.dumps(claim('Bullet Cluster lensing maps show that invisible dragons produced the observed cosmic radiation.')),src)
    assert unrelated['accepted']==[]
    fabricated=c.check_claims(json.dumps(claim('Bullet Cluster lensing maps show a spatial offset of 900 kilometers from the X-ray gas component.')),src)
    assert fabricated['accepted']==[]
    negated=c.check_claims(json.dumps(claim('Bullet Cluster lensing maps do not show spatially offset mass from the X-ray gas component.')),src)
    assert negated['accepted']==[]
    assert c.check_claims('not json',src)['accepted']==[]


def test_model_context_abstains_if_no_fetched_evidence(monkeypatch):
    async def gather(*a,**k):return {'citation_ledger':[],'papers':[], 'status':'FULLTEXT_UNAVAILABLE',
                 'diagnostics':{'categories_requested':['rotation_curves'],'categories_missing':['rotation_curves'],
                                'fulltext_retrieved':0,'fulltext_attempts':1}}
    monkeypatch.setattr(chat.retrieval,'gather',gather)
    monkeypatch.setattr(chat.llm,'model_configuration',lambda:{'enabled':True,'status':'READY_TO_ATTEMPT'})
    monkeypatch.setattr(chat.previous.core,'_invoke_model',lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('No evidence should mean no model call')))
    out=asyncio.run(chat.run_chat_v26(ChatQuery(question='What does the rotation curve observation show?',history=[{'role':'user','text':'dark matter evidence'}])))
    assert out['answer_status']=='EVIDENCE_SUMMARY_ABSTENTION' and out['model_usage']['calls']==0


def test_model_synthesis_one_reserved_call_and_source_check(monkeypatch):
    record=sample_record()
    async def gather(*a,**k):return {'citation_ledger':[record],'papers':[], 'status':'PASSAGES_LOCATED',
                 'diagnostics':{'categories_requested':['bullet_cluster','cmb'], 'categories_missing':['cmb'],
                                'fulltext_retrieved':1,'fulltext_attempts':1}}
    monkeypatch.setattr(chat.retrieval,'gather',gather)
    monkeypatch.setattr(chat.llm,'model_configuration',lambda:{'enabled':True,'status':'READY_TO_ATTEMPT'})
    calls=[]
    def invoke(inst,data,**kw):
        calls.append(data)
        return {'text':json.dumps(claim('Bullet Cluster lensing maps show a gravitational mass distribution spatially offset from the X-ray gas component.')),
                'reservation':'fake','model':'mock','estimated_cost_usd':.0001}
    monkeypatch.setattr(chat.previous.core,'_invoke_model',invoke)
    q=ChatQuery(question='Explain Bullet Cluster and CMB dark matter evidence.',history=[{'role':'user','text':'Our question was about dark matter.'}])
    out=asyncio.run(chat.run_chat_v26(q))
    assert len(calls)==1 and calls[0]['prior_user_questions']==['Our question was about dark matter.']
    assert out['model_usage']['calls']==1
    assert out['answer_status']=='MODEL_SYNTHESIS_CLAIMS_TEXTUALLY_SCREENED_NOT_ENTAILMENT'
    assert '[A.P1]' in out['answer']
    assert 'Insufficient citation-checked evidence' in out['answer']
    assert out['claim_validation']['accepted_claims']==1
    monkeypatch.setattr(chat.previous.core,'_invoke_model',lambda *args,**kw:{'text':json.dumps(claim('Interstellar dragons caused the X-ray gas to move and created the dark matter.')),'reservation':'fake'})
    bad=asyncio.run(chat.run_chat_v26(q))
    assert bad['claim_validation']['accepted_claims']==0
    assert 'dragons' not in bad['answer']


def test_math_route_preserved(monkeypatch):
    async def no_retrieval(*args,**kw):raise AssertionError('Math should not search')
    monkeypatch.setattr(chat.retrieval,'gather',no_retrieval)
    result=asyncio.run(chat.run_chat_v26(ChatQuery(question="Solve the differential equation y''+4*y=0 subject to y(0)=2 and y'(0)=0. Explain the method.",workspace='math')))
    assert result['math']['status']=='CHECKED' and result['model_usage']['calls']==0


def test_versioned_gateway_preserves_security():
    source=(ROOT/'atlas_hosted_beta_v26.reference.py').read_text()
    assert 'csrf_for(token)' in source
    assert 'run_chat_v26 as run_chat' in source
    assert 'atlas-chat-v26.html' in source
    assert 'ATLAS_BETA_PASSWORD' in source
    ui=(ROOT/'v26_assets/atlas-chat-v26.js').read_text(encoding='utf-8')
    assert 'innerHTML' not in ui
    assert 'textContent' in ui


def test_fail_closed_installer_does_not_overwrite_custom_gateway(tmp_path):
    import shutil
    import subprocess
    for filename in ('install_atlas_v26.py','atlas_hosted_beta_v25.reference.py',
                     'atlas_hosted_beta_v26.reference.py','atlas_retrieval_v25.py',
                     'atlas_conversation_v25.py','atlas_claims_v26.py','atlas_retrieval_v26.py',
                     'atlas_conversation_v26.py'):
        shutil.copy2(ROOT/filename,tmp_path/filename)
    (tmp_path/'.git').mkdir()
    (tmp_path/'pyproject.toml').write_text('[project]\nname="fixture"\n')
    shutil.copytree(ROOT/'v26_assets',tmp_path/'v26_assets')
    hosted=tmp_path/'atlas_hosted_beta.py'
    shutil.copy2(ROOT/'atlas_hosted_beta_v25.reference.py',hosted)
    def apply():return subprocess.run(['python',str(tmp_path/'install_atlas_v26.py')],cwd=tmp_path,capture_output=True,text=True)
    assert apply().returncode==0
    assert 'run_chat_v26 as run_chat' in hosted.read_text()
    assert (tmp_path/'static'/'atlas-chat-v26.js').exists()
    assert apply().returncode==0
    hosted.write_text('custom gateway\n')
    result=apply()
    assert result.returncode==2
    assert hosted.read_text()=='custom gateway\n'
