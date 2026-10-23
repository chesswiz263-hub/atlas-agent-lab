"""ATLAS v2.6: bounded, category-balanced original-observation discovery.

Metadata is used only to *rank* candidate sources; only downloaded repository
passages may be cited. Reuses v2.5's host allowlist, redirect/byte/PDF limits.
"""
from __future__ import annotations
import asyncio
from hashlib import sha256
import json
import os
import re
import time
from collections import defaultdict
from typing import Any
import httpx
import atlas_retrieval_v25 as old

MAX_QUERIES = 4
MAX_PAPERS = 8
MAX_ATTEMPTS = 12
MAX_CITATIONS = 8
# Each category is a distinct research objective, not a mere set of keywords.
DARK_MATTER = {
    'rotation_curves': ('galaxy rotation curves measured velocities',
                        ('rotation','velocity','galax','spiral','disk','radial')),
    'cluster_lensing': ('galaxy cluster weak lensing shear',
                        ('lensing','lens','shear','cluster','mass','mapping')),
    'bullet_cluster': ('1E0657-56 Bullet Cluster lensing X-ray gas',
                       ('bullet','1e0657','lensing','x-ray','gas','offset','collision')),
    'cmb': ('Planck cosmic microwave background anisotropy power spectrum',
            ('cosmic','microwave','cmb','anisotrop','acoustic','planck','wmap','spectrum')),
}
MOND = ('MOND galaxy rotation curves acceleration',
        ('mond','modified','newtonian','acceleration','rotation','gravity'))
NOISE = ('review','perspective','overview','modified gravity','theory of','status of','challenge to',
         'proceedings','comment on','meta-analysis','bibliometric')
OBSERVATIONAL = ('observ','measur','data','survey','results','x-ray','shear','lensing',
                 'rotation','spectrum','anisotrop','planck','wmap','velocity','empirical')


def plan(question: str, history: list[dict] | None = None) -> list[dict]:
    q = question.lower()
    user_history = [h.get('text','') for h in (history or [])[-4:] if isinstance(h,dict) and h.get('role')=='user']
    context = ' '.join(user_history[-2:]).lower()
    combined = q+' '+context if re.search(r'\b(that|those|it|them|above|previous|relevant|mond)\b',q) else q
    if 'mond' in q or 'modified gravity' in q:
        # Prior evidence remains background for subject resolution, never a citable source.
        key = 'rotation_curves' if ('rotation' in combined or 'galax' in combined) else 'cluster_lensing' if ('lens' in combined or 'bullet' in combined) else 'rotation_curves'
        spec = [('mond', MOND), (key, DARK_MATTER[key])]
        return [{'category':k,'query':t[0],'anchors':t[1]} for k,t in spec]
    if 'dark matter' in combined and (any(w in combined for w in ('rotation','lensing','bullet','microwave','cmb','evidence','observ'))):
        categories = list(DARK_MATTER)
        # Explicit focused question avoids four unnecessary requests.
        named = [k for k,regex in [('rotation_curves',r'rotation|galax'),('cluster_lensing',r'lensing|shear'),('bullet_cluster',r'bullet|1e0657'),('cmb',r'microwave|cmb|planck|wmap')] if re.search(regex,q)]
        if named and not re.search(r'\b(strongest|all|four|overall|main evidence)\b',q):
            categories = named
        return [{'category':k,'query':DARK_MATTER[k][0],'anchors':DARK_MATTER[k][1]} for k in categories[:MAX_QUERIES]]
    queries = old.plan_questions(question)
    return [{'category':f'topic_{i+1}','query':s,'anchors':tuple(old.terms(s))} for i,s in enumerate(queries[:MAX_QUERIES])]


def original_score(work: dict, category: str) -> float:
    title = str(work.get('title') or '').lower()
    # Rank is a discovery heuristic, never a claim of peer review or scientific quality.
    score = sum(1.5 for marker in OBSERVATIONAL if marker in title)
    score -= sum(2.5 for marker in NOISE if marker in title)
    if category != 'mond' and ('mond' in title or 'modified gravity' in title):score -= 12
    if category == 'bullet_cluster' and ('1e 0657' in title or '1e0657' in title or 'bullet' in title):score += 8
    if category == 'cmb' and ('planck' in title or 'wmap' in title or 'microwave' in title):score += 5
    if category == 'rotation_curves' and 'rotation' in title:score += 5
    if category == 'cluster_lensing' and ('shear' in title or 'lensing' in title):score += 5
    if work.get('type') == 'article':score += 1
    return score


def _safe_failure(exc: Exception) -> str:
    # Never log exception messages or request URLs; URLs may include the API key.
    if isinstance(exc,httpx.HTTPStatusError):return 'HTTP_'+str(exc.response.status_code)
    return type(exc).__name__


async def _retrieve_work(client:httpx.AsyncClient, work:dict, aid:str) -> dict:
    html_url = 'https://arxiv.org/html/'+aid
    pdf_url = 'https://arxiv.org/pdf/'+aid
    try:
        _, content_type, body = await old._bounded_get(client,html_url)
        if 'text/html' not in content_type.lower():raise ValueError('Not arXiv HTML')
        content = old._decode_html(body)
        kind, url = 'arXiv HTML', html_url
    except (httpx.HTTPError,ValueError):
        _,_,body = await old._bounded_get(client,pdf_url)
        if not body.startswith(b'%PDF-'):raise ValueError('Invalid PDF body')
        content = await asyncio.to_thread(old._pdf_text,body)
        kind,url = 'arXiv PDF',pdf_url
    title = work.get('title') or ''
    title_tokens = old.terms(title)
    if len(title_tokens & old.terms(content[:6500])) < min(2,len(title_tokens)):
        raise ValueError('Document title not corroborated')
    passages = old._make_excerpts(content)
    if not passages:raise ValueError('No extractable passages')
    return {'title':title[:250],'doi':old.normalize_doi(work.get('doi')),
            'arxiv_id':aid, 'source_url':url, 'kind':kind, 'document_sha256':sha256(body).hexdigest(),
            'passages':passages, 'publication_year':work.get('publication_year')}


def _support_score(passage:str, category:dict, title:str) -> float:
    anchors = set(category['anchors'])
    source = passage.lower()
    p_terms = old.terms(source)
    # Require a substantive match in the *fetched passage*, not metadata alone.
    hits = sum(1 for a in anchors if a in source or a in p_terms or any(t.startswith(a) for t in p_terms))
    if hits < 2:return -1
    score = hits/max(2,len(anchors))
    if 'observ' in source or 'measur' in source or 'data' in source:score += .16
    if category['category'] != 'mond' and 'mond' in source and hits<4:score -= .3
    if 'review' in title.lower():score -= .2
    return score


def choose_passages(plan_items:list[dict], papers_by_category:dict[str,list[dict]]) -> list[dict]:
    """Diversified top citation per covered category, then bounded optional backups."""
    best_by_category={}
    for item in plan_items:
        cat=item['category']; ranked=[]
        for paper in papers_by_category.get(cat,[]):
            for index,passage in enumerate(paper['passages']):
                excerpt = passage['text'][:500]
                score = _support_score(excerpt,item,paper['title'])
                if score>=.30:ranked.append((score,paper,index,passage,excerpt))
        ranked.sort(key=lambda x:x[0],reverse=True)
        best_by_category[cat]=ranked
    selected=[];seen_hash=set();doc_counts=defaultdict(int)
    for rank in range(2):
        for item in plan_items:
            cat=item['category']
            for score,paper,index,passage,excerpt in best_by_category.get(cat,[]):
                h=sha256(excerpt.encode('utf-8')).hexdigest()
                if h in seen_hash or doc_counts[paper['arxiv_id']]>=2:continue
                # Avoid same paper being mistaken for independent category coverage.
                if rank==0 and any(rec['arxiv_id']==paper['arxiv_id'] for rec in selected):continue
                rec={'citation_id':f'A.P{len(selected)+1}', 'evidence_category':cat,
                     'title':paper['title'],'doi':paper['doi'],'arxiv_id':paper['arxiv_id'],
                     'source_url':paper['source_url'],'source_locator':
                      (f"{paper['kind']} page {passage['page']}, passage {index+1}" if passage.get('page') else f"{paper['kind']} passage {index+1}"),
                     'excerpt':excerpt,'excerpt_sha256':h,'document_sha256':paper['document_sha256'],
                     'verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED',
                     'publication_status':'ARXIV_REPOSITORY_COPY_PEER_REVIEW_NOT_VERIFIED',
                     'relevance_score':round(score,3)}
                selected.append(rec);seen_hash.add(h);doc_counts[paper['arxiv_id']]+=1
                break
            if len(selected)>=MAX_CITATIONS: return selected
    return selected


async def gather(question:str,*,history:list[dict]|None=None,client:httpx.AsyncClient|None=None)->dict:
    objectives=plan(question,history)
    diagnostics={'search_queries':[x['query'] for x in objectives], 'categories_requested':[x['category'] for x in objectives],
                 'openalex_results':0,'arxiv_candidates':0,'fulltext_attempts':0,'fulltext_retrieved':0,
                 'fulltext_failures':[], 'selected_passages':0,
                 'limits':{'max_queries':MAX_QUERIES,'max_papers':MAX_PAPERS,'max_attempts':MAX_ATTEMPTS,
                           'max_download_bytes':old.MAX_BYTES,'max_pdf_pages':old.MAX_PAGES}}
    if os.getenv('ATLAS_V26_RETRIEVAL_ENABLED','1')!='1':
        return {'status':'DISABLED','citation_ledger':[], 'papers':[], 'diagnostics':diagnostics}
    key_source=next((k for k in ('ATLAS_OPENALEX_API_KEY','OPENALEX_API_KEY') if os.getenv(k,'').strip()),None)
    diagnostics['openalex_key_source']=key_source or 'NOT_CONFIGURED'
    owns=client is None
    if owns:client=httpx.AsyncClient(timeout=httpx.Timeout(7,connect=3),follow_redirects=False,
                              headers={'User-Agent':'ATLAS-Research/2.6 (bounded scientific prototype)'})
    try:
        # Leave ample time for the protected gateway's 90-second request timeout.
        deadline=time.monotonic()+65
        bucket={};found=set()
        for objective in objectives:
            if time.monotonic()>deadline-9:
                diagnostics['fulltext_failures'].append('RETRIEVAL_TIME_BUDGET_REACHED')
                bucket[objective['category']]=[]
                continue
            params={'search.title_and_abstract':objective['query'],'per_page':'8',
                    'select':'id,title,doi,type,publication_year,locations,primary_location,best_oa_location'}
            if key_source:params['api_key']=os.getenv(key_source).strip()
            try:
                _,_,raw=await old._bounded_get(client,old.OPENALEX,params=params,limit=1_000_000)
                parsed=json.loads(raw)
                works=[w for w in parsed.get('results',[])[:8] if isinstance(w,dict)]
                for w in works:found.add(w.get('id') or w.get('title'))
                ranked=[]
                for w in works:
                    ids=old.arxiv_identifiers(w)
                    if ids and isinstance(w.get('title'),str):ranked.append((original_score(w,objective['category']),w,ids[0]))
                ranked.sort(key=lambda x:x[0],reverse=True)
                bucket[objective['category']]=ranked
            except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:
                diagnostics['fulltext_failures'].append('OpenAlex '+objective['category']+': '+_safe_failure(exc))
                bucket[objective['category']]=[]
        diagnostics['openalex_results']=len(found)
        diagnostics['arxiv_candidates']=len({x[2] for b in bucket.values() for x in b})
        # Prioritize category coverage. On failure, attempt one alternative per category.
        by_cat=defaultdict(list); fetched={}; attempted=set()
        for rank in range(3):
            for objective in objectives:
                if time.monotonic()>deadline-15:
                    diagnostics['fulltext_failures'].append('RETRIEVAL_TIME_BUDGET_REACHED')
                    break
                cat=objective['category']
                if by_cat[cat] or diagnostics['fulltext_attempts']>=MAX_ATTEMPTS or len(fetched)>=MAX_PAPERS:continue
                candidates=bucket.get(cat,[])
                if rank>=len(candidates):continue
                _,work,aid=candidates[rank]
                if aid in fetched:
                    by_cat[cat].append(fetched[aid]);continue
                if aid in attempted:continue
                attempted.add(aid);diagnostics['fulltext_attempts']+=1
                try:
                    paper=await _retrieve_work(client,work,aid)
                    fetched[aid]=paper;by_cat[cat].append(paper);diagnostics['fulltext_retrieved']+=1
                except (httpx.HTTPError,ValueError,TypeError,ImportError) as exc:
                    diagnostics['fulltext_failures'].append(cat+' '+aid+': '+_safe_failure(exc))
        ledger=choose_passages(objectives,by_cat)
        covered={r['evidence_category'] for r in ledger}
        diagnostics['categories_covered']=[x['category'] for x in objectives if x['category'] in covered]
        diagnostics['categories_missing']=[x['category'] for x in objectives if x['category'] not in covered]
        diagnostics['selected_passages']=len(ledger)
        status='PASSAGES_LOCATED' if ledger else 'NO_RELEVANT_PASSAGES' if fetched else 'FULLTEXT_UNAVAILABLE' if attempted else 'NO_ARXIV_OPENALEX_CANDIDATES'
        return {'status':status,'citation_ledger':ledger,'diagnostics':diagnostics,
                'papers':[{'title':p['title'],'arxiv_id':p['arxiv_id'],'doi':p['doi'], 'source_url':p['source_url'],
                           'version':'arXiv repository copy; peer review not verified'} for p in fetched.values()]}
    finally:
        if owns:await client.aclose()
