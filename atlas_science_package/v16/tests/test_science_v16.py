"""v1.6 network-free adversarial checks for decomposition, evidence labels, budgets."""
import hashlib
import json

import pytest
from pydantic import ValidationError

from atlas.science_decomposition import (
    DecomposedResearchRequest, _append_source_batch, _coverage,
    plan_subquestions, run_decomposed_research,
)


def req(**kwargs):
    return DecomposedResearchRequest(
        question='Compare dark matter and modified gravity predictions for galaxy rotation curves',
        arxiv='off', **kwargs,
    )


def literature(excerpt='Galaxy rotation curves are present in surveyed systems.', doi='10.1234/paper1'):
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    return {'status': 'RESULTS_FOUND', 'primary_fulltext_count': 1,
        'papers': [{'id': 1, 'title': 'Sample work', 'doi': doi, 'doi_url': 'https://doi.org/'+doi,
            'verification': {'status': 'CROSSREF_METADATA_MATCH'},
            'primary_source': {'status': 'REPOSITORY_FULLTEXT_MATCHED',
                               'source_url': 'https://europepmc.org/articles/PMC100',
                               'document_sha256': 'f'*64},
            'primary_passages': [{'citation_id': 'P1.1', 'status': 'EXACT_SOURCE_EXCERPT',
                                  'excerpt': excerpt, 'excerpt_sha256': digest,
                                  'section': 'Results', 'paragraph': 1}]}]}


def foundation(papers=None):
    return {'version':'1.5', 'literature': literature() if papers is None else papers,
            'source_index': [], 'answer':'Existing checks',
            'calculations': {'summaries': ['Symbolic 1: VERIFIED']},
            'arxiv_discovery': {'status':'NOT_REQUESTED'}, 'report_sha256':'a'*64}


@pytest.mark.parametrize('bad', [
    {'max_followups': 3}, {'max_followups': -1}, {'max_total_papers': 7},
    {'max_total_primary_papers': 5}, {'subquestions':['too short']},
    {'subquestions':['a valid physics question', 'a valid physics question']},
    {'subquestions':['What is test one?', 'What is test two?', 'What is test three?', 'What is test four?']},
    {'model':'with spaces'}, {'bad_extra': 1},
])
def test_budgets_and_invalid_input_rejected(bad):
    with pytest.raises(ValidationError): req(**bad)


def test_explicit_subquestions_require_literature():
    with pytest.raises(ValidationError):
        req(literature='off', subquestions=['Is this experiment reproducible?'])


def test_auto_split_only_literal_constrained_comparisons():
    plan = plan_subquestions(req(), discovery_enabled=True)
    assert plan['strategy'] == 'LITERAL_COMPARISON_FACETS'
    assert plan['items'][0]['query'] == 'dark matter galaxy rotation curves'
    assert plan['items'][1]['query'] == 'modified gravity predictions galaxy rotation curves'
    assert plan['items'][0]['anchor'] == 'dark matter'
    plan2 = plan_subquestions(DecomposedResearchRequest(question='What causes all turbulence patterns?'),discovery_enabled=True)
    assert not plan2['items']
    assert plan2['strategy'] == 'NO_CONFIDENT_DECOMPOSITION'


def test_explicit_user_queries_unchanged_and_math_skipped():
    questions = ['What does sample A predict about elasticity?', 'How was stress measured in sample B?']
    plan = plan_subquestions(req(subquestions=questions), discovery_enabled=True)
    assert [x['query'] for x in plan['items']] == questions
    assert all(x['origin'] == 'EXPLICIT_USER_INPUT' for x in plan['items'])
    assert not plan_subquestions(req(), discovery_enabled=False)['items']


def test_source_fingerprint_and_batch_provenance():
    ledger, seen = [], set()
    assert _append_source_batch(ledger, seen, literature(), 'B') == 1
    assert ledger[0]['citation_id'] == 'B.P1.1'
    assert ledger[0]['original_citation_id'] == 'P1.1'
    assert _append_source_batch(ledger, seen, literature(), 'F1') == 0
    assert _append_source_batch(ledger, seen, literature('Dark matter galaxy rotation curves vary.'), 'F2') == 1
    assert ledger[1]['citation_id'] == 'F2.P1.1'
    forged = literature()
    forged['papers'][0]['primary_passages'][0]['excerpt_sha256'] = '0'*64
    assert _append_source_batch(ledger, seen, forged, 'F3') == 0
    forged['papers'][0]['primary_passages'][0]['excerpt_sha256'] = hashlib.sha256(
        forged['papers'][0]['primary_passages'][0]['excerpt'].encode()).hexdigest()
    forged['papers'][0]['verification']['status'] = 'UNCHECKED'
    assert _append_source_batch(ledger, seen, forged, 'F3') == 0


def test_anchor_requires_named_theory_not_generic_context():
    question = plan_subquestions(req(), discovery_enabled=True)['items'][0]
    ledger, seen = [], set()
    _append_source_batch(ledger, seen, literature(), 'B')
    assert _coverage(question, ledger)['status'] == 'NO_VERIFIED_TOPICAL_EXCERPT'
    _append_source_batch(ledger, seen, literature('Dark matter galaxy rotation curves appear in this paragraph.'), 'F1')
    assert _coverage(question, ledger)['status'] == 'TOPICAL_EXCERPT_LOCATED_NOT_CLAIM_VERIFIED'


@pytest.mark.asyncio
async def test_two_targeted_followups_use_fixed_budgets_and_no_model():
    queries = []
    async def base(r, client=None):
        assert r.provider == 'demo'
        return foundation()
    async def targeted(r, client=None):
        queries.append((r.question, r.max_papers, r.max_primary_papers, r.provider, r.interpret_theories))
        content = 'Dark matter galaxy rotation curves are measured.' if len(queries) == 1 else 'Modified gravity predictions for galaxy rotation curves differ.'
        return literature(content, doi=f'10.1234/paper{len(queries)+1}')
    result = await run_decomposed_research(req(), base_runner=base,followup_runner=targeted)
    assert len(queries) == 2
    assert [x[1:] for x in queries] == [(2,1,'demo',False), (1,1,'demo',False)]
    # Because the global cap is 6, second follow-up receives only 1 candidate slot.
    assert queries[-1][1] == 1
    assert result['budgets']['reserved_requested_papers'] == 6
    assert result['budgets']['reserved_requested_primary_papers'] == 4
    assert result['model_interpretation']['status'] == 'NOT_REQUESTED'
    assert {x['citation_id'] for x in result['citation_ledger']} == {'B.P1.1','F1.P1.1','F2.P1.1'}
    assert result['coverage']['topically_matched'] == 2
    assert result['answer_status'] == 'DETERMINISTIC_GAP_AWARE_REPORT_NOT_A_SCIENTIFIC_VERDICT'
    assert 'not verify scientific claims' in result['answer']


@pytest.mark.asyncio
async def test_covered_question_skips_futile_followup():
    questions = ['How were galaxy rotation curves measured in samples?']
    invoked = []
    async def base(r, client=None): return foundation()
    async def targeted(*args, **kwargs): invoked.append(1); raise AssertionError('should not run')
    result = await run_decomposed_research(req(subquestions=questions),base_runner=base,followup_runner=targeted)
    assert not invoked
    assert result['budgets']['used_followup_searches'] == 0
    assert result['coverage']['labels'][0]['status'] == 'TOPICAL_EXCERPT_LOCATED_NOT_CLAIM_VERIFIED'


@pytest.mark.asyncio
async def test_budget_zero_prevents_extra_discovery():
    async def base(r, client=None): return foundation()
    async def forbidden(*args,**kwargs): raise AssertionError('unexpected lookup')
    result = await run_decomposed_research(req(max_followups=0),base_runner=base,followup_runner=forbidden)
    assert result['followups'] == []
    assert result['coverage']['total_subquestions'] == 2


@pytest.mark.asyncio
async def test_global_budget_prevents_followup_even_if_search_allowed():
    async def base(r,client=None): return foundation()
    async def forbidden(*args,**kwargs): raise AssertionError('over-budget')
    result = await run_decomposed_research(req(max_total_papers=3,max_total_primary_papers=2),
                                           base_runner=base, followup_runner=forbidden)
    assert result['followups'] == []
    assert result['budgets']['reserved_requested_papers'] == 3


@pytest.mark.asyncio
async def test_math_only_never_calls_research_services():
    r = DecomposedResearchRequest(question='Differentiate x**2 + 3*x', literature='auto', arxiv='off')
    async def base(v,client=None):
        assert v.provider == 'demo'
        assert v.question == 'Differentiate x**2 + 3*x'
        return {'literature': {'status':'NOT_REQUESTED', 'papers':[]},
                'calculations':{'summaries':['Symbolic 1: VERIFIED']}}
    async def forbidden(*args,**kwargs): raise AssertionError('network query not allowed')
    out = await run_decomposed_research(r,base_runner=base,followup_runner=forbidden)
    assert out['decomposition']['strategy'] == 'LITERATURE_DISABLED'
    assert out['budgets']['reserved_requested_papers'] == 0
    assert out['citation_ledger'] == []


@pytest.mark.asyncio
async def test_failure_omits_exception_details_and_preserves_gaps():
    async def fail(*args,**kwargs): raise RuntimeError('PRIVATE_TOKEN_secretvalue')
    out = await run_decomposed_research(req(),base_runner=fail,followup_runner=fail)
    assert 'secretvalue' not in json.dumps(out)
    assert out['coverage']['topically_matched'] == 0
    assert all(f['status']=='FOLLOWUP_UNAVAILABLE' for f in out['followups'])
    assert 'abstaining' in out['answer']


@pytest.mark.asyncio
async def test_one_explicit_model_call_after_all_queries_only():
    calls = []
    async def base(r,client=None):
        assert r.provider == 'demo'
        calls.append('base')
        return foundation()
    async def targeted(r,client=None):
        calls.append('followup')
        return literature('Dark matter galaxy rotation curves appear here.','10.1234/alt')
    async def synthesis(r,sources,checks):
        calls.append('model')
        assert r.provider == 'openai'
        assert all(s['citation_id'].startswith(('B.','F1.','F2.')) for s in sources)
        return {'status':'ABSTAINED_NO_PRIMARY_TEXT','summary':None,'cited_ids':[]}
    out = await run_decomposed_research(req(provider='openai',max_followups=1),
         base_runner=base,followup_runner=targeted,synthesis_runner=synthesis)
    assert calls == ['base','followup','model']
    assert out['budgets']['model_calls'] == 1


@pytest.mark.asyncio
async def test_fingerprint_repeatable_for_identical_offline_inputs():
    async def base(r,client=None): return foundation()
    async def missing(r,client=None): return {'status':'NO_RESULTS', 'papers':[]}
    first = await run_decomposed_research(req(),base_runner=base,followup_runner=missing)
    second = await run_decomposed_research(req(),base_runner=base,followup_runner=missing)
    assert first['report_sha256'] == second['report_sha256']
    assert len(first['report_sha256']) == 64
