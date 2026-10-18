"""Live scientific upgrade tests with *mocked* scholarly APIs; no credentials or network."""
import json

import httpx
import pytest

from atlas.science import (
    ScienceAskRequest, abstract_from_index, compare_mentions, discover_papers,
    scientific_answer,
)
from atlas.science_math import MathTask, evaluate_math_task


OPENALEX_RESULT = {
    'results': [{
        'id': 'https://openalex.org/W123',
        'title': 'Galaxy Rotation Curves and Dark Matter',
        'doi': 'https://doi.org/10.1234/example.123',
        'publication_year': 2024,
        'authorships': [{'author': {'display_name': 'A. Scientist'}}],
        'primary_location': {'source': {'display_name': 'Physics Journal'}},
        'abstract_inverted_index': {
            'Dark': [0], 'matter': [1], 'and': [2], 'modified': [3],
            'Newtonian': [4], 'dynamics': [5], 'are': [6], 'compared.': [7],
        },
    }]
}


def mock_scholar(request: httpx.Request) -> httpx.Response:
    if request.url.host == 'api.openalex.org':
        return httpx.Response(200, json=OPENALEX_RESULT)
    if request.url.host == 'api.crossref.org':
        return httpx.Response(200, json={'message': {
            'DOI': '10.1234/example.123',
            'title': ['Galaxy Rotation Curves and Dark Matter'],
            'published': {'date-parts': [[2024, 6, 1]]},
        }})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_literature_discovery_and_crosscheck():
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_scholar)) as client:
        result = await discover_papers('dark matter rotation curves', client=client)
    assert result['status'] == 'RESULTS_FOUND'
    paper = result['papers'][0]
    assert paper['verification']['status'] == 'CROSSREF_METADATA_MATCH'
    assert paper['doi_url'] == 'https://doi.org/10.1234/example.123'
    assert 'modified Newtonian dynamics' in paper['abstract']
    assert paper['abstract_provenance'] == 'OPENALEX_INDEX_NOT_PRIMARY_TEXT'


@pytest.mark.asyncio
async def test_no_unverified_claims_about_comparison():
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_scholar)) as client:
        out = await scientific_answer(ScienceAskRequest(
            question='dark matter rotation curves',
            hypotheses=['dark matter', 'MOND'], provider='demo',
            math_tasks=[MathTask(expression='(x+1)**2 = x**2+2*x+1', operation='verify_equation')]
        ), client=client)
    assert out['answer_status'] == 'DETERMINISTIC_DISCOVERY_SUMMARY'
    assert out['hypothesis_comparison'][0]['papers_mentioning_label'] == [1]
    assert out['hypothesis_comparison'][1]['papers_mentioning_label'] == []
    assert all(h['status'] == 'NOT_EVALUATED' for h in out['hypothesis_comparison'])
    assert out['math_checks'][0]['status'] == 'FORMALLY_EQUIVALENT'
    assert 'not paper content' in out['limits'][1]


@pytest.mark.asyncio
async def test_api_unavailable_never_fabricates_papers():
    def bad(_request):
        return httpx.Response(503)
    async with httpx.AsyncClient(transport=httpx.MockTransport(bad)) as client:
        out = await scientific_answer(ScienceAskRequest(question='Evidence for dark matter'), client)
    assert out['status'] == 'DISCOVERY_UNAVAILABLE'
    assert out['papers'] == []
    assert 'could not find' in out['answer']


@pytest.mark.asyncio
async def test_crossref_title_mismatch_is_flagged():
    def mismatch(request):
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json=OPENALEX_RESULT)
        return httpx.Response(200, json={'message': {
            'DOI': '10.1234/example.123', 'title': ['Completely different publication'],
            'published': {'date-parts': [[2024]]},
        }})
    async with httpx.AsyncClient(transport=httpx.MockTransport(mismatch)) as client:
        out = await discover_papers('galaxy dark matter', client=client)
    assert out['papers'][0]['verification']['status'] == 'METADATA_MISMATCH'


def test_abstract_reconstruction_rejects_sparse_positions():
    assert abstract_from_index({'first': [0], 'missing': [4], 'words': [5]}) == ''


def test_safeguarded_math():
    assert evaluate_math_task(MathTask(expression='2*x + 1', operation='differentiate')).get('result') == '2'
    assert evaluate_math_task(MathTask(expression='sin(x)**2 + cos(x)**2 = 1', operation='verify_equation'))['status'] == 'FORMALLY_EQUIVALENT'
    assert evaluate_math_task(MathTask(expression='x+1 = x+2', operation='verify_equation'))['status'] == 'NOT_PROVEN'
    assert evaluate_math_task(MathTask(expression='__import__("os")', operation='simplify'))['status'] == 'NOT_CHECKED'
    assert evaluate_math_task(MathTask(expression='x**100', operation='simplify'))['status'] == 'NOT_CHECKED'


def test_validation_limits():
    with pytest.raises(ValueError):
        ScienceAskRequest(question='a', max_papers=200)
    with pytest.raises(ValueError):
        ScienceAskRequest(question='12345', hypotheses=['a'] * 10)


def test_science_response_json_serializable():
    # Model objects must not leak into the serialized API payload.
    request = ScienceAskRequest(question='research question', math_tasks=[MathTask(expression='1+1')])
    assert json.loads(request.model_dump_json())['math_tasks'][0]['operation'] == 'simplify'


@pytest.mark.asyncio
async def test_uncrosschecked_literature_cannot_feed_synthesis(monkeypatch):
    def no_crossref(request):
        if request.url.host == 'api.openalex.org':
            return httpx.Response(200, json=OPENALEX_RESULT)
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_crossref)) as client:
        out = await scientific_answer(ScienceAskRequest(
            question='galaxy rotation evidence', provider='openai'), client)
    assert out['answer_status'] == 'NO_CROSSCHECKED_ABSTRACT_EVIDENCE'


def test_malicious_doi_never_admitted():
    from atlas.science import _doi
    assert _doi('https://evil.test/path') is None
    assert _doi('https://doi.org/10.1234/valid') == '10.1234/valid'
    assert _doi('10.1234/x?redirect=http://127.0.0.1') is None


def test_invalid_hypothesis_fails_schema_validation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ScienceAskRequest(question='scientific discovery', hypotheses=['z' * 101])


@pytest.mark.asyncio
async def test_model_rejects_nonexistent_citation(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace

    config = ModuleType('atlas.config')
    config.DEFAULT_MODELS = {'openai': 'test-model'}
    provider_module = ModuleType('atlas.providers')

    class ProviderError(Exception):
        pass

    class FakeProvider:
        def __init__(self, name):
            self.name = name

        async def complete(self, messages, tools, model):
            return SimpleNamespace(content='This result cites a nonexistent paper [999].')

    provider_module.NativeProvider = FakeProvider
    provider_module.ProviderError = ProviderError
    monkeypatch.setitem(sys.modules, 'atlas.config', config)
    monkeypatch.setitem(sys.modules, 'atlas.providers', provider_module)
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_scholar)) as client:
        result = await scientific_answer(ScienceAskRequest(
            question='galaxy rotation and dark matter', provider='openai'), client)
    assert result['answer_status'] == 'MODEL_OUTPUT_REJECTED'
    assert '[999]' not in result['answer']
