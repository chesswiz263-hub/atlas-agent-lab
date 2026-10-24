"""ATLAS 2.6.3 live-report regression tests; HTTP mocked, no API or billing."""
import asyncio
import httpx
import atlas_retrieval_v26 as r

OBJ={'category':'cmb','query':r.DARK_MATTER['cmb'][0], 'anchors':r.DARK_MATTER['cmb'][1]}
WRONG='Bayesian estimation of our local motion from the Planck-2018 CMB temperature map'

def metadata(aid,title):
    return {'id':'https://openalex.org/W'+aid.replace('.',''),'title':title,'type':'article',
            'locations':[{'landing_page_url':'https://arxiv.org/abs/'+aid}]}

def planck_body(title=r.CURATED_CMB[0]['title']):
    # Mimic the long author/affiliation block of the real Planck publications.
    affiliations=''.join('<div>Affiliation: Observatory Department of Astronomy, university. '+str(i)+'</div>' for i in range(160))
    evidence=('We present cosmological parameter results from the final full-mission Planck '
              'measurements of the cosmic microwave background CMB temperature and polarization '
              'anisotropy power spectra. Under base Lambda CDM, we find a cold dark matter density '
              'and baryon matter density from acoustic peaks. We measure cosmological parameters '
              'with observed Planck data and characterize systematic uncertainties. ')
    return ('<html><body><h1>'+title+'</h1>'+affiliations+
            '<h2>Abstract</h2><p>'+evidence*4+'</p><h2>1 Introduction</h2><p>'+evidence*4+'</p>'+
            '</body></html>').encode('utf-8')

def test_real_fulltext_fallback_recovers_cmb_when_openalex_only_finds_distractor(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    monkeypatch.setenv('ATLAS_V26_CMB_CURATED_FALLBACK','1')
    seen=[]
    def route(request):
        seen.append(str(request.url))
        if request.url.host=='api.openalex.org':
            return httpx.Response(200,json={'results':[metadata('2106.07666',WRONG)]})
        if request.url.host=='ar5iv.labs.arxiv.org':
            assert request.url.path.startswith('/html/')
            assert request.url.path.endswith('1807.06209')
            return httpx.Response(200,headers={'content-type':'text/html'},content=planck_body())
        raise AssertionError('The distractor arXiv paper should not be retrieved')
    monkeypatch.setattr(r,'plan',lambda *_args,**_kwargs:[OBJ])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route),follow_redirects=False) as client:
            return await r.gather('dark matter evidence from CMB',client=client)
    result=asyncio.run(run())
    assert result['diagnostics']['categories_covered']==['cmb']
    assert result['diagnostics']['curated_cmb_fulltext_attempts']==1
    assert result['diagnostics']['curated_cmb_fulltext_accepted']==1
    assert result['diagnostics']['rejected_metadata']['cmb']==2  # initial + fallback
    ledger=result['citation_ledger']
    assert ledger[0]['arxiv_id']=='1807.06209'
    assert ledger[0]['publication_status']=='AR5IV_RENDERED_ARXIV_SOURCE_PEER_REVIEW_NOT_VERIFIED'
    assert 'Planck' in ledger[0]['excerpt'] and 'CMB' in ledger[0]['excerpt']
    assert 'Affiliation' not in ledger[0]['excerpt']
    assert result['papers'][0]['source_url'].startswith('https://ar5iv.labs.arxiv.org/html/')
    assert result['papers'][0]['version'].startswith('ar5iv third-party')
    assert all('OPENALEX' not in x.upper() for x in [rec['source_url'] for rec in ledger])

def test_does_not_cite_abstract_or_wrong_article_when_fulltext_fails(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    monkeypatch.setenv('ATLAS_V26_CMB_CURATED_FALLBACK','1')
    def route(request):
        if request.url.host=='api.openalex.org':return httpx.Response(200,json={'results':[]})
        if request.url.path.endswith('1807.06209'):
            return httpx.Response(200,headers={'content-type':'text/html'},content=planck_body('A completely unrelated satellite paper'))
        return httpx.Response(403,content='blocked')
    monkeypatch.setattr(r,'plan',lambda *_args,**_kwargs:[OBJ])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route),follow_redirects=False) as client:
            return await r.gather('dark matter evidence from CMB',client=client)
    result=asyncio.run(run())
    assert result['diagnostics']['categories_missing']==['cmb']
    assert not result['citation_ledger']
    assert result['diagnostics']['curated_cmb_fulltext_accepted']==0
    assert result['diagnostics']['curated_cmb_fulltext_attempts']==2

def test_optional_cmb_fallback_opt_out(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    monkeypatch.setenv('ATLAS_V26_CMB_CURATED_FALLBACK','0')
    seen=[]
    def route(request):
        seen.append(request.url.host)
        assert request.url.host=='api.openalex.org'
        return httpx.Response(200,json={'results':[]})
    monkeypatch.setattr(r,'plan',lambda *_args,**_kwargs:[OBJ])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route),follow_redirects=False) as client:
            return await r.gather('dark matter evidence from CMB',client=client)
    result=asyncio.run(run())
    assert result['diagnostics']['categories_missing']==['cmb']
    assert 'ar5iv.labs.arxiv.org' not in seen

def test_curated_fetch_requires_real_article_body_and_correlated_title(monkeypatch):
    async def run(body):
        def route(request):return httpx.Response(200,content=body,headers={'content-type':'text/html'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            return await r._retrieve_curated_cmb_work(client,r.CURATED_CMB[0])
    try:
        asyncio.run(run(b'<html><body><h1>Planck 2018 results. VI. Cosmological parameters</h1></body></html>'))
        assert False,'No body should fail'
    except ValueError as exc:assert 'No article body' in str(exc)
    try:
        asyncio.run(run(b'<html><body><h2>Abstract</h2><p>Other source has microwave background observations and data.</p></body></html>'))
        assert False,'Identity mismatch should fail'
    except ValueError as exc:assert 'not corroborated' in str(exc)


def test_hardcoded_metadata_is_not_a_source_or_answer():
    assert all('excerpt' not in x and 'answer' not in x for x in r.CURATED_CMB)
    assert len({x['arxiv_id'] for x in r.CURATED_CMB})==2
