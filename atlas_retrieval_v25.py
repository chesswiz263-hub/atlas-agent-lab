"""ATLAS v2.5 bounded open scholarly retrieval.

No generated citations. Every citation must point to a fetched arXiv-hosted full-text
passage; discovery metadata, abstracts and snippets do not qualify. This module
makes no model calls and does not claim scientific entailment or peer review.
"""
from __future__ import annotations
import asyncio
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

OPENALEX = 'https://api.openalex.org/works'
ARXIV_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7})(?:v\d+)?',re.I)
TOKENS = re.compile(r'[a-z][a-z0-9-]{2,}',re.I)
STOPWORDS=set('what why when where with how that this have has were are was from which their and the not but into strongest evidence observations scientific provide discuss cite papers published primary explain establish identify compare observational measurements theoretical interpretation competing uncertainties include sources based about please limitations original cite'.split())
MAX_QUERIES=4
MAX_WORKS=16
MAX_PAPERS=4
MAX_BYTES=4_000_000
MAX_PAGES=8


def terms(text:str)->set[str]:
    return {t.lower() for t in TOKENS.findall(text) if t.lower() not in STOPWORDS}


def plan_questions(question:str)->list[str]:
    """Transparent deterministic, question-anchored plans. Never LLM-invent topics."""
    q=question.lower()
    if 'dark matter' in q and ('rotation' in q or 'bullet cluster' in q or 'microwave' in q):
        return ['galaxy rotation curves dark matter',
                'Bullet Cluster weak gravitational lensing baryons',
                'cosmic microwave background cold dark matter acoustic peaks',
                'modified gravity MOND galaxy rotation curves'][:MAX_QUERIES]
    if 'mond' in q and ('lambda' in q or 'lcdm' in q or 'modified gravity' in q):
        return ['MOND galaxy rotation curves evidence',
                'Lambda CDM cosmic microwave background dark matter',
                'Bullet Cluster MOND gravitational lensing',
                'relativistic modified gravity cosmological constraints']
    # Limit to words present in the user's question; compact rather than literal long query.
    chunks=re.split(r'[?;:]|,\s*|\s+and\s+', question)
    variants=[]
    for chunk in chunks:
        words=[w.lower() for w in TOKENS.findall(chunk) if w.lower() not in STOPWORDS]
        if len(words)>=2:
            variants.append(' '.join(words[:7]))
    if not variants:
        variants=[' '.join(list(dict.fromkeys(w.lower() for w in TOKENS.findall(question) if w.lower() not in STOPWORDS))[:7])]
    result=[]
    for v in variants:
        if v.strip() and v not in result:result.append(v)
        if len(result)>=MAX_QUERIES:break
    return result


def arxiv_identifiers(work:dict[str,Any])->list[str]:
    """Only extract IDs from explicit arxiv.org URLs supplied by OpenAlex."""
    locations=[work.get('best_oa_location'),work.get('primary_location')]+(work.get('locations') or [])
    ids=[]
    for location in locations:
        if not isinstance(location,dict):continue
        for key in ('landing_page_url','pdf_url'):
            url=location.get(key)
            if not isinstance(url,str):continue
            p=urlparse(url)
            if p.scheme!='https' or (p.hostname or '').lower() not in {'arxiv.org','www.arxiv.org','export.arxiv.org'}:continue
            if not p.path.startswith(('/abs/','/pdf/','/html/')):continue
            suffix=p.path.split('/',2)[2].removesuffix('.pdf')
            if ARXIV_ID.fullmatch(suffix) and suffix not in ids:ids.append(suffix)
    return ids[:2]


def normalize_doi(doi:Any)->str|None:
    if not isinstance(doi,str):return None
    doi=re.sub(r'^https?://(?:dx\.)?doi\.org/','',doi,flags=re.I)
    return doi if re.fullmatch(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+',doi) else None


def _decode_html(raw:bytes)->str:
    class Reader(HTMLParser):
        def __init__(self):super().__init__();self.parts=[];self.skip=0
        def handle_starttag(self,t,a):
            if t in ('script','style','nav','header','footer'):self.skip+=1
            if t in ('p','div','article','section','h1','h2','h3','li') and self.skip==0:self.parts.append('\n\n')
        def handle_endtag(self,t):
            if t in ('script','style','nav','header','footer') and self.skip:self.skip-=1
            if t in ('p','section','li') and self.skip==0:self.parts.append('\n\n')
        def handle_data(self,t):
            if not self.skip:self.parts.append(t)
    reader=Reader();reader.feed(raw.decode('utf-8','replace'))
    return ''.join(reader.parts)


def _pdf_text(raw:bytes)->str:
    from pypdf import PdfReader
    pdf=PdfReader(BytesIO(raw),strict=True)
    if len(pdf.pages)>120:raise ValueError('PDF page budget exceeded')
    pieces=[]
    for p in pdf.pages[:MAX_PAGES]:
        try:pieces.append(p.extract_text(extraction_mode='plain') or '')
        except Exception:continue
    return '\f'.join(pieces)[:75_000]


def _make_excerpts(content:str)->list[dict]:
    """Page-located extracts for PDFs, ordered passage locators for HTML."""
    output=[]
    for page,part in enumerate(content.replace('\r','').split('\f'),1):
        part=re.sub(r'[\t ]+',' ',part)
        for paragraph in re.split(r'\n\s*\n+',part):
            line=' '.join(paragraph.split())
            if len(line)<95:continue
            for j in range(0,min(len(line),2200),510):
                chunk=line[j:j+510]
                if 110<=len(chunk)<=510:output.append({'text':chunk,'page':page if '\f' in content else None})
            if len(output)>=100:break
        if len(output)>=100:break
    return output


def select_evidence(question:str,queries:list[str],papers:list[dict])->list[dict]:
    ranked=[]
    qsets=[terms(q) for q in queries]
    for p in papers:
        title=p['title']
        for i,passage in enumerate(p['passages']):
            chunk=passage['text']
            cterms=terms(chunk)
            scores=[len(cterms & qs)/max(1,len(qs)) for qs in qsets]
            if not scores or max(scores)<0.20 or len(cterms & set.union(*qsets))<2:continue
            scored=max(scores) + .08*len(cterms & terms(question))
            ranked.append((scored,p,i,chunk,scores.index(max(scores)),passage['page']))
    ranked.sort(key=lambda x:x[0],reverse=True)
    selected=[];doc_count=Counter();query_count=Counter();seen=set()
    for score,p,i,chunk,qidx,page in ranked:
        if doc_count[p['arxiv_id']]>=2 or query_count[qidx]>=2:continue
        digest=sha256(chunk.encode()).hexdigest()
        if digest in seen:continue
        seen.add(digest);doc_count[p['arxiv_id']]+=1;query_count[qidx]+=1
        selected.append({'citation_id':f'A.P{len(selected)+1}', 'title':p['title'],
            'doi':p.get('doi'),'arxiv_id':p['arxiv_id'], 'source_url':p['url'],
            'excerpt':chunk[:500], 'source_locator':f"{p['kind']} page {page}, passage {i+1}" if page else f"{p['kind']} passage {i+1}",
            'document_sha256':p['document_sha256'],'excerpt_sha256':digest,
            'verification':'SOURCE_TEXT_LOCATED_CLAIM_NOT_ENTAILED',
            'publication_status':'ARXIV_REPOSITORY_COPY_PEER_REVIEW_NOT_VERIFIED',
            'matched_query':queries[qidx],'relevance_score':round(score,3)})
        if len(selected)>=6:break
    return selected


async def _bounded_get(client:httpx.AsyncClient,url:str,*,params:dict|None=None,limit:int=MAX_BYTES)->tuple[int,str,bytes]:
    """Reject redirects; cap bytes while streaming, not after allocation."""
    body=bytearray()
    async with client.stream('GET',url,params=params,follow_redirects=False) as response:
        if 300<=response.status_code<400:raise ValueError('Redirect disallowed')
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body)>limit:raise ValueError('Remote response exceeds byte budget')
        return response.status_code,response.headers.get('content-type',''),bytes(body)


async def gather(question:str,*,client:httpx.AsyncClient|None=None)->dict:
    queries=plan_questions(question)
    diagnostics={'search_queries':queries, 'openalex_results':0,'arxiv_candidates':0,
        'fulltext_attempts':0,'fulltext_retrieved':0,'fulltext_failures':[],
        'selected_passages':0,'limits':{'max_queries':MAX_QUERIES,'max_papers':MAX_PAPERS,
                                       'max_download_bytes':MAX_BYTES,'max_pdf_pages':MAX_PAGES}}
    if os.getenv('ATLAS_V25_RETRIEVAL_ENABLED','1')!='1':
        return {'status':'DISABLED','citation_ledger':[],'diagnostics':diagnostics,'papers':[]}
    own=client is None
    if own:
        client=httpx.AsyncClient(timeout=httpx.Timeout(7,connect=3),follow_redirects=False,
                                 headers={'User-Agent':'ATLAS-Research/2.5 (bounded academic prototype)'})
    try:
        results=[];seen=set();buckets=[]
        for phrase in queries:
            params={'search.title_and_abstract':phrase,'per_page':'4','select':'id,title,doi,locations,primary_location,best_oa_location'}
            key=os.getenv('ATLAS_OPENALEX_API_KEY','').strip()
            if key:params['api_key']=key
            try:
                _,_,raw=await _bounded_get(client,OPENALEX,params=params,limit=1_000_000)
                obj=__import__('json').loads(raw)
                bucket=[]
                for item in obj.get('results',[])[:4]:
                    if isinstance(item,dict):bucket.append(item)
                buckets.append(bucket)
            except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:
                diagnostics['fulltext_failures'].append('OpenAlex search failed: '+type(exc).__name__)
                buckets.append([])
        # Rotate search results across subquestions, preventing the first query
        # from taking every retrieval slot. Deduplicate by arXiv identifier.
        candidates=[];seen_arxiv=set()
        for rank in range(4):
            for bucket in buckets:
                if rank>=len(bucket):continue
                work=bucket[rank]
                if work.get('id') not in seen:
                    seen.add(work.get('id'));results.append(work)
                ids=arxiv_identifiers(work)
                if ids and ids[0] not in seen_arxiv and isinstance(work.get('title'),str):
                    seen_arxiv.add(ids[0]);candidates.append((work,ids[0]))
                if len(results)>=MAX_WORKS:break
            if len(results)>=MAX_WORKS:break
        diagnostics['openalex_results']=len(results)
        diagnostics['arxiv_candidates']=len(candidates)
        papers=[]
        for work,aid in candidates[:MAX_PAPERS]:
            diagnostics['fulltext_attempts']+=1
            try:
                # Fixed hosts and paths only, no redirects or arbitrary provider URLs.
                html_url='https://arxiv.org/html/'+aid
                url='https://arxiv.org/pdf/'+aid
                try:
                    _,kind_header,body=await _bounded_get(client,html_url)
                    if 'text/html' not in kind_header.lower():raise ValueError('HTML copy unavailable')
                    text=_decode_html(body);kind='arXiv HTML';url=html_url
                except (httpx.HTTPError,ValueError):
                    _,_,body=await _bounded_get(client,url)
                    if not body.startswith(b'%PDF-'):
                        raise ValueError('PDF unavailable or invalid')
                    text=await asyncio.to_thread(_pdf_text,body)
                    kind='arXiv PDF'
                # Prevent mismatches where a URL exists but document identity is not plausible.
                title_terms=terms(work['title'])
                top_terms=terms(text[:6500])
                if len(title_terms & top_terms)<min(2,len(title_terms)):
                    raise ValueError('Article title not corroborated in fetched source text')
                excerpts=_make_excerpts(text)
                if not excerpts:raise ValueError('No extractable passage-sized text')
                papers.append({'arxiv_id':aid,'title':work['title'][:250], 'doi':normalize_doi(work.get('doi')),
                               'url':url,'kind':kind,'document_sha256':sha256(body).hexdigest(),'passages':excerpts})
                diagnostics['fulltext_retrieved']+=1
            except (httpx.HTTPError,ValueError,TypeError) as exc:
                diagnostics['fulltext_failures'].append(f"{aid}: {type(exc).__name__}")
        ledger=select_evidence(question,queries,papers)
        diagnostics['selected_passages']=len(ledger)
        status=('PASSAGES_LOCATED' if ledger else 'NO_RELEVANT_PASSAGES' if papers
                else 'FULLTEXT_UNAVAILABLE' if candidates else 'NO_ARXIV_OPENALEX_CANDIDATES')
        return {'status':status,'citation_ledger':ledger,'diagnostics':diagnostics,
            'papers':[{'title':p['title'],'arxiv_id':p['arxiv_id'],'source_url':p['url'],
                      'doi':p['doi'],'version':'arXiv repository copy; peer review not verified'} for p in papers]}
    finally:
        if own:await client.aclose()
