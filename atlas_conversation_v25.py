"""ATLAS v2.5: bounded source-text acquisition + citation-grounded synthesis.

Keep v2.4.1's authoritative mathematics. The separate retrieval layer supplies
arXiv-hosted passages, provenance and diagnostics; metadata is never evidence.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import subprocess
import sys

from atlas_conversation_v22 import ChatQuery
import atlas_conversation_v22 as core
import atlas_conversation_v23 as presentation
import atlas_conversation_v24 as llm
import atlas_conversation_v241 as previous
import atlas_retrieval_v25 as retriever


def _enhance_math_view(view:dict,answer:dict)->dict:
    if not isinstance(view,dict) or view.get('kind')!='mathematics':return view
    seen=set();steps=[]
    for step in view.get('steps',[]):
        title=str(step.get('title','')).strip()
        explanation=str(step.get('explanation','')).strip()
        if explanation.casefold()==title.casefold():
            if 'gradient' in title.lower():explanation='Differentiate with respect to each variable while holding the other variable constant.'
            elif 'Hessian' in title:explanation='Take the second partial derivatives to form the matrix used in the local classification test.'
            elif 'characteristic' in title.lower():explanation='Try exponential solutions; their rates satisfy this polynomial equation.'
            elif 'initial conditions' in title.lower():explanation='Use the supplied values at x=0 to determine the integration constants.'
            else:explanation='Apply this step to obtain the next symbolic expression.'
        key=(title,step.get('latex',''))
        if key in seen:continue
        seen.add(key)
        steps.append({**step,'explanation':explanation})
    view['steps']=steps
    if answer.get('operation')=='ode':
        view['why']='Solve the constant-coefficient differential equation using its characteristic roots, then apply both initial conditions and substitute the result back into the original equation.'
    elif answer.get('operation')=='stationary_points_2d':
        view['why']='Set the gradient to zero to locate stationary points. The Hessian determines whether each nondegenerate point is a local minimum, maximum, or saddle.'
    return view


def _solve_extended_v25(task:dict)->dict:
    if len(json.dumps(task))>1500:raise ValueError('Math task too large')
    worker=Path(__file__).with_name('atlas_math_extension_v25.py')
    try:
        p=subprocess.run([sys.executable,'-I',str(worker)],input=json.dumps(task),
            text=True,capture_output=True,timeout=11,check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Math operation exceeded the time budget') from exc
    if p.returncode or len(p.stdout)>65000:raise ValueError('Math worker failed or exceeded output budget')
    try:out=json.loads(p.stdout)
    except ValueError as exc:raise ValueError('Math worker returned invalid data') from exc
    if not out.get('ok') or not isinstance(out.get('result'),dict) or out['result'].get('status')!='CHECKED':
        raise ValueError(str(out.get('error','Math task was not verified'))[:180])
    return out['result']


async def _math(query:ChatQuery)->dict:
    task=previous._extended_task(query.question.strip()) if query.math_task is None else None
    if task:
        try:
            answer=await asyncio.to_thread(_solve_extended_v25,task)
            view=_enhance_math_view(presentation.math_presentation(answer),answer)
            return {'answer':'The calculation was checked. See the formatted result and explanation.',
                'answer_status':'FORMAL_MATH_CHECKED','citation_ledger':[],'math':answer,
                'model_usage':{'calls':0},'presentation':view,'synthesis_status':'MATH_SYMPY_AUTHORITY',
                'limitations':['Supported constant-coefficient initial-value and two-variable stationary-point cases only.']}
        except (OSError,ValueError) as exc:
            return {'answer':'I could not safely complete that calculation: '+str(exc)[:200],
                    'answer_status':'MATH_NOT_CHECKED','citation_ledger':[],
                    'math':{'status':'NOT_CHECKED'},'model_usage':{'calls':0}}
    result=await previous.run_chat_v241(query)
    if isinstance(result.get('presentation'),dict) and result.get('math',{}).get('status')=='CHECKED':
        result['presentation']=_enhance_math_view(result['presentation'],result['math'])
    return result


async def run_chat_v25(query:ChatQuery)->dict:
    question=query.question.strip()
    # The original math engine remains authoritative; do not route math to network search.
    if query.math_task is not None or core._is_math_question(question,query.workspace) or previous._extended_task(question):
        return await _math(query)
    evidence=await retriever.gather(question)
    selected=evidence['citation_ledger']
    diag=evidence['diagnostics']
    model_conf=llm.model_configuration()
    narrative=None
    if selected and model_conf['enabled']:
        payload={'question':question,
                 'source_excerpts':[{'id':r['citation_id'],'title':r['title'],
                                     'excerpt':r['excerpt'][:450],
                                     'locator':r.get('source_locator','source passage')} for r in selected]}
        try:
            narrative=await asyncio.to_thread(core._invoke_model,core.SCIENCE_INSTRUCTIONS,payload,max_output_tokens=550)
            if not llm.validate_science_synthesis(narrative.get('text',''),selected):
                narrative['rejected']='CITATIONS_FORMAT_OR_NUMERICAL_CLAIMS_NOT_VALIDATED'
        except Exception as exc:
            narrative={'rejected':'PROVIDER_OR_BUDGET_UNAVAILABLE','failure_type':type(exc).__name__}
    used=bool(narrative and not narrative.get('rejected'))
    if used:
        text=narrative['text']
    elif selected:
        bullets=[f"[{r['citation_id']}] Located in *{r['title']}*: {r['excerpt'][:165]}…" for r in selected[:3]]
        text=('I located source text relevant to your question, but cannot yet provide a model-synthesized scientific conclusion. '
              'These source passages are leads for inspection, not verified interpretations:\n\n'+'\n\n'.join(bullets))
    else:
        text=('ATLAS could not locate enough relevant full-text passages from permitted sources to support an answer. '
              'This is a retrieval limitation—not evidence that the scientific literature lacks an answer.')
    if not selected and __import__('os').getenv('ATLAS_V25_LEGACY_FALLBACK','1')=='1':
        legacy=await previous.run_chat_v241(query)
        if legacy.get('citation_ledger'):
            legacy['v25_retrieval_diagnostics']=diag
            legacy['retrieval_strategy']='LEGACY_VERIFIED_SOURCE_PASSAGES'
            return legacy
    result={
        'version':'2.5','question':question,'answer':text,
        'answer_status':'MODEL_SYNTHESIS_LOCATORS_VALIDATED_NOT_ENTAILMENT' if used
          else 'SOURCE_TEXT_LOCATED_MODEL_NOT_USED' if selected else 'EVIDENCE_SUMMARY_ABSTENTION',
        'citation_ledger':selected,'available_papers':evidence['papers'],
        'research_diagnostics':{**diag,'phase':evidence['status'],'model_attempted':bool(narrative),
            'note':'Fetched repository full text is not independent scientific claim verification or peer review.'},
        'model_usage':{'calls':int(bool(narrative and 'reservation' in narrative)),
                       'model':(narrative or {}).get('model'),
                       'estimated_cost_usd':(narrative or {}).get('estimated_cost_usd'),
                       'usage':(narrative or {}).get('usage'),
                       'synthesis_status':'USED' if used else (narrative or {}).get('rejected','OFF')},
        'passage_selection':{'source_count':diag['fulltext_retrieved'],
                             'topically_ranked_count':len(selected),'method':'bounded lexical coverage and document diversity; not entailment'},
        'presentation':{'kind':'research','message':
              'Located text is provenance-backed but not independently verified scientific entailment.',
              'source_count':len(selected),'model_status':model_conf['status'],
              'source_text_status':evidence['status'],'retrieval_phase':evidence['status']},
        'synthesis_status':'SOURCE_LINKED_MODEL_NARRATIVE_NOT_ENTAILMENT_VERIFIED' if used
            else 'RESEARCH_EVIDENCE_LOCATED_MODEL_OFF' if selected else 'RESEARCH_ABSTENTION',
        'limitations':['OpenAlex discovery and arXiv-hosted full text only in this new route.',
                       'Abstracts and metadata are not treated as verified source passages.',
                       'Citation IDs and numeric-literal checks are not independent proof of each claim.']}
    return result
