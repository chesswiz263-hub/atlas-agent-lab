"""Bounded arXiv Atom metadata discovery; never implies full-text/claim verification."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time

import httpx
from defusedxml import ElementTree as ET

ARXIV_API = 'https://export.arxiv.org/api/query'
ATOM = '{http://www.w3.org/2005/Atom}'
ARXIV = '{http://arxiv.org/schemas/atom}'
IDENT = re.compile(r'(?:[0-9]{4}\.[0-9]{4,5}|[A-Za-z.-]+(?:\.[A-Z]{2})?/\d{7})(?:v[1-9]\d{0,2})?$', re.ASCII)
DOI = re.compile(r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$', re.ASCII)
STOP = frozenset('what when where explain explainable compare contrast research papers paper studies about between does do the and or for with that this from into recent how why versus evidence scientific mathematical theory theories'.split())
_LOCK = asyncio.Lock()
_LAST = 0.0


def _query(question: str) -> str:
    """Search literals only; no untrusted Boolean arXiv syntax."""
    words = [w.casefold() for w in re.findall(r'[A-Za-z0-9]{3,}', question) if w.casefold() not in STOP]
    tokens = list(dict.fromkeys(words))[:5]
    if not tokens:
        raise ValueError('No useful arXiv search terms')
    return ' AND '.join('all:' + t for t in tokens)


def _clean(text: str | None, maximum: int) -> str:
    return ' '.join((text or '').split())[:maximum]


def parse_atom(data: bytes, limit: int = 6) -> list[dict]:
    """Parse arXiv-hosted Atom metadata; no arbitrary URLs are followed."""
    if not 1 <= limit <= 6 or len(data) > 1_500_000:
        raise ValueError('Oversized or invalid arXiv feed')
    root = ET.fromstring(data)
    if root.tag != ATOM + 'feed':
        raise ValueError('Expected an Atom feed')
    results = []
    for entry in root.findall(ATOM + 'entry')[:limit]:
        raw_id = (entry.findtext(ATOM + 'id') or '').strip()
        # arXiv's Atom ID is either an arxiv.org/abs URL or legacy ID URL.
        match = re.fullmatch(r'https?://(?:www\.)?arxiv\.org/abs/(.+)', raw_id)
        if not match or not IDENT.fullmatch(match.group(1)):
            continue  # In particular, do not surface API error entries as papers.
        identifier = match.group(1)
        authors = [_clean(n.findtext(ATOM + 'name'), 100) for n in entry.findall(ATOM + 'author')[:8]]
        doi_raw = _clean(entry.findtext(ARXIV + 'doi'), 180)
        record = {
            'arxiv_id': identifier,
            'title': _clean(entry.findtext(ATOM + 'title'), 350),
            'authors': [a for a in authors if a],
            'abstract': _clean(entry.findtext(ATOM + 'summary'), 2500),
            'published': _clean(entry.findtext(ATOM + 'published'), 32),
            'updated': _clean(entry.findtext(ATOM + 'updated'), 32),
            'categories': [c.get('term', '')[:50] for c in entry.findall(ATOM + 'category')[:6]],
            'doi': doi_raw if DOI.fullmatch(doi_raw) else None,
            'url': 'https://arxiv.org/abs/' + identifier,
            'status': 'ARXIV_HOSTED_METADATA_ONLY',
        }
        if not record['title']:
            continue
        record['metadata_sha256'] = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        results.append(record)
    return results


async def _throttle() -> None:
    """Best-effort single-process throttle; deployments with many workers need a shared limit."""
    global _LAST
    async with _LOCK:
        now = time.monotonic()
        wait = max(0.0, 3.0 - (now - _LAST)) if _LAST else 0
        if wait:
            await asyncio.sleep(wait)
        _LAST = time.monotonic()


async def discover_arxiv(question: str, limit: int = 5, *, client: httpx.AsyncClient | None = None) -> dict:
    if not 5 <= len(question.strip()) <= 500 or not 1 <= limit <= 6:
        raise ValueError('Invalid arXiv request')
    try:
        q = _query(question)
    except ValueError:
        return {'status': 'NO_QUERY_TERMS', 'papers': [], 'source': 'arXiv', 'verification': 'NONE'}
    own = client is None
    if own:
        contact = os.getenv('ATLAS_RESEARCH_EMAIL', '').strip()
        agent = 'ATLAS-Agent-Lab/1.4' + (f' (research; {contact[:120]})' if contact else '')
        client = httpx.AsyncClient(timeout=14, follow_redirects=False, headers={'User-Agent': agent})
    assert client is not None
    try:
        if own:
            await _throttle()
        # Stream to bound response size before storing it; never fetch arbitrary source URLs.
        async with client.stream('GET', ARXIV_API, params={
            'search_query': q, 'start': 0, 'max_results': limit,
            'sortBy': 'relevance', 'sortOrder': 'descending',
        }, timeout=14) as response:
            response.raise_for_status()
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                if len(raw) + len(chunk) > 1_500_000:
                    raise ValueError('arXiv response exceeded limit')
                raw.extend(chunk)
        papers = parse_atom(bytes(raw), limit)
        return {'status': 'RESULTS_FOUND' if papers else 'NO_RESULTS',
                'papers': papers, 'source': 'arXiv', 'search_query': q,
                'verification': 'REPOSITORY_METADATA_NOT_FULLTEXT_VERIFIED',
                'notes': ['arXiv is a preprint repository; entries are not necessarily peer reviewed.',
                          'An Atom entry or DOI field is not an independently crosschecked publication claim.',
                          'No arXiv PDF/full text was fetched or mathematically checked.']}
    except (httpx.HTTPError, ValueError, ET.ParseError, TypeError):
        return {'status': 'ARXIV_UNAVAILABLE', 'papers': [], 'source': 'arXiv',
                'verification': 'NONE', 'message': 'arXiv did not return usable metadata. No papers were invented.'}
    finally:
        if own:
            await client.aclose()
