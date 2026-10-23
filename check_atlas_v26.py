"""Optional live acceptance probe. Makes OpenAlex/arXiv requests and, if opted in,
ONE budget-reserved model call. Prints no key, source text, or upstream URL params.
Run explicitly from an environment configured exactly like the hosted server.
"""
from __future__ import annotations
import asyncio
import json
from atlas_conversation_v22 import ChatQuery
from atlas_conversation_v26 import run_chat_v26
from atlas_conversation_v24 import model_configuration

QUESTION=('What is the strongest observational evidence for dark matter? Discuss '
          'galaxy rotation curves, gravitational lensing, the Bullet Cluster, and '
          'cosmic microwave background measurements. Explain what each observation '
          'establishes, cite primary scientific publications, and distinguish '
          'measured evidence from theoretical interpretation.')

async def main():
    result=await run_chat_v26(ChatQuery(question=QUESTION,workspace='research'))
    info=result.get('research_diagnostics',{})
    claim_categories={x['category'] for x in result.get('claim_ledger',[])}
    requested=info.get('categories_requested',[])
    report={
        'version':result.get('version'), 'answer_status':result.get('answer_status'),
        'categories_requested':requested,
        'source_categories_covered':info.get('categories_covered',[]),
        'source_categories_missing':info.get('categories_missing',[]),
        'claim_categories_covered':sorted(claim_categories),
        'claim_categories_missing':[x for x in requested if x not in claim_categories],
        'citations_located':len(result.get('citation_ledger',[])),
        'accepted_claims':result.get('claim_validation',{}).get('accepted_claims',0),
        'rejected_claims':result.get('claim_validation',{}).get('rejected_claims',0),
        'model_status':model_configuration().get('status'),
        'estimated_app_model_cost_usd':result.get('model_usage',{}).get('estimated_cost_usd'),
        'textual_coverage_pass':bool(requested) and all(x in claim_categories for x in requested),
        'human_scientific_review_required':True,
        'warning':'A passing quotation screen is not a semantic-entailment or peer-review guarantee.',
    }
    print(json.dumps(report,indent=2))
    return int(not report['textual_coverage_pass'])

if __name__=='__main__':raise SystemExit(asyncio.run(main()))
