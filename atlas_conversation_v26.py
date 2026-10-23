"""ATLAS 2.6 — category-balanced evidence -> bounded language model -> claim screen.

Retains v2.5 SymPy as mathematical authority and v2.4's durable API reservation,
provider opt-in, and quoted-source restrictions. Follow-up context is provided by
the existing client history (never treated as source evidence).
"""
from __future__ import annotations
import asyncio
import re
from typing import Any

from atlas_conversation_v22 import ChatQuery
import atlas_conversation_v25 as previous
import atlas_conversation_v24 as llm
import atlas_retrieval_v26 as retrieval
import atlas_claims_v26 as claims


def _bounded_history(history:list[dict]) -> list[dict]:
    """User questions are context; assistant answers are not authority."""
    return [{'role':'user','text':h['text'][:350]} for h in history[-4:]
            if isinstance(h,dict) and h.get('role')=='user' and isinstance(h.get('text'),str)]


def _reviewable_extracts(ledger:list[dict],missing:list[str])->str:
    if not ledger:
        return ('ATLAS could not retrieve citeable full-text passages for this question. '
                'This is a retrieval limitation, not a scientific conclusion.')
    samples=[];seen=set()
    for source in ledger:
        cat=source['evidence_category']
        if cat in seen:continue
        seen.add(cat)
        # Exact, source-linked excerpt with NO inferred scientific conclusion.
        excerpt=source['excerpt'][:260]
        samples.append(cat.replace('_',' ').title()+': source excerpt — “'+excerpt+'” ['+source['citation_id']+']')
    gaps=(' Evidence remains missing for '+', '.join(x.replace('_',' ') for x in missing)+'.') if missing else ''
    return ('ATLAS located passages, but a scientifically screened conversational synthesis is unavailable. '
            'These are quoted research leads, not conclusions:\n\n'+'\n\n'.join(samples)+gaps)


async def run_chat_v26(query:ChatQuery) -> dict:
    question=query.question.strip()
    if query.math_task is not None or previous.core._is_math_question(question,query.workspace) or previous.previous._extended_task(question):
        # Preserve deterministic formal checks; no academic retrieval on math queries.
        result=await previous._math(query)
        result['version']='2.6'
        return result
    history=_bounded_history(query.history)
    evidence=await retrieval.gather(question,history=history)
    ledger=evidence['citation_ledger'];diagnostics=evidence['diagnostics']
    required=diagnostics['categories_requested'];missing=diagnostics.get('categories_missing',required)
    model_conf=llm.model_configuration()
    model_result=None;validation={'accepted':[],'checks':[]};model_attempted=False
    if ledger and model_conf['enabled']:
        # Only located source text is passed as evidence. History cannot create citations.
        payload={
            'question':question,'prior_user_questions':[h['text'] for h in history[-2:]],
            'requested_categories':required,
            'evidence':[{'id':r['citation_id'],'category':r['evidence_category'],
                         'title':r['title'],'excerpt':r['excerpt'][:460],
                         'locator':r['source_locator']} for r in ledger[:8]],
        }
        model_attempted=True
        try:
            # v2.4/V2.2 wrapper reserves SQLite budget BEFORE invoking provider.
            model_result=await asyncio.to_thread(previous.core._invoke_model,
                                                   claims.INSTRUCTIONS,payload,max_output_tokens=700)
            validation=claims.check_claims(model_result.get('text',''),ledger)
        except Exception as exc:
            # Never reflect upstream credential-bearing error text in public outputs.
            model_result={'error_type':type(exc).__name__}
    accepted=validation['accepted']
    if accepted:
        answer=claims.render_answer(accepted,required,ledger)
        status='MODEL_SYNTHESIS_CLAIMS_TEXTUALLY_SCREENED_NOT_ENTAILMENT'
        synthesis_status='PARTIAL_OR_COMPLETE_TEXTUALLY_SCREENED_SYNTHESIS'
    elif ledger:
        answer=_reviewable_extracts(ledger,missing)
        status='SOURCE_TEXT_LOCATED_MODEL_NOT_USED'
        synthesis_status='EVIDENCE_LOCATED_NO_ACCEPTED_CLAIMS'
    else:
        answer=_reviewable_extracts([],missing)
        status='EVIDENCE_SUMMARY_ABSTENTION'
        synthesis_status='RESEARCH_ABSTENTION'
    accepted_categories={c['category'] for c in accepted}
    missing_claim_categories=[c for c in required if c not in accepted_categories]
    return {
        'version':'2.6','question':question,'answer':answer,'answer_status':status,
        'citation_ledger':ledger,'available_papers':evidence['papers'],
        'claim_validation':{'accepted_claims':len(accepted),'rejected_claims':sum(c['status']=='REJECTED' for c in validation['checks']),
                            'checks':validation['checks'],
                            'method':'exact excerpt quote, lexical support, numeric/negation and epistemic-class screening; NOT semantic entailment'},
        'claim_ledger':[{k:v for k,v in c.items() if k!='support_quote'} for c in accepted],
        'research_diagnostics':{**diagnostics,'phase':evidence['status'],'model_attempted':model_attempted,
                                'categories_without_accepted_claims':missing_claim_categories,
                                'note':'A source quotation or textual-support screen is not proof of scientific correctness.'},
        'model_usage':{'calls':int(bool(model_result and model_result.get('reservation'))),
                       'model':(model_result or {}).get('model'),
                       'estimated_cost_usd':(model_result or {}).get('estimated_cost_usd'),
                       'usage':(model_result or {}).get('usage'),
                       'synthesis_status':('USED' if accepted else ('NO_CLAIMS_PASSED' if model_result and model_result.get('text') else
                                             'PROVIDER_OR_BUDGET_UNAVAILABLE' if model_attempted else model_conf['status']))},
        'passage_selection':{'source_count':diagnostics.get('fulltext_retrieved',0),
                            'topically_ranked_count':len(ledger),
                            'method':'original-observation title ranking, balanced category coverage, source-text relevance'},
        'presentation':{'kind':'research', 'message':
                        'Claim-level quotation screening completed; substantive scientific entailment remains unverified.',
                        'source_count':len(ledger),'model_status':model_conf['status'],
                        'source_text_status':evidence['status'],'retrieval_phase':evidence['status']},
        'synthesis_status':synthesis_status,
        'limitations':['Citations resolve only to fetched arXiv-hosted repository copies, whose peer-review status is not verified.',
                       'Quote matching and lexical support checks cannot rule out all misinterpretations or contradictions.',
                       'Client-provided bounded history supplies context only and is not trusted as evidence.',
                       'The existing app budget ledger uses estimated charges; provider-side billing caps are separate.'],
    }
