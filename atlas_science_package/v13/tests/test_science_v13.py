"""Network-free tests for prediction conflicts, verified source anchors, and fail-closed model annotations."""
import json
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from atlas.science_theories import (ScienceAskV13Request, TheorySpec, compare_theories,
                                    conflicting_predictions, interpret_theory_evidence, scientific_answer_v13)

TEXT = ("Measurements of galaxy rotation curves show approximately flat orbital speeds "
        "in the outskirts of spiral galaxies and observational systematics need review. "
        "Independent lensing observations remain relevant to competing models of galaxy dynamics.")


def specs(first='increase', second='decrease', condition='outer spiral galaxy radii'):
    return [TheorySpec(name='Theory A', predictions=[{
        'observable': 'galaxy rotation curves', 'condition': condition,
        'expected_direction': first,
    }]), TheorySpec(name='Theory B', predictions=[{
        'observable': 'galaxy rotation curves', 'condition': condition,
        'expected_direction': second,
    }])]


def source():
    papers = [{'id': 1, 'title': 'Galaxy Rotation Curves', 'doi': '10.1234/research.100',
               'verification': {'status': 'CROSSREF_METADATA_MATCH'},
               'primary_source': {'status': 'REPOSITORY_FULLTEXT_MATCHED',
                                  'document_sha256': 'f'*64,
                                  'source_url': 'https://europepmc.org/articles/PMC111'}}]
    seg = {1: [{'section': 'Results', 'paragraph': 1, 'text': TEXT}]}
    return papers, seg


def test_conflicting_same_observable_and_stated_condition():
    found = conflicting_predictions(specs())
    assert len(found) == 1
    assert found[0]['status'] == 'POTENTIALLY_INCOMPATIBLE_PREDICTIONS'
    assert found[0]['first']['expected_direction'] == 'increase'


def test_do_not_infer_conflict_different_conditions_or_unknown():
    t = specs()
    t[1].predictions[0].condition = 'laboratory condition'
    assert conflicting_predictions(t) == []
    t = specs(condition='')
    assert conflicting_predictions(t) == []
    assert conflicting_predictions(specs('present', 'nonzero')) == []


def test_theory_input_bounds_and_no_uncontrolled_work():
    with pytest.raises(ValidationError):
        ScienceAskV13Request(question='Evaluate test signals', theories=[{'name': 'a', 'predictions': [{'observable':'x'}]}])
    with pytest.raises(ValidationError):
        ScienceAskV13Request(question='Evaluate test signals', theories=[{'name': 'Theory X', 'predictions':
                               [{'observable':'signal observable'}]*5}]*3)
    with pytest.raises(ValidationError):
        ScienceAskV13Request(question='Evaluate test signals', theories=[], interpret_theories=True)
    with pytest.raises(ValidationError):
        ScienceAskV13Request(question='Evaluate test signals', theories=specs(), interpret_theories=True, provider='demo')
    with pytest.raises(ValidationError):
        TheorySpec(name='bad', predictions=[{'observable': 'galaxy field', 'expected_direction': 'exploding'}])


def test_passage_evidence_is_topical_not_a_scientific_verdict():
    papers, seg = source()
    report, private = compare_theories(specs(), papers, seg)
    assert report['status'] == 'TOPICAL_PASSAGES_FOUND'
    assert len(report['evidence']) == 1  # Deduplicated paragraph across two predictions.
    e = report['evidence'][0]
    assert e['document_sha256'] == 'f'*64
    assert len(e['paragraph_sha256']) == 64
    assert e['excerpt'] in TEXT
    assert e['paragraph'] == 1
    assert e['verification'] == 'REPOSITORY_PARAGRAPH_LOCATED'
    assert report['theories'][0]['predictions'][0]['assessment'] == 'NOT_ASSESSED'
    assert report['theories'][0]['predictions'][0]['evidence_ids'] == ['E1']
    assert report['theories'][1]['predictions'][0]['evidence_ids'] == ['E1']
    assert private['E1'] == TEXT


def test_do_not_promote_metadata_only_abstracts_to_primary_evidence():
    papers, seg = source()
    papers[0]['primary_source']['status'] = 'NO_OPEN_ACCESS_XML'
    report, _ = compare_theories(specs(), papers, seg)
    assert report['status'] == 'NO_PRIMARY_TEXT'
    assert report['evidence'] == []
    assert all(not t['predictions'][0]['evidence_ids'] for t in report['theories'])


def test_source_without_matching_crossref_identity_is_excluded():
    papers, seg = source()
    papers[0]['verification']['status'] = 'METADATA_MISMATCH'
    report, _ = compare_theories(specs(), papers, seg)
    assert not report['evidence']


def test_irrelevant_content_stays_unassessed():
    papers, seg = source()
    different = [TheorySpec(name='Other', predictions=[{'observable': 'plasma turbulence viscosity',
                                                       'condition': 'cryogenic apparatus'}])]
    report, _ = compare_theories(different, papers, seg)
    assert report['status'] == 'NO_TOPICAL_PASSAGES'


def fake_provider(monkeypatch, response):
    config = ModuleType('atlas.config')
    config.DEFAULT_MODELS = {'openai':'model-for-testing'}
    module = ModuleType('atlas.providers')
    class ProviderError(Exception):
        pass
    class Provider:
        def __init__(self, provider):
            self.provider = provider
        async def complete(self, messages, tools, model):
            assert 'E1' in messages[1]['content']
            return SimpleNamespace(content=response)
    module.NativeProvider = Provider
    module.ProviderError = ProviderError
    monkeypatch.setitem(sys.modules, 'atlas.config', config)
    monkeypatch.setitem(sys.modules, 'atlas.providers', module)


def candidate(evidence_id='E1', quote='Measurements of galaxy rotation curves show approximately flat orbital speeds',
              theory_index=1):
    return {'assessments': [{'theory_index': theory_index, 'prediction_index':1,
                             'evidence_id': evidence_id, 'relation':'context_only',
                             'source_quote': quote,
                             'rationale': 'The paragraph mentions the observable but does not test the prediction.'}]}


@pytest.mark.asyncio
async def test_model_quote_and_source_id_validated(monkeypatch):
    papers, seg = source()
    report, private = compare_theories(specs(), papers, seg)
    fake_provider(monkeypatch, json.dumps(candidate()))
    await interpret_theory_evidence(ScienceAskV13Request(
        question='Compare galaxy rotation curves', provider='openai', theories=specs(),
        interpret_theories=True), report, private)
    assert report['model_status'] == 'MODEL_PROPOSALS_QUOTE_CHECKED_NOT_ENTAILMENT_VERIFIED'
    assert report['model_assessments'][0]['status'] == 'MODEL_PROPOSAL_NOT_INDEPENDENTLY_ENTAILED'


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [candidate('E77'), candidate(quote='A made-up invented statement'),
                                          candidate(theory_index=3)])
async def test_model_invented_citations_quotes_or_associations_rejected(monkeypatch, payload):
    papers, seg = source()
    report, private = compare_theories(specs(), papers, seg)
    fake_provider(monkeypatch, json.dumps(payload))
    await interpret_theory_evidence(ScienceAskV13Request(
        question='Compare galaxy rotation curves', provider='openai', theories=specs(),
        interpret_theories=True), report, private)
    assert report['model_status'] == 'MODEL_OUTPUT_REJECTED_OR_PROVIDER_UNAVAILABLE'
    assert report['model_assessments'] == []


@pytest.mark.asyncio
async def test_model_cannot_smuggle_markdown_or_extra_fields(monkeypatch):
    papers, seg = source()
    report, private = compare_theories(specs(), papers, seg)
    fake_provider(monkeypatch, '```json\n'+json.dumps(candidate())+'\n```')
    await interpret_theory_evidence(ScienceAskV13Request(question='Compare galaxy rotation curves',
        provider='openai', theories=specs(), interpret_theories=True), report, private)
    assert report['model_status'] == 'MODEL_OUTPUT_REJECTED_OR_PROVIDER_UNAVAILABLE'


@pytest.mark.asyncio
async def test_no_primary_sources_abstain_even_with_provider(monkeypatch):
    papers, seg = source()
    papers[0]['primary_source']['status'] = 'NO_OPEN_ACCESS_XML'
    report, private = compare_theories(specs(), papers, seg)
    await interpret_theory_evidence(ScienceAskV13Request(question='Compare galaxy rotation curves',
        provider='openai', theories=specs(), interpret_theories=True), report, private)
    assert report['model_status'] == 'ABSTAINED_NO_VERIFIED_EVIDENCE'


ARTICLE = b'''<article><front><article-meta><article-id pub-id-type="doi">10.1234/research.100</article-id>
<article-id pub-id-type="pmc">111</article-id></article-meta></front><body><sec>
<title>Results</title><p>Measurements of galaxy rotation curves show approximately flat orbital speeds
in the outskirts of spiral galaxies and observational systematics need review.
Independent lensing observations remain relevant to competing models of galaxy dynamics.</p>
</sec></body></article>'''


def mock_service(request):
    if request.url.host == 'api.openalex.org':
        return httpx.Response(200, json={'results': [{'id':'https://openalex.org/W1',
              'title':'Galaxy Rotation Curves', 'doi':'https://doi.org/10.1234/research.100',
              'publication_year':2024, 'authorships':[], 'primary_location':{},
              'abstract_inverted_index':{'Galaxy':[0],'rotation':[1],'curves':[2],'were':[3],'observed':[4]}}]})
    if request.url.host == 'api.crossref.org':
        return httpx.Response(200, json={'message':{'DOI':'10.1234/research.100',
               'title':['Galaxy Rotation Curves'], 'published':{'date-parts':[[2024]]}}})
    if request.url.path.endswith('/search'):
        return httpx.Response(200, json={'resultList':{'result':[{'doi':'10.1234/research.100',
          'title':'Galaxy Rotation Curves', 'pmcid':'PMC111', 'isOpenAccess':'Y', 'inEPMC':'Y'}]}})
    if request.url.path.endswith('/PMC111/fullTextXML'):
        return httpx.Response(200, content=ARTICLE)
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_v13_end_to_end_mocked_network_preserves_v12_math_and_passages():
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_service)) as client:
        out = await scientific_answer_v13(ScienceAskV13Request(
            question='Compare evidence on galaxy rotation curves in spiral galaxies',
            theories=specs(), math_tasks=[{'expression':'x**2 + 2*x + 1', 'operation':'differentiate'}]), client=client)
    assert out['primary_fulltext_count'] == 1
    assert out['math_checks'][0]['status'] == 'COMPUTED'
    assert out['theory_comparison_v13']['status'] == 'TOPICAL_PASSAGES_FOUND'
    assert out['theory_comparison_v13']['evidence'][0]['doi'] == '10.1234/research.100'
    assert 'segments_by_id' not in out and '_segments_sink' not in out


@pytest.mark.asyncio
async def test_v13_no_papers_never_creates_an_evidence_matrix():
    def empty(req):
        if req.url.host == 'api.openalex.org':
            return httpx.Response(200, json={'results': []})
        return httpx.Response(404)
    async with httpx.AsyncClient(transport=httpx.MockTransport(empty)) as client:
        out = await scientific_answer_v13(ScienceAskV13Request(
            question='Compare observations for alternative physical models', theories=specs()), client=client)
    assert out['theory_comparison_v13']['status'] == 'NO_PRIMARY_TEXT'
    assert out['theory_comparison_v13']['evidence'] == []
