"""Bounded open-access full-text verification for ATLAS research dossiers.

Only fixed Europe PMC REST endpoints are called. Never fetch URLs from search results,
article XML, or model output. Full text stays ephemeral; API returns short excerpts.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import quote

import httpx
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from pydantic import BaseModel, Field, field_validator

from atlas.science import _doi, _normalize_title

EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
PMC_RE = re.compile(r'^PMC[1-9][0-9]{0,11}$')
MAX_XML_BYTES = 4_000_000
MAX_SEGMENTS = 350
STOPWORDS = {'the','that','this','what','which','with','from','were','where','when','into','does','have','been','does',
             'their','some','there','about','between','under','than','over','these','those','using','used','more',
             'less','research','studies','scientific','paper','compare','evidence','based','against','and','for'}


class QuoteCandidate(BaseModel):
    doi: str = Field(min_length=7, max_length=180)
    quote: str = Field(min_length=12, max_length=320)

    @field_validator('doi')
    @classmethod
    def valid_doi(cls, v: str) -> str:
        d = _doi(v)
        if not d:
            raise ValueError('A valid DOI is required for passage verification')
        return d

    @field_validator('quote')
    @classmethod
    def nonblank_quote(cls, v: str) -> str:
        if len(v.strip().split()) < 3:
            raise ValueError('Quote must contain at least three words')
        return v.strip()


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip()


def _tag(e) -> str:
    return e.tag.rsplit('}', 1)[-1] if isinstance(e.tag, str) else ''


def _text(element) -> str:
    return _norm(''.join(element.itertext()))


def _extract_xml(xml: bytes, doi: str, pmcid: str) -> dict:
    """Validate the source article's own identifiers; produce private paragraph list."""
    if not 100 <= len(xml) <= MAX_XML_BYTES:
        raise ValueError('FULLTEXT_INVALID_SIZE')
    try:
        root = SafeET.fromstring(xml)
    except (SafeET.ParseError, ValueError, DefusedXmlException) as exc:
        raise ValueError('FULLTEXT_INVALID_XML') from exc
    if _tag(root) != 'article':
        raise ValueError('FULLTEXT_WRONG_ROOT')
    ids = {}
    for e in root.iter():
        if _tag(e) == 'article-id':
            kind = e.attrib.get('pub-id-type', '').lower()
            if kind in ('doi', 'pmc'):
                ids.setdefault(kind, []).append(_text(e))
    if not any((_doi(x) or '').casefold() == doi.casefold() for x in ids.get('doi', [])):
        raise ValueError('XML_DOI_UNCONFIRMED')
    if ids.get('pmc') and not any(('PMC' + v.removeprefix('PMC')) == pmcid for v in ids['pmc']):
        raise ValueError('XML_PMCID_MISMATCH')
    body = next((e for e in root.iter() if _tag(e) == 'body'), None)
    if body is None:
        raise ValueError('FULLTEXT_NO_BODY')
    parents = {child: parent for parent in root.iter() for child in parent}
    segments = []
    for e in body.iter():
        if _tag(e) != 'p':
            continue
        passage = _text(e)
        if len(passage) < 35:
            continue
        ancestor = parents.get(e)
        section = 'Body'
        while ancestor is not None and ancestor is not body:
            if _tag(ancestor) == 'sec':
                header = next((x for x in ancestor if _tag(x) == 'title'), None)
                if header is not None:
                    section = _text(header)[:100] or 'Body'
                break
            ancestor = parents.get(ancestor)
        segments.append({'paragraph': len(segments) + 1, 'section': section,
                         'text': passage[:8000]})
        if len(segments) >= MAX_SEGMENTS:
            break
    if not segments:
        raise ValueError('FULLTEXT_NO_PASSAGES')
    lic = next((x for x in root.iter() if _tag(x) == 'license'), None)
    license_note = ''
    if lic is not None:
        license_note = next((v for k, v in lic.attrib.items() if k.endswith('href')), '') or _text(lic)[:140]
    return {'segments': segments, 'sha256': hashlib.sha256(xml).hexdigest(),
            'license': license_note[:160] or 'LICENSE_NOT_EXTRACTED'}


def _summary(status: str, **kwargs) -> dict:
    return {'status': status, 'source': 'Europe PMC OA XML',
            'scope': 'Repository full-text identity and literal source-span checking; scientific claims not validated',
            **kwargs}


async def retrieve_primary(paper: dict, client: httpx.AsyncClient) -> tuple[dict, list[dict]]:
    """Look up DOI->OA PMCID, then validate XML article identifier before extracts."""
    paper_doi = _doi(paper.get('doi'))
    if paper.get('verification', {}).get('status') != 'CROSSREF_METADATA_MATCH' or not paper_doi:
        return _summary('DOI_METADATA_NOT_CROSSCHECKED'), []
    if paper['verification'].get('update_notice_present'):
        return _summary('UPDATE_REVIEW_REQUIRED', warning='Crossref registered an editorial update; manual status review required'), []
    try:
        response = await client.get(EPMC + '/search', params={
            'query': 'DOI:' + paper_doi, 'resultType': 'core', 'format': 'json', 'pageSize': 5,
        }, timeout=10, follow_redirects=False)
        response.raise_for_status()
        items = response.json().get('resultList', {}).get('result', [])
        if not isinstance(items, list):
            raise ValueError('Malformed results')
        candidates = [p for p in items if isinstance(p, dict)
                      and (_doi(p.get('doi')) or '').casefold() == paper_doi.casefold()]
        if not candidates:
            return _summary('NO_REPOSITORY_DOI_RECORD'), []
        candidate = next((p for p in candidates if p.get('isOpenAccess') == 'Y'
                          and p.get('inEPMC') == 'Y' and PMC_RE.fullmatch(str(p.get('pmcid') or ''))), None)
        if candidate is None:
            return _summary('NO_OPEN_ACCESS_XML'), []
        pmcid = str(candidate['pmcid'])
        sim = SequenceMatcher(None, _normalize_title(str(candidate.get('title') or '')),
                              _normalize_title(paper['title'])).ratio()
        if sim < .84:
            return _summary('REPOSITORY_TITLE_MISMATCH'), []
        url = EPMC + '/' + quote(pmcid, safe='') + '/fullTextXML'
        async with client.stream('GET', url, timeout=12, follow_redirects=False) as xml_response:
            if xml_response.status_code == 404:
                return _summary('NO_OPEN_ACCESS_XML'), []
            xml_response.raise_for_status()
            length = xml_response.headers.get('content-length')
            if length and length.isdigit() and int(length) > MAX_XML_BYTES:
                return _summary('FULLTEXT_TOO_LARGE'), []
            chunks, size = [], 0
            async for part in xml_response.aiter_bytes():
                size += len(part)
                if size > MAX_XML_BYTES:
                    return _summary('FULLTEXT_TOO_LARGE'), []
                chunks.append(part)
        try:
            parsed = _extract_xml(b''.join(chunks), paper_doi, pmcid)
        except ValueError as exc:
            return _summary(str(exc)), []
        meta = _summary('REPOSITORY_FULLTEXT_MATCHED', pmcid=pmcid,
                        source_url='https://europepmc.org/articles/' + pmcid,
                        fulltext_url=url, document_sha256=parsed['sha256'],
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                        license=parsed['license'], passage_count=len(parsed['segments']),
                        status_warning='Absence of an update notice is NOT proof that the paper is unretracted.')
        return meta, parsed['segments']
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
        return _summary('REPOSITORY_UNAVAILABLE'), []


def _terms(question: str) -> set[str]:
    return {w for w in re.findall('[a-z0-9]{4,}', question.lower()) if w not in STOPWORDS}


def _short_quote(txt: str, terms: set[str], words: int = 13) -> str:
    toks = txt.split()
    if len(toks) <= words:
        return txt
    match = next((i for i, w in enumerate(toks) if re.sub('[^a-z0-9]', '', w.lower()) in terms), 0)
    start = max(0, min(len(toks) - words, match - 2))
    return ' '.join(toks[start:start+words])


def select_passages(paper_id: int, segments: list[dict], question: str, max_items: int = 2) -> tuple[list[dict], list[dict]]:
    terms = _terms(question)
    ranked = []
    for p in segments:
        words = set(re.findall(r'[a-z0-9]{4,}', p['text'].lower()))
        overlap = len(words & terms)
        if overlap:
            ranked.append((overlap, p))
    ranked.sort(key=lambda v: (-v[0], v[1]['paragraph']))
    displayed, model_evidence = [], []
    for i, (score, p) in enumerate(ranked[:max_items], 1):
        label = f'P{paper_id}.{i}'
        excerpt = _short_quote(p['text'], terms)
        displayed.append({'citation_id': label, 'section': p['section'], 'paragraph': p['paragraph'],
                          'excerpt': excerpt, 'excerpt_sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                          'match_term_count': score, 'status': 'EXACT_SOURCE_EXCERPT'})
        # Source material for configured model is deliberately bounded to a few paragraphs.
        model_evidence.append({'citation_id': label, 'text': ' '.join(p['text'].split()[:100]),
                               'section': p['section'], 'paragraph': p['paragraph']})
    return displayed, model_evidence


def verify_quotes(candidates: list[QuoteCandidate], papers: list[dict], segments_by_id: dict[int, list[dict]]) -> list[dict]:
    output = []
    for quote in candidates:
        target = next((p for p in papers if (p.get('doi') or '').lower() == quote.doi.lower()), None)
        if not target:
            output.append({'doi': quote.doi, 'status': 'DOI_NOT_IN_DISCOVERY', 'citation_id': None})
            continue
        sections = segments_by_id.get(target['id'], [])
        if target.get('primary_source', {}).get('status') != 'REPOSITORY_FULLTEXT_MATCHED':
            output.append({'doi': quote.doi, 'status': 'SOURCE_NOT_VERIFIED', 'citation_id': None})
            continue
        exact = _norm(quote.quote)
        found = next((p for p in sections if exact in p['text']), None)
        if not found:
            output.append({'doi': quote.doi, 'status': 'EXACT_QUOTE_NOT_FOUND', 'citation_id': None})
            continue
        output.append({'doi': quote.doi, 'status': 'EXACT_TEXT_MATCH',
                       'citation_id': f"P{target['id']}.Q{len(output)+1}",
                       'section': found['section'], 'paragraph': found['paragraph'],
                       'matched_sha256': hashlib.sha256(exact.encode()).hexdigest(),
                       'matched_excerpt': _short_quote(exact, set(), 18),
                       'scope': 'Only text occurrence checked, not claim truth or quoted context.'})
    return output
