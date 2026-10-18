"""Offline regression tests for v1.8 quantitative engine and source boundaries."""
import hashlib
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.science_quantitative import (
    Quantity, QuantitativeCase, QuantitativeResearchRequest, SourceQuoteCheck,
    compare_case, audit_quotes, run_quantitative_research,
)


def pair(**overrides):
    baseline = {
        'case_id':'Q1', 'label':'Example speed',
        'prediction': {'observable':'orbital speed', 'conditions':'radius 10 kpc',
                       'value':'220', 'unit':'km/s', 'standard_uncertainty':'10'},
        'measurement': {'observable':'orbital speed', 'conditions':'radius 10 kpc',
                        'value':'215000', 'unit':'m/s', 'standard_uncertainty':'8000'},
        'uncertainty_model':'independent_gaussian_1sigma',
    }
    baseline.update(overrides)
    return QuantitativeCase.model_validate(baseline)


def ledger_item():
    excerpt = 'The reported orbital speed was 215 km/s with an uncertainty estimate of 8 km/s.'
    return {'citation_id':'B.P1.1', 'doi':'10.1234/example.2026',
            'doi_url':'https://doi.org/10.1234/example.2026',
            'source_url':'https://example.org/fulltext',
            'title':'Example science article','section':'Results','paragraph':2,
            'excerpt':excerpt,'excerpt_sha256':hashlib.sha256(excerpt.encode()).hexdigest(),
            'document_sha256':'a'*64,'origin_batch':'B',
            'verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED'}


def test_exact_unit_conversion_and_sigma():
    got=compare_case(pair())
    assert got['calculation_status']=='ARITHMETIC_CHECKED_ASSUMPTIONS_UNVERIFIED'
    calc=got['calculation']
    assert calc['prediction_si']=='2.2E+5'
    assert calc['measurement_si']=='2.15E+5'
    assert Decimal(calc['measurement_minus_prediction_si'])==Decimal('-5000')
    assert abs(Decimal(calc['standardized_residual'])-Decimal('0.3904344047')) < Decimal('0.0000000001')
    assert got['scientific_validity']=='NOT_ESTABLISHED'


def test_correct_sign_for_negative_measurement():
    obj=pair(prediction={'observable':'speed', 'conditions':'standard lab', 'value':'-4', 'unit':'m/s'},
             measurement={'observable':'speed', 'conditions':'standard lab', 'value':'2', 'unit':'m/s'},
             uncertainty_model='none')
    assert Decimal(compare_case(obj)['calculation']['measurement_minus_prediction_si'])==Decimal('6')


def test_dimension_mismatch_abstains():
    obj=pair(measurement={'observable':'orbital speed','conditions':'radius 10 kpc', 'value':'215','unit':'m'}, uncertainty_model='none')
    r=compare_case(obj)
    assert r['calculation_status']=='ABSTAINED_DIMENSION_MISMATCH'
    assert 'calculation' not in r


def test_conditions_mismatch_abstains():
    obj=pair(measurement={'observable':'orbital speed', 'conditions':'radius 11 kpc', 'value':'215','unit':'km/s'}, uncertainty_model='none')
    assert compare_case(obj)['calculation_status']=='ABSTAINED_OBSERVABLE_OR_CONDITIONS_DIFFER'


def test_observable_mismatch_abstains():
    obj=pair(measurement={'observable':'radial speed','conditions':'radius 10 kpc', 'value':'215','unit':'km/s'}, uncertainty_model='none')
    assert compare_case(obj)['calculation_status']=='ABSTAINED_OBSERVABLE_OR_CONDITIONS_DIFFER'


def test_case_insensitive_normalization_only():
    obj=pair(measurement={'observable':'  ORBITAL  SPEED  ','conditions':'RADIUS   10 KPC','value':'220000','unit':'m/s'}, uncertainty_model='none')
    assert compare_case(obj)['calculation_status']=='ARITHMETIC_CHECKED_ASSUMPTIONS_UNVERIFIED'


def test_uncertainty_not_automatically_interpreted():
    obj=pair(uncertainty_model='none')
    result=compare_case(obj)
    assert result['calculation']['standardized_residual'] is None
    assert 'No statistical comparison' in result['limitations'][0]


def test_missing_uncertainty_rejected_with_model():
    with pytest.raises(ValidationError):
        pair(measurement={'observable':'orbital speed','conditions':'radius 10 kpc', 'value':'215','unit':'km/s'})


def test_negative_uncertainty_rejected():
    with pytest.raises(ValidationError):
        pair(prediction={'observable':'orbital speed','conditions':'radius 10 kpc', 'value':'220','unit':'km/s', 'standard_uncertainty':'-4'})

@pytest.mark.parametrize('unit', ['mph', 'degC', 'm**2', 'N*m', '', 'm/s\n0'])
def test_unsafe_or_ambiguous_units_rejected(unit):
    with pytest.raises(ValidationError):
        pair(prediction={'observable':'orbital speed','conditions':'radius 10 kpc', 'value':'220','unit':unit})

@pytest.mark.parametrize('value', ['NaN','Infinity','-Infinity','1e300'])
def test_nonfinite_or_unbounded_values_rejected(value):
    with pytest.raises(ValidationError):
        pair(prediction={'observable':'orbital speed','conditions':'radius 10 kpc', 'value':value,'unit':'km/s'})


def test_correlation_must_be_explicit_bounded():
    with pytest.raises(ValidationError):pair(correlation='0.5')
    with pytest.raises(ValidationError):pair(uncertainty_model='correlation_supplied_gaussian_1sigma', correlation='1.2')
    with pytest.raises(ValidationError):pair(uncertainty_model='correlation_supplied_gaussian_1sigma')


def test_perfect_correlated_equal_uncertainty_gives_zero():
    obj=pair(uncertainty_model='correlation_supplied_gaussian_1sigma', correlation='1',
             measurement={'observable':'orbital speed','conditions':'radius 10 kpc',
                          'value':'215','unit':'km/s','standard_uncertainty':'10'})
    calc=compare_case(obj)['calculation']
    assert calc['combined_standard_uncertainty_si']=='0'
    assert calc['standardized_residual'] is None


def test_anticorrelated_uncertainty_adds():
    obj=pair(uncertainty_model='correlation_supplied_gaussian_1sigma', correlation='-1',
             measurement={'observable':'orbital speed','conditions':'radius 10 kpc',
                          'value':'215','unit':'km/s','standard_uncertainty':'10'})
    assert Decimal(compare_case(obj)['calculation']['combined_standard_uncertainty_si'])==20000


def test_paper_quote_exact_match_is_only_locator():
    s=ledger_item()
    request=SourceQuoteCheck(case_id='Q1',side='measurement',citation_id='B.P1.1',exact_quote=s['excerpt'][:45])
    audit=audit_quotes([request],[s])[0]
    assert audit['status']=='VERBATIM_QUOTE_LOCATED_NUMERIC_TRANSCRIPTION_UNVERIFIED'
    assert audit['numerical_value_extracted_or_verified'] is False


def test_fake_document_hash_rejected():
    s=ledger_item();s['document_sha256']='not-a-real-hash'
    link=SourceQuoteCheck(case_id='Q1',side='prediction',citation_id='B.P1.1',exact_quote=s['excerpt'][:45])
    assert audit_quotes([link],[s])[0]['status']=='NO_VERIFIED_QUOTE_MATCH'


def test_forged_excerpt_digest_rejected():
    s=ledger_item();s['excerpt_sha256']='0'*64
    link=SourceQuoteCheck(case_id='Q1',side='prediction',citation_id='B.P1.1',exact_quote=s['excerpt'][:45])
    assert audit_quotes([link],[s])[0]['status']=='NO_VERIFIED_QUOTE_MATCH'


def test_invented_citation_rejected():
    s=ledger_item()
    link=SourceQuoteCheck(case_id='Q1',side='measurement',citation_id='F2.P3.2',exact_quote=s['excerpt'][:45])
    assert audit_quotes([link],[s])[0]['status']=='NO_VERIFIED_QUOTE_MATCH'


def test_wrong_quote_rejected_even_when_id_matches():
    s=ledger_item()
    link=SourceQuoteCheck(case_id='Q1',side='measurement',citation_id='B.P1.1',exact_quote='A fabricated but sufficiently long quotation')
    assert audit_quotes([link],[s])[0]['status']=='NO_VERIFIED_QUOTE_MATCH'


def test_user_supplied_source_without_discovery_denied():
    with pytest.raises(ValidationError):
        QuantitativeResearchRequest(comparisons=[pair()],source_checks=[{'case_id':'Q1','side':'measurement',
             'citation_id':'B.P1.1','exact_quote':'A quote that is long enough for validation'}])


def test_duplicate_case_ids_rejected():
    with pytest.raises(ValidationError):QuantitativeResearchRequest(comparisons=[pair(),pair()])


def test_nonexistent_source_case_rejected():
    with pytest.raises(ValidationError):
        QuantitativeResearchRequest(comparisons=[pair()],research_question='Research some measurement literature',
          source_checks=[{'case_id':'Q2','side':'measurement','citation_id':'B.P1.1','exact_quote':'Sufficiently long cited exact quote'}])


def test_duplicate_source_case_side_rejected():
    ref={'case_id':'Q1','side':'measurement','citation_id':'B.P1.1','exact_quote':'Sufficiently long cited exact quote'}
    with pytest.raises(ValidationError):
        QuantitativeResearchRequest(comparisons=[pair()],research_question='Research some measurement literature',source_checks=[ref,ref])


def test_extra_fields_denied():
    with pytest.raises(ValidationError):QuantitativeResearchRequest(comparisons=[pair()],provider='openai')


@pytest.mark.asyncio
async def test_math_only_does_not_call_research():
    async def no_network(*args,**kwargs):
        raise AssertionError('Network research must never run without explicit question')
    data=await run_quantitative_research(QuantitativeResearchRequest(comparisons=[pair()]),research_runner=no_network)
    assert data['source_audit']['status']=='NOT_REQUESTED'
    assert data['report_sha256']
    unsigned=dict(data);del unsigned['report_sha256']
    raw=json.dumps(unsigned,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False)
    assert hashlib.sha256(raw.encode()).hexdigest()==data['report_sha256']


@pytest.mark.asyncio
async def test_source_research_no_model_and_quote_checked():
    s=ledger_item()
    async def fake_runner(params,client=None):
        assert params.provider=='demo'
        assert params.max_followups==1
        assert params.max_total_papers==5
        assert params.arxiv=='off'
        return {'citation_ledger':[s], 'budgets':{'max_total_papers':5},
                'execution_trace':[{'stage':'FOUNDATION'}]}
    req=QuantitativeResearchRequest(comparisons=[pair()],research_question='Research primary source speed literature',
        source_checks=[SourceQuoteCheck(case_id='Q1',side='measurement',citation_id='B.P1.1',exact_quote=s['excerpt'][:45])])
    data=await run_quantitative_research(req,research_runner=fake_runner)
    assert data['source_audit']['status']=='SOURCE_TEXT_CANDIDATES_LOCATED'
    assert data['source_audit']['quotes'][0]['status']=='VERBATIM_QUOTE_LOCATED_NUMERIC_TRANSCRIPTION_UNVERIFIED'
    assert 'scientific_validity' in data['cases'][0]


@pytest.mark.asyncio
async def test_research_failure_does_not_turn_into_positive_citation():
    async def broken_runner(*args,**kwargs):
        raise RuntimeError('token secret or arbitrary malicious error')
    req=QuantitativeResearchRequest(comparisons=[pair()],research_question='Research published galaxy rotation measurements')
    report=await run_quantitative_research(req,research_runner=broken_runner)
    assert report['source_audit']['status']=='SOURCE_DISCOVERY_UNAVAILABLE'
    assert 'token secret' not in json.dumps(report)
    assert report['cases'][0]['calculation_status']=='ARITHMETIC_CHECKED_ASSUMPTIONS_UNVERIFIED'


@pytest.mark.asyncio
async def test_stale_quote_cannot_be_accepted_from_wrong_run():
    s=ledger_item()
    async def fake_runner(params,client=None):
        return {'citation_ledger':[], 'execution_trace':[], 'budgets':{}}
    req=QuantitativeResearchRequest(comparisons=[pair()],research_question='Research primary source speed literature',
        source_checks=[SourceQuoteCheck(case_id='Q1',side='measurement',citation_id='B.P1.1',exact_quote=s['excerpt'][:45])])
    result=await run_quantitative_research(req,research_runner=fake_runner)
    assert result['source_audit']['quotes'][0]['status']=='NO_VERIFIED_QUOTE_MATCH'
