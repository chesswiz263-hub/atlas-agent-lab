"""Network-free primary-text, quote, evidence-gate and malicious-XML tests."""
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest

from atlas.science_primary import QuoteCandidate, _extract_xml, retrieve_primary, verify_quotes
from atlas.science_v12 import ScienceAskV12Request, scientific_answer_v12

ARTICLE = b'''<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<article-id pub-id-type="doi">10.1234/example.123</article-id>
<article-id pub-id-type="pmc">12345</article-id>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0"/></permissions>
</article-meta></front>
<body><sec><title>Observations</title>
<p>Galaxy rotation curves indicate missing mass under ordinary gravity assumptions.
Observational rotation curves require careful interpretation and independent crosschecks.</p>
<p>A hypothetical competing modified dynamics explanation was evaluated against the observed
orbital motions using separate assumptions about the governing acceleration field.</p>
</sec></body></article>'''


OA_RESULT = {'resultList': {'result': [{'doi': '10.1234/example.123',
    'title': 'Galaxy Rotation Curves and Dark Matter', 'pmcid': 'PMC12345',
    'isOpenAccess': 'Y', 'inEPMC': 'Y'}]}}


def response_for(request: httpx.Request) -> httpx.Response:
    if request.url.host == 'api.openalex.org':
        return httpx.Response(200, json={'results': [{
            'id': 'https://openalex.org/W1', 'title': 'Galaxy Rotation Curves and Dark Matter',
            'doi': 'https://doi.org/10.1234/example.123', 'publication_year': 2024,
            'authorships': [], 'primary_location': {},
            'abstract_inverted_index': {'Galaxy': [0], 'rotation': [1], 'curves': [2],
                 'can': [3], 'test': [4], 'ideas.': [5]},
        }]})
    if request.url.host == 'api.crossref.org':
        return httpx.Response(200, json={'message': {'DOI': '10.1234/example.123',
            'title': ['Galaxy Rotation Curves and Dark Matter'],
            'published': {'date-parts': [[2024]]}}})
    if request.url.path.endswith('/search'):
        return httpx.Response(200, json=OA_RESULT)
    if request.url.path.endswith('/PMC12345/fullTextXML'):
        return httpx.Response(200, content=ARTICLE, headers={'content-type': 'application/xml'})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_primary_quote_exact_match_and_provenance():
    async with httpx.AsyncClient(transport=httpx.MockTransport(response_for)) as client:
        result = await scientific_answer_v12(ScienceAskV12Request(
            question='What do galaxy rotation curves indicate about missing mass?',
            quote_candidates=[{'doi': '10.1234/example.123',
                'quote': 'Galaxy rotation curves indicate missing mass under ordinary gravity assumptions.'}],
        ), client)
    assert result['primary_fulltext_count'] == 1
    p = result['papers'][0]
    assert p['verification']['status'] == 'CROSSREF_METADATA_MATCH'
    assert p['primary_source']['status'] == 'REPOSITORY_FULLTEXT_MATCHED'
    assert len(p['primary_source']['document_sha256']) == 64
    assert 'creativecommons.org' in p['primary_source']['license']
    assert p['primary_passages'][0]['citation_id'] == 'P1.1'
    assert p['primary_passages'][0]['section'] == 'Observations'
    assert p['primary_passages'][0]['excerpt'] in ' '.join(ARTICLE.decode().split())
    assert result['quote_verifications'][0]['status'] == 'EXACT_TEXT_MATCH'
    assert result['answer_status'] == 'DETERMINISTIC_PRIMARY_EVIDENCE_REPORT'
    assert 'independently verified' not in result['answer']


@pytest.mark.asyncio
async def test_false_quote_is_rejected_not_fuzzily_accepted():
    async with httpx.AsyncClient(transport=httpx.MockTransport(response_for)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(
            question='What do galaxy rotation curves indicate about missing mass?',
            quote_candidates=[{'doi': '10.1234/example.123',
                'quote': 'Galaxy rotation curves prove the theory of dark matter is correct.'}],
        ), client)
    assert out['quote_verifications'][0]['status'] == 'EXACT_QUOTE_NOT_FOUND'


@pytest.mark.asyncio
async def test_repository_doi_mismatch_is_not_verified():
    xml = ARTICLE.replace(b'10.1234/example.123', b'10.1234/fabricated.999')
    def wrong(request):
        if request.url.path.endswith('fullTextXML'):
            return httpx.Response(200, content=xml)
        return response_for(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(wrong)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass'), client)
    assert out['papers'][0]['primary_source']['status'] == 'XML_DOI_UNCONFIRMED'
    assert out['primary_fulltext_count'] == 0


@pytest.mark.asyncio
async def test_redirect_is_never_followed_to_unsafe_host():
    def redirect(request):
        if request.url.path.endswith('fullTextXML'):
            return httpx.Response(302, headers={'location': 'http://127.0.0.1/private'})
        return response_for(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass'), client)
    assert out['papers'][0]['primary_source']['status'] == 'REPOSITORY_UNAVAILABLE'


@pytest.mark.asyncio
async def test_open_access_status_required():
    def no_oa(request):
        if request.url.path.endswith('/search'):
            return httpx.Response(200, json={'resultList': {'result': [
                {**OA_RESULT['resultList']['result'][0], 'isOpenAccess': 'N'}]}})
        return response_for(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_oa)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass'), client)
    assert out['papers'][0]['primary_source']['status'] == 'NO_OPEN_ACCESS_XML'


@pytest.mark.asyncio
async def test_crossref_update_requires_manual_review():
    def updated(request):
        if request.url.host == 'api.crossref.org':
            return httpx.Response(200, json={'message': {'DOI': '10.1234/example.123',
                'title': ['Galaxy Rotation Curves and Dark Matter'],
                'published': {'date-parts': [[2024]]}, 'update-to': [{'type': 'retraction'}]}})
        return response_for(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(updated)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass'), client)
    assert out['papers'][0]['primary_source']['status'] == 'UPDATE_REVIEW_REQUIRED'


def test_reject_external_entities_and_invalid_root():
    danger = b'<!DOCTYPE article [<!ENTITY xx SYSTEM "file:///etc/passwd">]><article><body><p>&xx;</p></body></article>'
    with pytest.raises(Exception):
        _extract_xml(danger, '10.1234/example.123', 'PMC12345')
    with pytest.raises(ValueError):
        _extract_xml(b'<other>' + b' ' * 200 + b'</other>', '10.1234/example.123', 'PMC12345')


@pytest.mark.asyncio
async def test_response_max_bytes_guard():
    def too_big(request):
        if request.url.path.endswith('fullTextXML'):
            return httpx.Response(200, content=ARTICLE, headers={'content-length': '99999999'})
        return response_for(request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(too_big)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass'), client)
    assert out['papers'][0]['primary_source']['status'] == 'FULLTEXT_TOO_LARGE'


@pytest.mark.asyncio
async def test_model_citations_use_primary_passage_ids(monkeypatch):
    config = ModuleType('atlas.config')
    config.DEFAULT_MODELS = {'openai': 'test-model'}
    module = ModuleType('atlas.providers')
    class ProviderError(Exception):
        pass
    class FakeProvider:
        def __init__(self, provider):
            self.provider = provider
        async def complete(self, messages, tools, model):
            assert 'P1.1' in messages[1]['content']
            return SimpleNamespace(content='The article reports missing mass in rotation curves [P1.1].')
    module.NativeProvider = FakeProvider
    module.ProviderError = ProviderError
    monkeypatch.setitem(sys.modules, 'atlas.config', config)
    monkeypatch.setitem(sys.modules, 'atlas.providers', module)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response_for)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass', provider='openai'), client)
    assert out['answer_status'] == 'PRIMARY_PASSAGE_GROUNDED_NOT_CLAIM_VERIFIED'
    assert out['source_span_citations'] == ['P1.1']


@pytest.mark.asyncio
async def test_model_citation_fabrication_rejected(monkeypatch):
    config = ModuleType('atlas.config')
    config.DEFAULT_MODELS = {'openai': 'test-model'}
    module = ModuleType('atlas.providers')
    class ProviderError(Exception):
        pass
    class FakeProvider:
        def __init__(self, provider):
            pass
        async def complete(self, messages, tools, model):
            return SimpleNamespace(content='Invented proof from source [P9.9].')
    module.NativeProvider = FakeProvider
    module.ProviderError = ProviderError
    monkeypatch.setitem(sys.modules, 'atlas.config', config)
    monkeypatch.setitem(sys.modules, 'atlas.providers', module)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response_for)) as client:
        out = await scientific_answer_v12(ScienceAskV12Request(question='galaxy rotation curves missing mass', provider='openai'), client)
    assert out['answer_status'] == 'PRIMARY_MODEL_CITATIONS_REJECTED'
    assert '[P9.9]' not in out['answer']


def test_quote_and_request_validation_limits():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        QuoteCandidate(doi='https://private-host/x', quote='An illustrative exact passage')
    with pytest.raises(ValidationError):
        ScienceAskV12Request(question='Galactic astrophysics', max_primary_papers=99)
    with pytest.raises(ValidationError):
        ScienceAskV12Request(question='Galactic astrophysics', quote_candidates=[
            {'doi':'10.1234/example.123','quote':'A three word example'}] * 5)
