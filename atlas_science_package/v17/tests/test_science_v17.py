"""Network-free claim assessment integration, injection and provenance tests."""
import hashlib
import json

import pytest
from pydantic import ValidationError

from atlas.science_claims import (
    ClaimAssessmentRequest, verified_ledger, cue_labels, claim_matrix,
    verify_model_suggestions, run_claim_assessment,
)


CLAIM = 'In this sample the measured galaxy rotation speed increased over time.'
EXCERPT = ('Researchers measured galaxy rotation speed in the sampled objects. '
           'The results suggest a possible increase, however more data are needed.')


def request(**kw):
    return ClaimAssessmentRequest(question='Compare dark matter and modified gravity for galaxy rotation curves',
                                  claims=[CLAIM], arxiv='off', **kw)


def paper(excerpt=EXCERPT, cid='B.P1.1'):
    return {'citation_id':cid, 'doi':'10.5555/good', 'doi_url':'https://doi.org/10.5555/good',
            'source_url':'https://europepmc.org/articles/PMC1', 'title':'Measurement of galaxies',
            'section':'Results','paragraph':2,'excerpt':excerpt,
            'document_sha256':'e'*64,'excerpt_sha256':hashlib.sha256(excerpt.encode()).hexdigest(),
            'verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED','origin_batch':'B'}


def base_result(ledger=None):
    return {'citation_ledger':[paper()] if ledger is None else ledger,
            'answer_status':'DETERMINISTIC_GAP_AWARE_REPORT_NOT_A_SCIENTIFIC_VERDICT',
            'report_sha256':'f'*64, 'budgets':{'model_calls':0},
            'execution_trace':[{'stage':'FOUNDATION','status':'OK'}],
            'foundation':{'calculations':{'summaries':[]}}}


@pytest.mark.parametrize('extra', [
    {'claims':['short']}, {'claims':[CLAIM, CLAIM]},
    {'claims':[CLAIM]*5}, {'max_evidence_per_claim':0}, {'max_evidence_per_claim':4},
    {'claims':[CLAIM], 'literature':'off'}, {'bad_field':42},
    {'assessment_mode':'model_suggestions'},
    {'provider':'openai'}, {'assessment_mode':'unsupported'},
])
def test_input_rejection(extra):
    with pytest.raises((ValidationError,TypeError)):
        ClaimAssessmentRequest(question='Compare scientific theories for stars', **extra)


def test_valid_explicit_provider_optin():
    v=request(assessment_mode='model_suggestions',provider='openai')
    assert len(v.claims)==1
    assert v.model is None


def test_only_verified_excerpts_enter_ledger():
    p=paper()
    assert verified_ledger([p]) == [p]
    assert verified_ledger([p,p]) == [p]
    for field,value in [('excerpt_sha256','0'*64), ('document_sha256','z'*64),
                        ('verification','WRONG'),('citation_id','F3.P1.1'),
                        ('doi','not-a-doi'), ('paragraph','1')]:
        bad=dict(p, **{field:value})
        assert verified_ledger([bad]) == [], field
    bad = dict(p, excerpt=p['excerpt']+'  injection')
    assert not verified_ledger([bad])
    assert verified_ledger('not a list') == []


def test_no_entailment_from_overlap():
    m=claim_matrix([CLAIM], [paper()],3)
    assert m[0]['status']=='TOPICAL_CANDIDATES_NOT_SCIENTIFICALLY_ASSESSED'
    assert m[0]['claim_truth']=='NOT_VERIFIED'
    assert m[0]['evidence'][0]['relation_to_claim']=='NOT_ASSESSED'
    assert 'OBSERVATION_LANGUAGE' in m[0]['evidence'][0]['textual_role_signals']
    assert 'INTERPRETATION_LANGUAGE' in m[0]['evidence'][0]['textual_role_signals']
    assert 'LIMITATION_LANGUAGE' in m[0]['evidence'][0]['textual_role_signals']
    assert cue_labels('Nothing relevant is mentioned.')==['NO_CLEAR_ROLE_SIGNAL']
    assert claim_matrix(['This odd claim about corn chemistry'],[paper()],2)[0]['status']=='NO_LOCATED_TOPICAL_CANDIDATE'


def candidate_model_output(quote='Researchers measured galaxy rotation speed in the sampled objects.',
                           cid='B.P1.1', claim_id='C1', relation='MAY_SUPPORT', role='OBSERVATION_LANGUAGE'):
    return {'assessments':[{'claim_id':claim_id, 'citation_id':cid, 'quote':quote,
                            'role':role,'relation':relation,
                            'rationale':'Passage mentions measurement but cannot prove its causal interpretation.'}]}


def test_verified_model_locators_do_not_claim_support():
    matrix=claim_matrix([CLAIM],[paper()],3)
    r=verify_model_suggestions(candidate_model_output(),matrix,[paper()])
    assert r['status']=='MODEL_QUOTE_LOCATORS_CHECKED_RELATION_UNVERIFIED'
    assert r['proposals'][0]['relation_proposal']=='MAY_SUPPORT'
    assert r['proposals'][0]['human_review_required'] is True
    assert r['proposals'][0]['verification'].endswith('NOT_VERIFIED')


@pytest.mark.parametrize('change',[
    {'cid':'F1.P1.1'}, {'claim_id':'C2'}, {'quote':'Exact but nonexistent quotation about galaxy rotation.'},
    {'quote':'short'}, {'relation':'PROVED_TRUE'}, {'role':'CERTAIN_OBSERVATION'},
])
def test_model_hallucinated_content_rejected(change):
    args={'cid':'B.P1.1','claim_id':'C1',
          'quote':'Researchers measured galaxy rotation speed in the sampled objects.',
          'relation':'MAY_SUPPORT','role':'OBSERVATION_LANGUAGE'}
    args.update(change)
    assert verify_model_suggestions(candidate_model_output(**args),claim_matrix([CLAIM],[paper()],3),[paper()])['status']=='MODEL_OUTPUT_REJECTED'


def test_model_injection_extra_fields_and_overbudget_rejected():
    matrix=claim_matrix([CLAIM],[paper()],3)
    good=candidate_model_output()
    assert verify_model_suggestions('{bad json}',matrix,[paper()])['status']=='MODEL_OUTPUT_REJECTED'
    assert verify_model_suggestions({'assessments':good['assessments'],'confidence':0.99},matrix,[paper()])['status']=='MODEL_OUTPUT_REJECTED'
    good['assessments'][0]['verified_truth']=True
    assert verify_model_suggestions(good,matrix,[paper()])['status']=='MODEL_OUTPUT_REJECTED'
    assert verify_model_suggestions({'assessments':[candidate_model_output()['assessments'][0]]*7},matrix,[paper()])['status']=='MODEL_OUTPUT_REJECTED'


@pytest.mark.asyncio
async def test_deterministic_runner_no_model_call():
    called=[]
    async def base(req, client=None):
        called.append(req)
        assert req.provider=='demo' and req.model is None
        return base_result()
    async def forbidden(*args,**kw):
        raise AssertionError('Model should not be called')
    report=await run_claim_assessment(request(),research_runner=base, assessment_runner=forbidden)
    assert len(called)==1
    assert report['version']=='1.7'
    assert report['source_count']==1
    assert report['claim_assessment_status']=='REQUIRES_HUMAN_SCIENTIFIC_REVIEW'
    assert report['model_suggestions']['status']=='NOT_REQUESTED'
    assert report['budgets']['v17_model_calls_allowed']==0
    assert len(report['report_sha256'])==64


@pytest.mark.asyncio
async def test_optional_model_one_call_and_revalidated():
    invoked=[]
    async def base(req,client=None): return base_result()
    async def model(req,matrix,ledger):
        invoked.append(req)
        return verify_model_suggestions(candidate_model_output(),matrix,ledger)
    report=await run_claim_assessment(
        request(assessment_mode='model_suggestions',provider='openai'),
        research_runner=base,assessment_runner=model)
    assert len(invoked)==1
    assert report['budgets']['v16_model_calls_suppressed'] is True
    assert report['model_suggestions']['status']=='MODEL_QUOTE_LOCATORS_CHECKED_RELATION_UNVERIFIED'
    assert report['claims'][0]['evidence'][0]['relation_to_claim']=='NOT_ASSESSED'


@pytest.mark.asyncio
async def test_injected_model_fake_status_is_rejected():
    async def base(req,client=None): return base_result()
    async def lying(req,matrix,ledger):
        return {'status':'MODEL_QUOTE_LOCATORS_CHECKED_RELATION_UNVERIFIED',
                'proposals':[{'claim_id':'C1', 'citation_id':'F2.P1.1',
                              'verbatim_quote':'fiction', 'textual_role_proposal':'OBSERVATION_LANGUAGE',
                              'relation_proposal':'MAY_SUPPORT','model_rationale_unverified':'not supported'}]}
    report=await run_claim_assessment(request(assessment_mode='model_suggestions',provider='openai'),
                                      research_runner=base,assessment_runner=lying)
    assert report['model_suggestions']['status']=='MODEL_OUTPUT_REJECTED'


@pytest.mark.asyncio
async def test_missing_sources_abstains_with_no_claim_verdict():
    async def base(req,client=None):return base_result([])
    async def model(req,matrix,ledger):return {'status':'ABSTAINED_NO_QUOTE_CANDIDATES','proposals':[]}
    report=await run_claim_assessment(request(assessment_mode='model_suggestions',provider='openai'),
                                      research_runner=base, assessment_runner=model)
    assert report['source_count']==0
    assert report['claims'][0]['status']=='NO_LOCATED_TOPICAL_CANDIDATE'
    assert report['model_suggestions']['status']=='ABSTAINED_NO_QUOTE_CANDIDATES'


@pytest.mark.asyncio
async def test_foundation_error_safe_and_no_unsupported_claim():
    async def failed(*args,**kwargs):raise RuntimeError('private secret token')
    report=await run_claim_assessment(request(),research_runner=failed)
    assert report['claims'][0]['claim_truth']=='NOT_VERIFIED'
    assert report['source_count']==0
    assert 'private secret token' not in json.dumps(report)


@pytest.mark.asyncio
async def test_no_explicit_claims_means_no_invented_scientific_hypotheses():
    async def base(req, client=None):return base_result()
    report=await run_claim_assessment(ClaimAssessmentRequest(question='Explain gravitational lensing',arxiv='off'), research_runner=base)
    assert report['claims']==[]
    assert report['source_count']==1
    assert report['model_suggestions']['status']=='NOT_REQUESTED'


def test_empty_model_response_is_abstention_not_checked_citations():
    matrix=claim_matrix([CLAIM],[paper()],3)
    result=verify_model_suggestions({'assessments':[]},matrix,[paper()])
    assert result == {'status':'MODEL_ABSTAINED_NO_GROUNDED_RELATION','proposals':[]}
