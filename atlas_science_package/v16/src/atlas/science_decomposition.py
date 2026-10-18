"""ATLAS v1.6: bounded, explicitly grounded decomposition and gap-targeted discovery.

This module never treats topical overlap as scientific support. Remote passages remain
untrusted data. No recursive agents, invented premises, user-supplied URLs, or implicit
model calls. Source locators retain their originating search/batch identity.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from atlas.science_theories import ScienceAskV13Request
from atlas.science_workflow import (
    ResearchWorkflowRequest, _interpret_with_provider, _source_index,
    plan_research, run_scientific_workflow,
)

VERSION = '1.6'
STOP = frozenset('about above across after among analysis and are based because between compare '
                 'data does evidence explain find for from how into literature model models of on or '
                 'papers prediction predictions research study studies than that the theory theories '
                 'their these this those under versus what when where whether which with would'.split())
COMPARE = re.compile(
    r'^\s*(?:compare|contrast)\s+(.{3,95}?)\s+(?:and|versus|vs\.?|against)\s+'
    r'(.{3,95}?)\s+(?:for|in|on|under|regarding)\s+(.{5,130}?)\s*[.?!]?\s*$', re.I,
)


class DecomposedResearchRequest(ResearchWorkflowRequest):
    subquestions: list[str] = Field(default_factory=list, max_length=3)
    auto_decompose: bool = True
    max_followups: int = Field(default=2, ge=0, le=2)
    # These are *reserved query capacities*, not counts inferred from returned results.
    max_total_papers: int = Field(default=6, ge=3, le=6)
    max_total_primary_papers: int = Field(default=4, ge=2, le=4)

    @field_validator('subquestions')
    @classmethod
    def validate_subquestions(cls, value: list[str]) -> list[str]:
        cleaned = [' '.join(s.split()) for s in value]
        if any(not 10 <= len(s) <= 240 for s in cleaned):
            raise ValueError('Each explicit subquestion must be 10–240 characters')
        if len({s.casefold() for s in cleaned}) != len(cleaned):
            raise ValueError('Duplicate subquestions are not allowed')
        return cleaned

    @model_validator(mode='after')
    def validate_decomposition_budget(self):
        if self.max_total_papers < self.max_papers or self.max_total_primary_papers < self.max_primary_papers:
            raise ValueError('Total reserved budgets must cover the initial discovery budget')
        if self.literature == 'off' and (self.subquestions or self.max_followups > 0 and self.auto_decompose):
            # Math-only flows may keep defaults: the planner will simply skip discovery.
            if self.subquestions:
                raise ValueError('Explicit research subquestions require literature discovery')
        return self


def plan_subquestions(req: DecomposedResearchRequest, *, discovery_enabled: bool) -> dict:
    if not discovery_enabled:
        return {'strategy': 'LITERATURE_DISABLED', 'items': [], 'max_followups': 0,
                'provenance': 'No subquestions inferred when literature is disabled'}
    if req.subquestions:
        return {'strategy': 'USER_SUPPLIED', 'items': [
            {'id': f'Q{i}', 'query': q, 'anchor': None, 'origin': 'EXPLICIT_USER_INPUT'}
            for i, q in enumerate(req.subquestions, 1)], 'max_followups': req.max_followups}
    if req.auto_decompose:
        match = COMPARE.fullmatch(req.question)
        if match:
            left, right, context = (' '.join(s.split()).rstrip('?.!') for s in match.groups())
            # The two query facets are only substrings taken from the user's text.
            if all(len(x.split()) <= 9 for x in (left, right, context)):
                return {'strategy': 'LITERAL_COMPARISON_FACETS', 'items': [
                    {'id': 'Q1', 'query': (left + ' ' + context)[:240], 'anchor': left.casefold(), 'origin': 'USER_WORDING'},
                    {'id': 'Q2', 'query': (right + ' ' + context)[:240], 'anchor': right.casefold(), 'origin': 'USER_WORDING'},
                ], 'max_followups': req.max_followups}
    return {'strategy': 'NO_CONFIDENT_DECOMPOSITION', 'items': [],
            'max_followups': 0, 'provenance': 'No additional searches invented from ambiguous prose'}


def _words(s: str) -> set[str]:
    return {t for t in re.findall(r'[a-z0-9]{3,}', s.casefold()) if t not in STOP}


def _coverage(question: dict, ledger: list[dict]) -> dict:
    # Topical text only. Neither citation existence nor overlap establishes entailment.
    terms = _words(question['query'])
    hits = []
    for source in ledger:
        excerpt = source.get('excerpt', '')
        words = _words(excerpt)
        shared = terms.intersection(words)
        anchor = question.get('anchor')
        if len(shared) >= 2 and (anchor is None or anchor in excerpt.casefold()):
            hits.append({'citation_id': source['citation_id'], 'overlapping_terms': sorted(shared)[:8]})
    return {'id': question['id'], 'query': question['query'], 'origin': question['origin'],
            'status': 'TOPICAL_EXCERPT_LOCATED_NOT_CLAIM_VERIFIED' if hits else 'NO_VERIFIED_TOPICAL_EXCERPT',
            'topical_citations': hits[:6], 'scientific_entailment': 'NOT_ASSESSED'}


def _append_source_batch(ledger: list[dict], seen: set[tuple], papers: dict, label: str) -> int:
    added = 0
    for source in _source_index(papers):
        key = (source['doi'].casefold(), source['excerpt_sha256'])
        if key in seen:
            continue
        seen.add(key)
        doc = dict(source)
        doc['origin_batch'] = label
        doc['original_citation_id'] = source['citation_id']
        doc['citation_id'] = f'{label}.{source["citation_id"]}'
        ledger.append(doc)
        added += 1
    return added


def _base_request(req: DecomposedResearchRequest) -> ResearchWorkflowRequest:
    fields = set(ResearchWorkflowRequest.model_fields)
    values = {k: v for k, v in req.model_dump().items() if k in fields}
    values['provider'] = 'demo'
    values['model'] = None
    return ResearchWorkflowRequest.model_validate(values)


async def run_decomposed_research(req: DecomposedResearchRequest, *,
                                  base_runner=None, followup_runner=None,
                                  synthesis_runner=None, client=None) -> dict:
    """Up to one v1.5 run, two targeted literature runs, one explicit provider call.

    Dependency injection exists for offline tests. In production, each batch goes
    through v1.3's same guarded discovery / DOI / primary-text verification path.
    """
    base_runner = base_runner or run_scientific_workflow
    if followup_runner is None:
        from atlas.science_theories import scientific_answer_v13
        followup_runner = scientific_answer_v13
    synthesis_runner = synthesis_runner or _interpret_with_provider
    base_req = _base_request(req)
    base_plan, _ = plan_research(base_req)
    discovery_enabled = any(s['tool'] == 'literature_and_theory' for s in base_plan['steps'])
    decomposition = plan_subquestions(req, discovery_enabled=discovery_enabled)
    trace = []
    # Provider is forced off in the foundation: at most one model call, after all searches.
    try:
        foundation = await base_runner(base_req, client=client)
        if not isinstance(foundation, dict):
            raise TypeError('Invalid foundation output')
    except Exception:
        # Exclude exception text: errors may include credentials or remote data.
        foundation = {'status': 'BASE_UNAVAILABLE', 'answer': 'Base research unavailable.',
                      'literature': {'status': 'LITERATURE_UNAVAILABLE', 'papers': []},
                      'calculations': {'summaries': []}, 'source_index': [], 'arxiv_discovery': {'status': 'NOT_REQUESTED'},
                      'report_sha256': None}
    initial_literature = foundation.get('literature') or {'status': 'NOT_REQUESTED', 'papers': []}
    if not isinstance(initial_literature, dict):
        initial_literature = {'status': 'LITERATURE_UNAVAILABLE', 'papers': []}
    ledger: list[dict] = []
    seen: set[tuple] = set()
    added = _append_source_batch(ledger, seen, initial_literature, 'B') if discovery_enabled else 0
    trace.append({'stage': 'FOUNDATION', 'status': initial_literature.get('status', 'UNKNOWN'),
                  'source_text_locators_added': added, 'requested_papers': req.max_papers,
                  'requested_primary_papers': req.max_primary_papers})
    # Reserve full first-round quotas, even if fewer results were returned.
    remaining_papers = req.max_total_papers - (req.max_papers if discovery_enabled else 0)
    remaining_primary = req.max_total_primary_papers - (req.max_primary_papers if discovery_enabled else 0)
    followups = []
    max_followups = decomposition['max_followups']
    for question in decomposition['items']:
        coverage = _coverage(question, ledger)
        if coverage['status'] != 'NO_VERIFIED_TOPICAL_EXCERPT':
            trace.append({'stage': 'GAP_CHECK', 'subquestion': question['id'], 'status': 'TOPICAL_EXCERPT_ALREADY_PRESENT'})
            continue
        if len(followups) >= max_followups or remaining_papers <= 0 or remaining_primary <= 0:
            trace.append({'stage': 'GAP_CHECK', 'subquestion': question['id'], 'status': 'SEARCH_SKIPPED_BUDGET_OR_DISABLED'})
            continue
        allocation_papers = min(2, remaining_papers)
        allocation_primary = min(1, remaining_primary, allocation_papers)
        if allocation_primary == 0:
            break
        remaining_papers -= allocation_papers
        remaining_primary -= allocation_primary
        step = {'id': f'F{len(followups)+1}', 'subquestion': question['id'],
                'query': question['query'], 'requested_papers': allocation_papers,
                'requested_primary_papers': allocation_primary}
        try:
            parameters = ScienceAskV13Request(
                question=question['query'], provider='demo', max_papers=allocation_papers,
                include_primary=True, max_primary_papers=allocation_primary,
                theories=[], interpret_theories=False)
            payload = await followup_runner(parameters, client=client)
            if not isinstance(payload, dict):
                raise TypeError('Unexpected discovery result')
            step['status'] = str(payload.get('status', 'UNKNOWN'))[:80]
            step['source_text_locators_added'] = _append_source_batch(ledger, seen, payload, step['id'])
            step['candidate_count'] = min(allocation_papers, len(payload.get('papers', [])))
            step['candidates'] = [
                {'title': str(p.get('title', ''))[:350], 'doi': p.get('doi'),
                 'verification': (p.get('verification') or {}).get('status', 'UNKNOWN'),
                 'primary_status': (p.get('primary_source') or {}).get('status', 'UNKNOWN')}
                for p in payload.get('papers', [])[:allocation_papers] if isinstance(p, dict)]
        except Exception:
            step.update(status='FOLLOWUP_UNAVAILABLE', source_text_locators_added=0,
                        candidate_count=0, candidates=[])
        followups.append(step)
        trace.append({'stage': 'TARGETED_DISCOVERY', **{k: v for k, v in step.items() if k != 'candidates'}})
    gaps = [_coverage(q, ledger) for q in decomposition['items']]
    available = [s for s in ledger if isinstance(s.get('citation_id'), str)]
    calculations = (foundation.get('calculations') or {}).get('summaries', [])
    if not isinstance(calculations, list):
        calculations = []
    if req.provider == 'demo':
        commentary = {'status': 'NOT_REQUESTED', 'summary': None, 'cited_ids': []}
    else:
        try:
            commentary = await synthesis_runner(req, available[:6], calculations[:11])
            if not isinstance(commentary, dict) or not isinstance(commentary.get('status'), str):
                raise ValueError('invalid model synthesis')
        except Exception:
            commentary = {'status': 'MODEL_REJECTED_OR_PROVIDER_UNAVAILABLE', 'summary': None, 'cited_ids': []}
    trace.append({'stage': 'SYNTHESIS', 'status': commentary['status'], 'provider': req.provider})
    resolved = sum(g['status'] == 'TOPICAL_EXCERPT_LOCATED_NOT_CLAIM_VERIFIED' for g in gaps)
    lines = [f'Initial research: {initial_literature.get("status", "UNKNOWN")}.',
             f'Follow-up searches: {len(followups)}/{max_followups}; '
             f'crosschecked source-text excerpts: {len(available)}.']
    for g in gaps:
        lines.append(f'{g["id"]}: {g["status"]} — {g["query"]}')
    if not available:
        lines.append('No independently crosschecked primary-text passages were found; abstaining from an evidence-supported scientific answer.')
    else:
        lines.append('Located excerpts establish passage provenance and topic overlap ONLY; they do not verify scientific claims or compare theory validity.')
    if commentary.get('summary') and commentary.get('status') == 'MODEL_INTERPRETATION_LOCATORS_CHECKED_NOT_ENTAILMENT':
        lines.append('Unverified model interpretation: ' + str(commentary['summary'])[:700])
    if calculations:
        lines.append('Formal checks (assume supplied expressions): ' + '; '.join(map(str, calculations[:11])))
    result = {
        'version': VERSION, 'question': req.question, 'decomposition': decomposition,
        'coverage': {'topically_matched': resolved, 'total_subquestions': len(gaps),
                     'labels': gaps, 'scientific_claim_verification': 'NOT_PERFORMED'},
        'followups': followups, 'citation_ledger': available,
        'budgets': {'max_followup_searches': max_followups, 'used_followup_searches': len(followups),
                    'max_total_requested_papers': req.max_total_papers,
                    'max_total_requested_primary_papers': req.max_total_primary_papers,
                    'reserved_requested_papers': req.max_papers + sum(x['requested_papers'] for x in followups) if discovery_enabled else 0,
                    'reserved_requested_primary_papers': req.max_primary_papers + sum(x['requested_primary_papers'] for x in followups) if discovery_enabled else 0,
                    'model_calls': 0 if req.provider == 'demo' else 1,
                    'network_note': 'Quotas bound discovery attempts at application level, not TCP requests, redirects or upstream client retries.'},
        'execution_trace': trace,
        'answer': '\n'.join(lines),
        'answer_status': ('UNVERIFIED_MODEL_INTERPRETATION_WITH_VERIFIED_LOCATORS'
                          if commentary.get('status') == 'MODEL_INTERPRETATION_LOCATORS_CHECKED_NOT_ENTAILMENT' and commentary.get('summary')
                          else 'DETERMINISTIC_GAP_AWARE_REPORT_NOT_A_SCIENTIFIC_VERDICT'),
        'model_interpretation': commentary,
        'foundation': foundation,
        'limitations': [
            'A passage or topical match does not establish support, opposition, experimental validity, or scientific truth.',
            'Only certain repository-hosted open-access full text can be checked; inaccessible papers remain unverified.',
            'Deterministic subquestions are literal rewrites of user text, not autonomous scientific hypotheses.',
            'A missing topical excerpt does not prove the literature lacks relevant evidence.',
            'Only validated locator labels, not model scientific entailment, are checked in generated interpretation.',
            'Model and remote service availability depend on your actual backend configuration.',
            'This report fingerprint identifies an output payload; it does not independently reproduce a scientific result.',
        ],
    }
    canonical = json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'), default=str)
    result['report_sha256'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return result
