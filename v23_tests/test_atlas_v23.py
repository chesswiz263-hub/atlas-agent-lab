"""ATLAS v2.3: symbolic fidelity, readable presentation and source boundaries."""
import asyncio
from xml.etree import ElementTree as ET

import pytest

from atlas_conversation_v22 import ChatQuery
from atlas_conversation_v23 import (
    _math_subprocess_v23, math_presentation, run_chat_v23,
    SCIENCE_V23_INSTRUCTIONS,
)
from atlas_math_v23 import solve_task, parse_safe


def test_full_integration_by_parts_natural_language(monkeypatch):
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    res=asyncio.run(run_chat_v23(ChatQuery(question='Integrate x^2 * sin(x) and explain each step',workspace='math')))
    assert res['answer_status']=='FORMAL_MATH_CHECKED'
    assert res['math']['result']=='-x**2*cos(x) + 2*x*sin(x) + 2*cos(x) + C'
    view=res['presentation']
    assert view['kind']=='mathematics'
    assert 'x^{2}' in view['result_latex']
    assert '<msup>' in view['result_mathml']
    assert 'lower' in view['why'].lower() and '2 → 1 → 0' in view['why']
    assert sum('Apply integration by parts' in step['title'] for step in view['steps']) == 2
    assert not any('Find an antiderivative and differentiate' in step['explanation'] for step in view['steps'])
    assert 'differentiat' in view['verification'].lower()
    assert res['model_usage']['calls']==0


def test_mathml_parseable_no_non_xml_entities():
    ans=solve_task({'operation':'integrate','expression':'x^2*sin(x)','variable':'x'})
    formula=ans['result_mathml']
    root=ET.fromstring('<math>'+formula+'</math>')
    assert root.find('.//msup') is not None
    for step in ans['steps']:
        if step.get('mathml'):
            ET.fromstring('<math>'+step['mathml']+'</math>')


@pytest.mark.parametrize('task,marker',[ 
    ({'operation':'differentiate','expression':'x^2'},'<msup>'),
    ({'operation':'definite_integral','expression':'x^2','bounds':[['x','0','1']]},'<mfrac>'),
    ({'operation':'gradient','expression':'x^2+y^2+z^2'},'<mtable>'),
    ({'operation':'limit','expression':'sin(x)/x','point':'0'},'<mn>1</mn>'),
    ({'operation':'solve','expression':'x^2-4=0'},'<mn>2</mn>'),
])
def test_common_math_latex_and_mathml(task,marker):
    answer=_math_subprocess_v23(task)
    assert answer['status']=='CHECKED'
    assert marker in answer['result_mathml'] or any(marker in step.get('mathml','') for step in answer['steps'])
    ET.fromstring('<math>'+answer['result_mathml']+'</math>')


def test_restricted_parser_preserved():
    for attack in ("__import__('os').system('whoami')", 'x.__class__', '(lambda x:x)(3)'):
        with pytest.raises((ValueError,SyntaxError,TypeError)):
            parse_safe(attack)


def test_scientific_synthesis_prompt_contains_provenance_limits():
    assert 'ONLY the provided' in SCIENCE_V23_INSTRUCTIONS
    assert 'UNTRUSTED DATA' in SCIENCE_V23_INSTRUCTIONS
    assert 'NOT independent' in SCIENCE_V23_INSTRUCTIONS
    assert 'citation ID' in SCIENCE_V23_INSTRUCTIONS


def test_math_model_disabled_never_called(monkeypatch):
    import atlas_conversation_v23 as v23
    monkeypatch.setenv('ATLAS_LLM_ENABLED','0')
    monkeypatch.setenv('ATLAS_LLM_MATH_EXPLAIN','1')
    monkeypatch.setattr(v23.base,'_invoke_model',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Unexpected billed model call')))
    output=asyncio.run(v23.run_chat_v23(ChatQuery(question='Differentiate x^2',workspace='math')))
    assert output['presentation']['kind']=='mathematics'
    assert output['model_usage']['calls']==0


def test_research_abstention_preserved(monkeypatch):
    import atlas_conversation_v23 as v23
    async def fake_research(query):
        return {'answer':'No reliable passage available.','answer_status':'EVIDENCE_SUMMARY_ABSTENTION',
                'citation_ledger':[],'model_usage':{'calls':0}}
    monkeypatch.setattr(v23.base,'run_chat',fake_research)
    result=asyncio.run(v23.run_chat_v23(ChatQuery(question='Assess the evidence for a new hypothesis',workspace='research')))
    assert result['answer']=='No reliable passage available.'
    assert result['presentation']['kind']=='research'
    assert result['citation_ledger']==[]


def test_optional_math_model_only_polishes_introduction(monkeypatch):
    import atlas_conversation_v23 as v23
    monkeypatch.setenv('ATLAS_LLM_ENABLED','1')
    monkeypatch.setenv('ATLAS_LLM_MATH_EXPLAIN','1')
    monkeypatch.setattr(v23.base,'_invoke_model',lambda *args,**kwargs:
        {'text':'Because the polynomial gets simpler when differentiated, integrating by parts makes each following integral easier.',
         'estimated_cost_usd':0.001, 'reservation':'fake-test'})
    answer=asyncio.run(v23.run_chat_v23(ChatQuery(question='Integrate x^2*sin(x)',workspace='math')))
    assert answer['math']['result'].startswith('-x**2*cos(x)')
    assert 'tutor_note' in answer['presentation']
    assert 'MODEL_NARRATIVE_NOT_MATHEMATICALLY_VERIFIED' == answer['presentation']['tutor_note_status']
    assert answer['model_usage']['calls']==1


def test_research_citation_per_sentence_rejects_uncited_claim():
    from atlas_conversation_v23 import _validated_science_sentences
    records=[{'citation_id':'B.P1.1', 'excerpt':'An existing source contains relevant primary text.'}]
    assert _validated_science_sentences('The located passage addresses the subject. [B.P1.1]', records)
    assert not _validated_science_sentences('An unrelated factual claim was asserted without attribution. A different claim has a citation. [B.P1.1]', records)
