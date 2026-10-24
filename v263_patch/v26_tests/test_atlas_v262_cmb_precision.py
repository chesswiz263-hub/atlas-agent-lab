"""v2.6.2 source-intent regressions. Entirely mocked: no API, billing or deployment."""
import asyncio
import httpx
import atlas_retrieval_v26 as r

WRONG = 'Bayesian estimation of our local motion from the Planck-2018 CMB temperature map'
RIGHT = 'Planck 2018 results. V. CMB power spectra and likelihoods'
PARAM = 'Planck 2018 results. VI. Cosmological parameters'
CIB = 'Planck early results. XVIII. The power spectrum of cosmic infrared background anisotropies'


def row(aid, title):
    return {'id':'https://openalex.org/W'+aid.replace('.',''), 'type':'article','title':title,
            'locations':[{'landing_page_url':'https://arxiv.org/abs/'+aid}]}


def test_reject_planck_local_motion_as_dark_matter_evidence():
    assert not r._observational_title({'title':WRONG},'cmb')
    assert not r._observational_title({'title':CIB},'cmb')
    assert r._observational_title({'title':RIGHT},'cmb')
    assert r._observational_title({'title':PARAM},'cmb')


def test_power_spectra_rank_above_cmb_dipole():
    assert r.original_score({'title':RIGHT},'cmb')>r.original_score({'title':WRONG},'cmb')


def test_mere_cmb_local_motion_excerpt_does_not_prove_cmb_evidence():
    p='Our relative motion with respect to the cosmic microwave background produces a temperature dipole in a CMB map.'
    objective={'category':'cmb','anchors':r.DARK_MATTER['cmb'][1]}
    assert r._support_score(p,objective,WRONG)<0


def test_live_report_pattern_is_rejected_and_targeted_fallback_recovers(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    seen=[]
    def route(request):
        if request.url.host=='api.openalex.org':
            term=str(request.url.params.get('search.title_and_abstract',''))
            seen.append(term)
            return httpx.Response(200,json={'results':[row('2106.07666',WRONG)] if 'results V' not in term else [row('1907.12875',RIGHT)]})
        assert request.url.host=='arxiv.org'
        aid=request.url.path.split('/')[-1]
        assert aid=='1907.12875','Wrong Planck paper should never be downloaded'
        paragraph=('We measure Planck CMB temperature polarization anisotropy power spectra, '
                   'including acoustic peaks that constrain cosmological model parameters. ')
        return httpx.Response(200,content=('<html><h1>'+RIGHT+'</h1><p>'+paragraph*9+'</p></html>').encode(),
                              headers={'content-type':'text/html'})
    obj={'category':'cmb','query':r.DARK_MATTER['cmb'][0], 'anchors':r.DARK_MATTER['cmb'][1]}
    monkeypatch.setattr(r,'plan',lambda *_a,**_kw:[obj])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            return await r.gather('What dark matter evidence comes from CMB acoustic peaks?',client=client)
    result=asyncio.run(run())
    assert result['diagnostics']['categories_missing']==[]
    assert result['diagnostics']['rejected_metadata']['cmb']==1
    assert result['diagnostics']['fulltext_attempts']==1
    assert len(seen)==2
    assert result['citation_ledger'] and all(x['arxiv_id']=='1907.12875' for x in result['citation_ledger'])


def test_only_wrong_paper_results_in_honest_gap(monkeypatch):
    monkeypatch.setenv('ATLAS_V26_RETRIEVAL_ENABLED','1')
    monkeypatch.setenv('ATLAS_V26_CMB_CURATED_FALLBACK','0')  # explicitly exercise no-fallback mode
    def route(request):
        assert request.url.host=='api.openalex.org'
        return httpx.Response(200,json={'results':[row('2106.07666',WRONG)]})
    obj={'category':'cmb','query':r.DARK_MATTER['cmb'][0], 'anchors':r.DARK_MATTER['cmb'][1]}
    monkeypatch.setattr(r,'plan',lambda *_a,**_kw:[obj])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            return await r.gather('What does the CMB show?',client=client)
    result=asyncio.run(run())
    assert result['diagnostics']['categories_covered']==[]
    assert result['diagnostics']['categories_missing']==['cmb']
    assert result['citation_ledger']==[]
