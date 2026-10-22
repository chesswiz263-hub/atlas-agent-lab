"""ATLAS v2.4.1: small reviewed math routes and truthful research diagnostics.

The existing evidence engine, MathML frontend, LLM pricing and quota enforcement,
authentication and science provenance checks are not altered.
"""
from __future__ import annotations
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from atlas_conversation_v22 import ChatQuery
import atlas_conversation_v23 as presentation
import atlas_conversation_v24 as v24

_MATH_PREFIX = re.compile(r'^\s*(?:evaluate|compute|find)\s+(?:the\s+)?(?:indefinite\s+)?integral\s+of\s+',re.I)
_EXPLANATORY_SUFFIX = re.compile(r'^(?:explain|show|verify|describe|discuss|include|state)\b',re.I)
_STATIONARY = re.compile(r'^\s*find\s+and\s+classify\s+all\s+stationary\s+points\s+of\s+f\(x\s*,\s*y\)\s*=\s*',re.I)
_ODE = re.compile(r'^\s*solve\s+(?:the\s+)?differential\s+equation\s+',re.I)
_ICS = re.compile(r"^\s*y\(0\)\s*=\s*([-+\w.*/^()]+)\s+and\s+y'\(0\)\s*=\s*([-+\w.*/^()]+)\s*$",re.I)


def _first_math_clause(text: str) -> str | None:
    """Get the math-only leading clause, with strict trailing teaching request.

    Does not infer math from arbitrary prose and does not relax the AST parser.
    """
    head, sep, tail = text.strip().partition('. ')
    if sep and not _EXPLANATORY_SUFFIX.match(tail):return None
    if not sep:head=text.strip().rstrip('.')
    return head.strip()


def _rewrite_indefinite_integral(text: str) -> str | None:
    from atlas_math_v23 import parse_safe
    head=_first_math_clause(text)
    if not head or not _MATH_PREFIX.match(head):return None
    expression=_MATH_PREFIX.sub('',head,count=1).strip()
    # Treat elementary e^x in teaching notation as the exponential function.
    expression=re.sub(r'(?<![\w])e\s*\^\s*([a-zA-Z])\b',r'exp(\1)',expression)
    if len(expression)>230:return None
    try:parse_safe(expression)
    except (ValueError,TypeError,SyntaxError,RecursionError):return None
    return 'Integrate '+expression


def _extended_task(text: str) -> dict[str,Any] | None:
    head=_first_math_clause(text)
    if not head:return None
    m=_STATIONARY.match(head)
    if m:
        expression=head[m.end():].strip()
        if expression and len(expression)<=230:
            return {'operation':'stationary_points_2d','expression':expression}
        return None
    m=_ODE.match(head)
    if m:
        remainder=head[m.end():]
        parts=re.split(r'\s+subject\s+to\s+',remainder,maxsplit=1,flags=re.I)
        if len(parts)!=2:return None
        conditions=_ICS.fullmatch(parts[1])
        if not conditions:return None
        return {'operation':'ode_ivp_2nd','expression':parts[0].strip(),
                'initial_y':conditions.group(1),'initial_dy':conditions.group(2)}
    return None


def _extended_subprocess(task:dict)->dict:
    if len(json.dumps(task))>1500:raise ValueError('Math extension request too long')
    proc=subprocess.run([sys.executable,'-I',str(Path(__file__).with_name('atlas_math_extension_v241.py'))],
        input=json.dumps(task),text=True,capture_output=True,timeout=11,check=False)
    if proc.returncode or len(proc.stdout)>65_000:
        raise ValueError('Math extension unavailable or exceeded resource budget')
    try:out=json.loads(proc.stdout)
    except ValueError as exc:raise ValueError('Math extension returned an invalid response') from exc
    if not out.get('ok'):
        raise ValueError(str(out.get('error','Mathematical task unsupported'))[:220])
    answer=out.get('result')
    if not isinstance(answer,dict) or answer.get('status')!='CHECKED':
        raise ValueError('Mathematics not checked')
    return answer


def _discovery_diagnostics(result:dict)->dict:
    foundation=result.get('foundation') or {}
    lit=foundation.get('literature') or {}
    arxiv=foundation.get('arxiv_discovery') or {}
    ledger=result.get('citation_ledger') or []
    selection=result.get('passage_selection') or {}
    raw_source_count=selection.get('source_count',0)
    sources_selected=selection.get('topically_ranked_count',len(ledger))
    if not raw_source_count: phase='NO_SOURCE_TEXT_LOCATED'
    elif not sources_selected: phase='SOURCE_TEXT_NOT_TOPICALLY_SELECTED'
    elif result.get('answer_status')=='MODEL_SYNTHESIS_LOCATORS_VALIDATED_NOT_ENTAILMENT':phase='SOURCE_LINKED_NARRATIVE'
    else:phase='SOURCES_LOCATED_BUT_NARRATIVE_UNAVAILABLE'
    return {
        'phase':phase,
        'literature_status':str(lit.get('status','UNKNOWN'))[:70],
        'arxiv_metadata_status':str(arxiv.get('status','UNKNOWN'))[:70],
        'located_source_passages':raw_source_count,
        'selected_source_passages':sources_selected,
        'publication_metadata_count':len((lit.get('papers') or [])),
        'used_followups':len(result.get('followups') or []),
        'decomposition_strategy':str((result.get('decomposition') or {}).get('strategy','UNKNOWN'))[:80],
        'model_attempted':bool((result.get('model_usage') or {}).get('calls')),
        'note':('Only repository-fulltext-matched passages qualify as cited evidence. '
                'arXiv abstracts and publication metadata alone are not independently located primary-source full text.'),
    }


async def run_chat_v241(query:ChatQuery)->dict:
    text=query.question.strip()
    task=_extended_task(text) if query.math_task is None else None
    if task is not None:
        try:
            answer=await asyncio.to_thread(_extended_subprocess,task)
            view=presentation.math_presentation(answer)
            return {'answer':'I solved the mathematical task and checked the result. See the formatted result and steps.',
                'answer_status':'FORMAL_MATH_CHECKED', 'citation_ledger':[], 'math':answer,
                'model_usage':{'calls':0,'math_parsing':'DETERMINISTIC_EXTENSION'},
                'presentation':view,'synthesis_status':'MATH_SYMPY_AUTHORITY',
                'limitations':['This operation is limited to the explicitly stated task family; domain assumptions and any degenerate cases require review.']}
        except (ValueError, OSError) as exc:
            return {'answer':'I could not safely complete that calculation: '+str(exc)[:200],
                'answer_status':'MATH_NOT_CHECKED', 'citation_ledger':[],
                'math':{'status':'NOT_CHECKED'}, 'model_usage':{'calls':0},
                'presentation':{'kind':'research','message':'No checked mathematical result was produced.'}}
    rewritten=_rewrite_indefinite_integral(text) if query.math_task is None else None
    if rewritten is not None:
        query=query.model_copy(update={'question':rewritten})
    result=await v24.run_chat_v24(query)
    if isinstance(result,dict) and result.get('presentation',{}).get('kind')=='research':
        diag=_discovery_diagnostics(result)
        result['research_diagnostics']=diag
        result['presentation']['retrieval_phase']=diag['phase']
        if diag['phase']=='NO_SOURCE_TEXT_LOCATED':
            result['presentation']['message']=(
                'No crosschecked full-text primary-source passages were located. '
                'Metadata-only records are research leads, not evidence for a scientific answer.')
    return result
