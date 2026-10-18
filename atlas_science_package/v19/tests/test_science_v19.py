"""Network-free regression tests for v1.9 publication numerical-span extraction."""
import hashlib
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.science_extraction import (
    ExtractionResearchRequest, ExtractedComparison, extract_candidates,
    compare_extracted, run_extraction_research,
)


def ledger(excerpt, *, cid='B.P1.1', doi='10.1234/atlas.2026', doc='a'*64):
    return {'citation_id':cid,'doi':doi,'doi_url':'https://doi.org/'+doi,
            'source_url':'https://example.org/article','title':'Mocked primary article',
            'section':'Results','paragraph':3,'excerpt':excerpt,
            'excerpt_sha256':hashlib.sha256(excerpt.encode()).hexdigest(),
            'document_sha256':doc,'origin_batch':'B',
            'verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED'}


def request(**kwargs):
    return ExtractionResearchRequest(research_question='Find primary scientific speed measurements and predictions',**kwargs)


def selection(left,right,**kwargs):
    data={'case_id':'Q1','label':'Illustrative speeds','prediction_candidate_id':left['candidate_id'],
          'measurement_candidate_id':right['candidate_id'],'observable':'orbital speed',
          'conditions':'same radius 10 kpc','user_confirms_roles_and_context':True}
    data.update(kwargs)
    return ExtractedComparison(**data)


def sample():
    return extract_candidates([ledger('The model predicted 220 ± 10 km/s. We measured 215 ± 8 km/s.')])


def test_numeric_with_units_and_uncertainty():
    c=sample()
    assert len(c)==2
    assert [x['value'] for x in c]==['220','215']
    assert [x['printed_uncertainty'] for x in c]==['10','8']
    assert all(x['unit']=='km/s' for x in c)
    assert all(x['status']=='SOURCE_EXCERPT_SPAN_CHECKED_SCIENTIFIC_ROLE_UNVERIFIED' for x in c)
    assert all(x['uncertainty_interpretation']=='NOT_ESTABLISHED' for x in c)


def test_literal_offsets_and_hashes():
    for c in sample():
        assert c['excerpt'][slice(*c['excerpt_offset'])]==c['literal']
        assert hashlib.sha256(c['excerpt'].encode()).hexdigest()==c['excerpt_sha256']
        assert c['candidate_id'].startswith('N') and len(c['candidate_id'])==21


def test_duplicate_and_stable_candidate_ids():
    src=ledger('Measured speed 200 km/s.')
    a=extract_candidates([src,src]);b=extract_candidates([src])
    assert len(a)==1 and a==b


def test_invalid_excerpt_digest_is_rejected():
    src=ledger('Measured 200 km/s');src['excerpt_sha256']='f'*64
    assert extract_candidates([src])==[]


def test_invalid_document_digest_is_rejected():
    src=ledger('Measured 200 km/s');src['document_sha256']='junk'
    assert extract_candidates([src])==[]


def test_invalid_doi_identity_is_rejected():
    src=ledger('Measured 200 km/s');src['doi']='arxiv:12345'
    assert extract_candidates([src])==[]


def test_missing_verification_flag_is_rejected():
    src=ledger('Measured 200 km/s');src['verification']='VERIFIED_SCIENTIFIC_TRUTH'
    assert extract_candidates([src])==[]


def test_no_bare_numbers_or_years():
    assert extract_candidates([ledger('Measured 220 objects in 2025, comparison 110.')])==[]


@pytest.mark.parametrize('literal', ['220 mph', '200 Celsius', '3 N*m','3 mol','10 ft/s','100 m/s^3','7 kelvin'])
def test_unknown_or_ambiguous_units_not_extracted(literal):
    assert extract_candidates([ledger('We measured '+literal+'.')])==[]


@pytest.mark.parametrize('literal', ['NaN km/s','Infinity km/s','2e99 km/s','1e-105 km/s'])
def test_unsafe_numeric_inputs_rejected(literal):
    assert extract_candidates([ledger('Measured '+literal+'.')])==[]


def test_range_end_not_silently_extracted():
    assert extract_candidates([ledger('Reported 200–220 km/s.')])==[]


def test_percent_and_scientific_notation():
    c=extract_candidates([ledger('Measurement: 2.5e3 m/s; efficiency 12 %.')])
    assert len(c)==2
    assert [(x['value'],x['unit']) for x in c]==[('2.5E+3','m/s'),('12','%')]


def test_mixed_dimensions_are_extracted_but_not_compared():
    c=extract_candidates([ledger('Length measured 3 km and model speed 4 km/s.')])
    res=compare_extracted([selection(c[0],c[1])],c)[0]
    assert res['status']=='ABSTAINED_DIMENSION_MISMATCH'
    assert 'calculation' not in res


def test_candidate_limit():
    src=ledger('Data: '+'; '.join(f'{i} km/s' for i in range(1,9)))
    assert len(extract_candidates([src],limit=3))==3
    with pytest.raises(ValueError): extract_candidates([src],limit=25)
    with pytest.raises(ValueError): extract_candidates([src],limit=True)


def test_checked_arithmetic_after_explicit_role_confirmation():
    c=sample()
    r=compare_extracted([selection(c[0],c[1])],c)[0]
    assert r['status']=='ARITHMETIC_CHECKED_ASSUMPTIONS_UNVERIFIED'
    assert Decimal(r['calculation']['measurement_minus_prediction_si'])==Decimal('-5000')
    assert r['calculation']['standardized_residual'] is None
    assert r['scientific_validity']=='NOT_ESTABLISHED'
    assert r['source_bindings']['measurement']['literal']=='215 ± 8 km/s'
    assert r['source_transcription']=='VERBATIM_SPAN_EXTRACTED_HUMAN_CONTEXT_REQUIRED'


def test_no_automatic_uncertainty_assumption():
    c=sample()
    with pytest.raises(ValidationError):
        selection(c[0],c[1],uncertainty_model='independent_gaussian_1sigma')


def test_confirmed_uncertainty_allows_descriptive_residual():
    c=sample()
    sel=selection(c[0],c[1],uncertainty_model='independent_gaussian_1sigma',
                  user_confirms_uncertainties_gaussian_1sigma=True)
    r=compare_extracted([sel],c)[0]
    assert abs(Decimal(r['calculation']['standardized_residual'])-Decimal('0.3904344047'))<Decimal('1e-10')
    assert r['scientific_validity']=='NOT_ESTABLISHED'


def test_uncertainty_missing_fails_closed():
    c=extract_candidates([ledger('Model predicted 220 km/s, observed 215 ± 8 km/s.')])
    sel=selection(c[0],c[1],uncertainty_model='independent_gaussian_1sigma',
                  user_confirms_uncertainties_gaussian_1sigma=True)
    assert compare_extracted([sel],c)[0]['status']=='ABSTAINED_MISSING_PRINTED_UNCERTAINTY'


def test_explicit_correlated_model():
    c=sample()
    sel=selection(c[0],c[1],uncertainty_model='correlation_supplied_gaussian_1sigma',
                  user_confirms_uncertainties_gaussian_1sigma=True, correlation='0.5')
    r=compare_extracted([sel],c)[0]
    assert r['calculation']['standardized_residual'] is not None


@pytest.mark.parametrize('correlation', ['NaN','2','-2',None])
def test_correlations_rejected(correlation):
    c=sample()
    with pytest.raises(ValidationError):
        selection(c[0],c[1],uncertainty_model='correlation_supplied_gaussian_1sigma',
                  user_confirms_uncertainties_gaussian_1sigma=True, correlation=correlation)


def test_stale_candidate_lookup_abstains():
    c=sample()
    r=compare_extracted([selection(c[0],c[1])],c[:1])[0]
    assert r['status']=='ABSTAINED_UNREVIEWED_OR_MISSING_SOURCE'
    assert 'calculation' not in r


def test_user_review_is_mandatory():
    c=sample()
    with pytest.raises(ValidationError):selection(c[0],c[1],user_confirms_roles_and_context=False)


def test_same_candidate_twice_rejected():
    c=sample()
    with pytest.raises(ValidationError):selection(c[0],c[0])


def test_no_arbitrary_client_facts_or_links():
    c=sample()
    with pytest.raises(ValidationError):selection(c[0],c[1],extra_url='https://attacker.example')
    with pytest.raises(ValidationError):ExtractionResearchRequest(research_question='Find primary speed studies 2026',candidates=c)


def test_duplicate_comparison_ids_rejected():
    c=sample();a=selection(c[0],c[1])
    with pytest.raises(ValidationError):request(comparisons=[a,a])


@pytest.mark.asyncio
async def test_bounded_no_model_discovery_and_report_integrity():
    s=ledger('Predicted 220 ± 10 km/s; measured 215 ± 8 km/s.')
    async def fake_runner(params,client=None):
        assert params.provider=='demo' and params.arxiv=='off'
        assert params.max_total_papers==5 and params.max_total_primary_papers==3
        assert params.auto_decompose is False
        return {'citation_ledger':[s], 'budgets':{'max_total_papers':5},
                'execution_trace':[{'stage':'FOUNDATION'}]}
    result=await run_extraction_research(request(),research_runner=fake_runner)
    assert result['source_status']=='PRIMARY_TEXT_EXCERPTS_LOCATED'
    assert len(result['candidates'])==2
    unsigned=dict(result);digest=unsigned.pop('report_sha256')
    expected=hashlib.sha256(json.dumps(unsigned,sort_keys=True,ensure_ascii=False,
                          separators=(',', ':'),allow_nan=False).encode()).hexdigest()
    assert digest==expected
    assert result['scientific_truth']=='NOT_ESTABLISHED'


@pytest.mark.asyncio
async def test_comparison_only_uses_currently_refetched_source():
    s=ledger('The model predicted 220 ± 10 km/s and measured 215 ± 8 km/s.')
    candidates=extract_candidates([s]); sel=selection(*candidates)
    async def fake_runner(*args,**kwargs):return {'citation_ledger':[s]}
    report=await run_extraction_research(request(comparisons=[sel]),research_runner=fake_runner)
    assert report['comparisons'][0]['calculation']['measurement_minus_prediction_si']=='-5E+3'
    async def changed(*args,**kwargs):
        return {'citation_ledger':[ledger('The model predicted 230 ± 10 km/s and measured 215 ± 8 km/s.')]}
    stale=await run_extraction_research(request(comparisons=[sel]),research_runner=changed)
    assert stale['comparisons'][0]['status']=='ABSTAINED_UNREVIEWED_OR_MISSING_SOURCE'


@pytest.mark.asyncio
async def test_broken_discovery_never_promotes_client_comparison():
    c=sample();sel=selection(c[0],c[1])
    async def broken(*args,**kwargs):raise RuntimeError('private secret')
    report=await run_extraction_research(request(comparisons=[sel]),research_runner=broken)
    assert report['source_status']=='DISCOVERY_UNAVAILABLE'
    assert report['candidates']==[]
    assert report['comparisons'][0]['status']=='ABSTAINED_UNREVIEWED_OR_MISSING_SOURCE'
    assert 'private secret' not in str(report)


def test_input_limit_and_invalid_text():
    with pytest.raises(ValidationError):request(max_candidates=25)
    with pytest.raises(ValidationError):ExtractionResearchRequest(research_question='     ')
