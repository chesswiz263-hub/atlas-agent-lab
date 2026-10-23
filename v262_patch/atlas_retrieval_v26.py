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
import textwrap
from collections import defaultdict
from typing import Any
import httpx
import atlas_retrieval_v25 as old

MAX_QUERIES = 4
MAX_EXTRA_QUERIES = 2  # only on missing source-text coverage
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
    'cmb': ('Planck 2018 CMB power spectra temperature polarization',
            ('cosmic','microwave','cmb','anisotrop','acoustic','planck','wmap','spectrum')),
}
MOND = ('MOND galaxy rotation curves acceleration',
        ('mond','modified','newtonian','acceleration','rotation','gravity'))
NOISE = ('review','perspective','overview','modified gravity','theory of','status of','challenge to',
         'proceedings','comment on','meta-analysis','bibliometric')
OBSERVATIONAL = ('observ','measur','data','survey','results','x-ray','shear','lensing',
                 'rotation','spectrum','anisotrop','planck','wmap','velocity','empirical')
# This is a high-stakes distinction: Planck cosmic INFRARED background (CIB)
# surveys are not measurements of CMB acoustic peaks, regardless of overlap.
CIB_TITLE = re.compile(r'cosmic\s+(?:far[- ]?)?infrared\s+background|\binfrared\s+background\b|\bcib\b', re.I)
CMB_TITLE = re.compile(r'\bcmb\b|cosmic\s+microwave\s+background|\bwmap\b|'
                       r'\bplanck\b.*(?:\bcmb\b|microwave|power spectra|polarization|polarisation)', re.I)
CMB_PASSAGE = re.compile(r'\bcmb\b|cosmic\s+microwave\s+background|'
                         r'\btemperature\s+anisotrop|\bpolariz|\bpolarisation|acoustic\s+peak', re.I)
# The CMB category concerns *cosmological matter evidence*, not every
# publication analyzing microwave maps. A paper about our local velocity,
# kinematic dipole or map foregrounds does not satisfy this objective.
CMB_DISTRACTOR_TITLE = re.compile(
    r'local motion|solar system motion|peculiar velocity|kinematic dipole|'
    r'our motion|aberration|dipolar modulation|dipole anisotrop|'
    r'foreground|instrument calibrat|cosmic infrared|dust emission',re.I)
CMB_EVIDENCE_TITLE = re.compile(
    r'acoustic|power\s+spectr|\bspectra\b|likelihood|cosmological\s+paramet|'
    r'matter\s+densit|cold\s+dark\s+matter|anisotrop\w*\s+measurements?|'
    r'polariz\w*\s+(?:anisotrop|measurements?)|'
    r'polaris\w*\s+(?:anisotrop|measurements?)',re.I)
# Ranking and passage detection alone are not proof that a paper measures dark
# matter. Retain quote-by-quote screening and explicitly mark missing support.
CMB_TARGET_PASSAGE = re.compile(
    r'acoustic|peak|power\s+spectr|\bspectra\b|cosmological\s+paramet|'
    r'matter\s+densit|cold\s+dark\s+matter|\bcdm\b|\blambda.?cdm\b|'
    r'polari[sz]ation\s+anisotrop|temperature\s+anisotrop',re.I)
FALLBACK = {
    'cmb': 'Planck 2018 results V CMB power spectra likelihoods',
    'bullet_cluster': 'Bullet Cluster 1E0657 lensing X ray gas mass separation',
    'cluster_lensing': 'CLASH clusters weak strong gravitational lensing shear measurements',
    'rotation_curves': 'SPARC observed galaxy rotation curves mass discrepancy',
}


def _observational_title(work:dict,cat:str)->bool:
    title=str(work.get('title') or '')
    lower=title.lower()
    if cat == 'mond':return 'mond' in lower or 'modified newton' in lower
    if CIB_TITLE.search(title) or any(x in lower for x in ('modified gravity', 'mond', 'review', 'perspective', 'bibliometric')):
        return False
    if cat == 'cmb':
        # Planck collaboration cosmological-parameter papers may omit the
        # literal string CMB from their title; generic dipole/motion analyses
        # must not be accepted merely because they mention CMB.
        planck_parameters = ('planck' in lower and 'cosmological parameters' in lower)
        return bool((CMB_TITLE.search(title) or planck_parameters) and
                    CMB_EVIDENCE_TITLE.search(title) and
                    not CMB_DISTRACTOR_TITLE.search(title))
    if cat == 'bullet_cluster':return any(x in lower for x in ('bullet cluster','1e0657','1e 0657'))
    if cat == 'cluster_lensing':return ('lens' in lower or 'shear' in lower) and any(x in lower for x in ('cluster', 'clash'))
    if cat == 'rotation_curves':return ('rotation' in lower or 'kinematic' in lower or 'velocity' in lower) and any(x in lower for x in ('galax', 'spiral', 'disk', 'sparc'))
    return True


def _passage_is_category_specific(source:str,category:str)->bool:
    if category=='cmb':
        return (bool(CMB_PASSAGE.search(source)) and
                bool(CMB_TARGET_PASSAGE.search(source)) and
                not bool(CIB_TITLE.search(source)))
    if category=='bullet_cluster':
        lower=source.lower()
        return ('bullet' in lower or '1e0657' in lower) and ('gas' in lower or 'x-ray' in lower or 'lensing' in lower)
    return True


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
    if category == 'cmb':
        if 'planck' in title or 'wmap' in title or 'microwave' in title:score += 5
        if 'power spectra' in title or 'power spectrum' in title:score += 12
        if 'cosmological parameters' in title:score += 14
        if 'acoustic' in title:score += 9
        if CMB_DISTRACTOR_TITLE.search(title):score -= 40
    if category == 'rotation_curves' and 'rotation' in title:score += 5
    if category == 'cluster_lensing' and ('shear' in title or 'lensing' in title):score += 5
    if work.get('type') == 'article':score += 1
    return score


def _safe_failure(exc: Exception) -> str:
    # Never log exception messages or request URLs; URLs may include the API key.
    if isinstance(exc,httpx.HTTPStatusError):return 'HTTP_'+str(exc.response.status_code)
    return type(exc).__name__


def _coherent_excerpts(content:str)->list[dict]:
    """v2.6.1 readable, word-aligned passage windows with preserved PDF page labels.

    Older 510-character slicing severed words, producing the visible
    "ned from" / "llet cluster" artifacts and poor model quotations.
    """
    result=[]
    paginated='\f' in content
    for page, part in enumerate(content.replace('\r','').split('\f'),1):
        for paragraph in re.split(r'\n\s*\n+',part):
            line=' '.join(paragraph.split())
            if len(line)<95:continue
            for chunk in textwrap.wrap(line[:2800],width=480,break_long_words=False,break_on_hyphens=False):
                if len(chunk)>=110:result.append({'text':chunk,'page':page if paginated else None})
                if len(result)>=100:return result
    return result


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
    passages = _coherent_excerpts(content)
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
    if hits < 2 or not _passage_is_category_specific(source,category['category']):return -1
    score = hits/max(2,len(anchors))
    if 'observ' in source or 'measur' in source or 'data' in source:score += .16
    # Direct findings beat introductions or literature-review passages. This is
    # ranking, not source-claim entailment.
    if any(x in source for x in ('we measure', 'we find', 'we present', 'our results', 'we observe', 'we show', 'we detect')):score += .3
    if any(x in source for x in ('recently, we', 'presented a detailed', 'derived radial profiles', 'et al.')):score -= .12
    if category['category'] != 'mond' and 'mond' in source and hits<4:score -= .3
    if 'review' in title.lower():score -= .2
    if category['category']=='cmb':
        if CMB_TARGET_PASSAGE.search(source):score += .32
        if re.search(r'cold\s+dark\s+matter|matter\s+densit|\bcdm\b',source):score += .3
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
    diagnostics={'search_queries':[], 'categories_requested':[x['category'] for x in objectives],
                 'openalex_results':0,'arxiv_candidates':0,'fulltext_attempts':0,'fulltext_retrieved':0,
                 'fulltext_failures':[],'rejected_metadata':{},'rejected_passages':{},'selected_passages':0,
                 'limits':{'max_queries':MAX_QUERIES+MAX_EXTRA_QUERIES,'max_papers':MAX_PAPERS,'max_attempts':MAX_ATTEMPTS,
                           'max_download_bytes':old.MAX_BYTES,'max_pdf_pages':old.MAX_PAGES}}
    if os.getenv('ATLAS_V26_RETRIEVAL_ENABLED','1')!='1':
        diagnostics['categories_covered']=[]
        diagnostics['categories_missing']=diagnostics['categories_requested'][:]
        return {'status':'DISABLED','citation_ledger':[], 'papers':[], 'diagnostics':diagnostics}
    key_source=next((k for k in ('ATLAS_OPENALEX_API_KEY','OPENALEX_API_KEY') if os.getenv(k,'').strip()),None)
    diagnostics['openalex_key_source']=key_source or 'NOT_CONFIGURED'
    owns=client is None
    if owns:client=httpx.AsyncClient(timeout=httpx.Timeout(7,connect=3),follow_redirects=False,
                              headers={'User-Agent':'ATLAS-Research/2.6 (bounded scientific prototype)'})
    try:
        deadline=time.monotonic()+65
        bucket=defaultdict(list);found=set();unique_arxiv=set()
        by_cat=defaultdict(list); fetched={}; attempted=set(); analyzed=set()

        async def discover(objective:dict, phrase:str)->None:
            if len(diagnostics['search_queries'])>=MAX_QUERIES+MAX_EXTRA_QUERIES or time.monotonic()>deadline-18:
                return
            diagnostics['search_queries'].append(phrase)
            params={'search.title_and_abstract':phrase,'per_page':'8',
                    'select':'id,title,doi,type,publication_year,locations,primary_location,best_oa_location'}
            if key_source:params['api_key']=os.getenv(key_source).strip()
            try:
                _,_,raw=await old._bounded_get(client,old.OPENALEX,params=params,limit=1_000_000)
                works=[w for w in json.loads(raw).get('results',[])[:8] if isinstance(w,dict)]
                for w in works:found.add(w.get('id') or w.get('title'))
                ranked=[]
                for w in works:
                    ids=old.arxiv_identifiers(w)
                    if not ids or not isinstance(w.get('title'),str):continue
                    unique_arxiv.add(ids[0])
                    if not _observational_title(w,objective['category']):
                        cat=objective['category']
                        diagnostics['rejected_metadata'][cat]=diagnostics['rejected_metadata'].get(cat,0)+1
                        continue
                    ranked.append((original_score(w,objective['category']),w,ids[0]))
                # Preserve ranked candidates across the bounded targeted fallback.
                existing={aid for _,_,aid in bucket[objective['category']]}
                bucket[objective['category']].extend(row for row in ranked if row[2] not in existing)
                bucket[objective['category']].sort(key=lambda x:x[0],reverse=True)
            except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError) as exc:
                diagnostics['fulltext_failures'].append('OpenAlex '+objective['category']+': '+_safe_failure(exc))

        async def retrieve_candidates(objectives_to_try:list[dict])->None:
            # Exhaustive within the three-alternative bounded allowance per
            # category, rather than stopping at first topically wrong paper.
            for rank in range(8):
                for objective in objectives_to_try:
                    if time.monotonic()>deadline-12 or diagnostics['fulltext_attempts']>=MAX_ATTEMPTS or len(fetched)>=MAX_PAPERS:
                        return
                    cat=objective['category']
                    if by_cat[cat]:continue
                    candidates=bucket.get(cat,[])
                    if rank>=len(candidates):continue
                    _,work,aid=candidates[rank]
                    if (cat,aid) in analyzed:continue
                    if aid in fetched:
                        paper=fetched[aid]
                    elif aid in attempted:continue
                    else:
                        attempted.add(aid);diagnostics['fulltext_attempts']+=1
                        try:
                            paper=await _retrieve_work(client,work,aid)
                            fetched[aid]=paper;diagnostics['fulltext_retrieved']+=1
                        except (httpx.HTTPError,ValueError,TypeError,ImportError) as exc:
                            diagnostics['fulltext_failures'].append(cat+' '+aid+': '+_safe_failure(exc))
                            continue
                    # Crucial: a retrieved *document* is not coverage if none of
                    # its excerpts makes category-specific scientific contact.
                    compatible=any(_support_score(p['text'][:500],objective,paper['title'])>=.30 for p in paper['passages'])
                    analyzed.add((cat,aid))
                    if compatible:by_cat[cat].append(paper)
                    else:diagnostics['rejected_passages'][cat]=diagnostics['rejected_passages'].get(cat,0)+1

        for objective in objectives:
            await discover(objective,objective['query'])
        await retrieve_candidates(objectives)
        # Only request additional metadata if the original budgeted objectives
        # still lack usable full-text evidence. Prioritize the CMB gap.
        missing=[x for x in objectives if not by_cat[x['category']]]
        missing.sort(key=lambda o: (o['category']!='cmb',o['category']))
        extra_count=0
        for objective in missing:
            if extra_count>=MAX_EXTRA_QUERIES or time.monotonic()>deadline-18:break
            phrase=FALLBACK.get(objective['category'])
            if not phrase or phrase in diagnostics['search_queries']:continue
            await discover(objective,phrase)
            extra_count+=1
            # Resume attempts only if the discovery actually produced new candidates.
            await retrieve_candidates([objective])
        diagnostics['openalex_results']=len(found)
        diagnostics['arxiv_candidates']=len(unique_arxiv)
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
