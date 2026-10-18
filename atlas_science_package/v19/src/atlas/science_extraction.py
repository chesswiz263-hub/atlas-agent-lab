"""ATLAS v1.9 — source-anchored numeric mentions and human-reviewed comparisons.

Extraction is deliberately narrow: decimal/scientific values with a known unit,
optionally followed by a printed ± uncertainty. Input comes ONLY from the
v1.6/1.7 checked primary-text citation ledger obtained during this request.
Source text is evidence of wording, not a validated experiment, role, uncertainty
level, physical interpretation, or a proven scientific claim.

No general web fetch, arbitrary URLs, model calls, stateful secrets, or eval.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas.science_claims import verified_ledger
from atlas.science_decomposition import DecomposedResearchRequest, run_decomposed_research
from atlas.science_quantitative import UNITS, Quantity, QuantitativeCase, compare_case

MAX_CANDIDATES = 24
# Disallow bare 1 as a unit; requiring an explicit unit avoids extracting years,
# citations and random dimensionless numbers as alleged measurements.
UNIT_KEYS = sorted((k for k in UNITS if k != '1'), key=len, reverse=True)
_UNIT_EXPRESSION = '|'.join(re.escape(unit) for unit in UNIT_KEYS)
_NUMBER = r'[+-]?(?:\d{1,10}(?:\.\d{0,12})?|\.\d{1,12})(?:[eE][+-]?\d{1,2})?'
MENTION = re.compile(
    rf'(?<![\w.^–—-])(?P<value>{_NUMBER})'
    rf'(?:[ \t\u00a0]*(?:±|\+/-)[ \t\u00a0]*(?P<uncertainty>{_NUMBER}))?'
    rf'[ \t\u00a0]*(?P<unit>{_UNIT_EXPRESSION})(?![A-Za-z0-9/^*·²³⁻])'
)
DOI = re.compile(r'^10\.\d{4,9}/\S{1,170}$', re.I)
SHA = re.compile(r'^[a-f0-9]{64}$')
ROLE_CUES = {
    'MEASUREMENT_LANGUAGE': re.compile(r'\b(?:observed|measured|detected|reported|obtained|estimated)\b', re.I),
    'PREDICTION_LANGUAGE': re.compile(r'\b(?:predicted|predicts?|model|simulated|simulation|calculated)\b', re.I),
}


def _hash(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def _numeric(value: str) -> str | None:
    try:
        number = Decimal(value)
        if not number.is_finite() or abs(number) > Decimal('1e50'):
            return None
        if number and abs(number) < Decimal('1e-100'):
            return None
        return str(number)
    except (InvalidOperation, TypeError):
        return None


def extract_candidates(raw_ledger: list[dict], *, limit: int = MAX_CANDIDATES) -> list[dict]:
    """Extract candidate literal spans; preserve offsets into SHA-checked excerpts.

    The input ledger is revalidated internally. Never trust a client-supplied
    citation id, document digest or excerpt digest as proof of a source fetch.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
        raise ValueError('Candidate limit is 1–24')
    ledger = verified_ledger(raw_ledger)
    result, ids = [], set()
    for source in ledger:
        excerpt = source['excerpt']
        for match in MENTION.finditer(excerpt):
            # Reject the terminal portion of ranges such as 200–220 km/s.
            if match.start() > 1 and excerpt[match.start()-1] in '-–—' and excerpt[match.start()-2].isdigit():
                continue
            literal = match.group(0)
            value, unc = _numeric(match.group('value')), None
            if value is None:
                continue
            if match.group('uncertainty') is not None:
                unc = _numeric(match.group('uncertainty'))
                if unc is None or Decimal(unc) < 0:
                    continue
            unit = match.group('unit')
            try:
                # Apply existing v1.8 numeric and supported-unit validators.
                Quantity(observable='unclassified quantitative mention',
                         conditions='conditions require human review',
                         value=value, unit=unit, **({'standard_uncertainty': unc} if unc is not None else {}))
            except ValueError:
                continue
            span = [match.start(), match.end()]
            identity = [source['doi'].lower(), source['document_sha256'],
                        source['excerpt_sha256'], *span, literal]
            candidate_id = 'N' + _hash(identity)[:20]
            if candidate_id in ids:
                continue
            ids.add(candidate_id)
            result.append({
                'candidate_id': candidate_id,
                'value': value, 'unit': unit, 'printed_uncertainty': unc,
                'uncertainty_interpretation': 'NOT_ESTABLISHED',
                'literal': literal, 'excerpt_offset': span,
                'citation_id': source['citation_id'],
                'doi': source['doi'], 'doi_url': source.get('doi_url'),
                'source_url': source.get('source_url'), 'title': source.get('title'),
                'section': source['section'], 'paragraph': source['paragraph'],
                'excerpt': excerpt, 'excerpt_sha256': source['excerpt_sha256'],
                'document_sha256': source['document_sha256'],
                'textual_cues': [name for name, pattern in ROLE_CUES.items()
                                if pattern.search(excerpt)] or ['NO_CLEAR_ROLE_CUE'],
                'status': 'SOURCE_EXCERPT_SPAN_CHECKED_SCIENTIFIC_ROLE_UNVERIFIED',
            })
            if len(result) >= limit:
                return result
    return result


class ExtractedComparison(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(pattern=r'^Q[1-4]$')
    label: str = Field(min_length=3, max_length=130)
    prediction_candidate_id: str = Field(pattern=r'^N[a-f0-9]{20}$')
    measurement_candidate_id: str = Field(pattern=r'^N[a-f0-9]{20}$')
    observable: str = Field(min_length=3, max_length=140)
    conditions: str = Field(min_length=3, max_length=200)
    user_confirms_roles_and_context: Literal[True]
    uncertainty_model: Literal['none','independent_gaussian_1sigma',
                               'correlation_supplied_gaussian_1sigma'] = 'none'
    user_confirms_uncertainties_gaussian_1sigma: bool = False
    correlation: Decimal | None = None

    @field_validator('observable', 'conditions')
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = ' '.join(value.split())
        if len(value) < 3:
            raise ValueError('Specify a meaningful observable and experimental conditions')
        return value

    @model_validator(mode='after')
    def require_explicit_review(self):
        if self.prediction_candidate_id == self.measurement_candidate_id:
            raise ValueError('Select two distinct candidate mentions')
        if self.uncertainty_model != 'none' and not self.user_confirms_uncertainties_gaussian_1sigma:
            raise ValueError('Printed uncertainty is not known to be Gaussian 1σ; explicit confirmation required')
        if self.uncertainty_model == 'correlation_supplied_gaussian_1sigma':
            if self.correlation is None or not self.correlation.is_finite() or not -1 <= self.correlation <= 1:
                raise ValueError('Provide a correlation in [-1,1]')
        elif self.correlation is not None:
            raise ValueError('Correlation requires the correlated-uncertainty model')
        return self


class ExtractionResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    research_question: str = Field(min_length=15, max_length=500)
    max_candidates: int = Field(default=24, ge=1, le=24)
    comparisons: list[ExtractedComparison] = Field(default_factory=list, max_length=4)

    @field_validator('research_question')
    @classmethod
    def valid_question(cls, question: str) -> str:
        question = ' '.join(question.split())
        if len(question) < 15:
            raise ValueError('Research question cannot be blank')
        return question

    @model_validator(mode='after')
    def unique_ids(self):
        ids = [c.case_id for c in self.comparisons]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate comparison IDs')
        return self


def compare_extracted(comparisons: list[ExtractedComparison], candidates: list[dict]) -> list[dict]:
    """Fail closed on any lookup or uncertainty ambiguity; never invent values."""
    indexed = {c['candidate_id']: c for c in candidates}
    output = []
    for selection in comparisons:
        base = {'case_id': selection.case_id, 'label': selection.label,
                'status': 'ABSTAINED_UNREVIEWED_OR_MISSING_SOURCE',
                'scientific_validity': 'NOT_ESTABLISHED',
                'human_review_required': True,
                'limitations': ['Source context and candidate role remain user assertions, not scientifically verified.']}
        p, m = indexed.get(selection.prediction_candidate_id), indexed.get(selection.measurement_candidate_id)
        if p is None or m is None:
            base['limitations'].append('At least one selected candidate was not found in this fresh checked primary-text retrieval.')
            output.append(base)
            continue
        if selection.uncertainty_model != 'none' and (p['printed_uncertainty'] is None or m['printed_uncertainty'] is None):
            base['status'] = 'ABSTAINED_MISSING_PRINTED_UNCERTAINTY'
            base['limitations'].append('Both sources must print explicit ± uncertainties to compute a residual.')
            output.append(base)
            continue
        try:
            quantities = []
            for x in (p, m):
                kwargs = {'observable':selection.observable, 'conditions':selection.conditions,
                          'value': x['value'], 'unit': x['unit']}
                if selection.uncertainty_model != 'none':
                    kwargs['standard_uncertainty'] = x['printed_uncertainty']
                quantities.append(Quantity(**kwargs))
            case = QuantitativeCase(case_id=selection.case_id, label=selection.label,
                                    prediction=quantities[0], measurement=quantities[1],
                                    uncertainty_model=selection.uncertainty_model,
                                    **({'correlation': selection.correlation} if selection.correlation is not None else {}))
            computed = compare_case(case)
            computed['source_transcription'] = 'VERBATIM_SPAN_EXTRACTED_HUMAN_CONTEXT_REQUIRED'
            computed['source_bindings'] = {
                'prediction': {'candidate_id': p['candidate_id'], 'citation_id': p['citation_id'],
                               'doi': p['doi'], 'excerpt_sha256':p['excerpt_sha256'],
                               'literal':p['literal'], 'document_sha256':p['document_sha256']},
                'measurement': {'candidate_id': m['candidate_id'], 'citation_id': m['citation_id'],
                                'doi': m['doi'], 'excerpt_sha256':m['excerpt_sha256'],
                                'literal':m['literal'], 'document_sha256':m['document_sha256']},
            }
            computed['human_review_required'] = True
            computed['limitations'].append('Printed ± uncertainties are not confirmed as Gaussian 1σ by extraction; the user explicitly asserted this if modeled.')
            computed['limitations'].append('User mapped mentions to roles, observables and identical conditions; these cannot be proven by the parser.')
            base.update(computed)
            base['status'] = computed['calculation_status']
        except (ValueError, TypeError) as error:
            base['status'] = 'ABSTAINED_INVALID_SOURCE_COMPARISON'
            base['limitations'].append('Source comparison failed safely; inspect source values and units.')
        output.append(base)
    return output


async def run_extraction_research(req: ExtractionResearchRequest, *, research_runner=None, client=None) -> dict:
    """One bounded, no-model primary-text lookup; rerun on comparison requests."""
    research_runner = research_runner or run_decomposed_research
    params = DecomposedResearchRequest(
        question=req.research_question, literature='on', arxiv='off', provider='demo',
        auto_decompose=False, max_followups=1, max_total_papers=5,
        max_total_primary_papers=3, max_papers=3, max_primary_papers=2)
    source_status = 'DISCOVERY_UNAVAILABLE'
    trace, budgets, ledger = [], {}, []
    try:
        data = await research_runner(params, client=client)
        if not isinstance(data, dict):
            raise ValueError('Invalid discovery response')
        ledger = verified_ledger(data.get('citation_ledger', []))
        trace = data.get('execution_trace', []) if isinstance(data.get('execution_trace'), list) else []
        budgets = data.get('budgets', {}) if isinstance(data.get('budgets'), dict) else {}
        source_status = 'PRIMARY_TEXT_EXCERPTS_LOCATED' if ledger else 'NO_CHECKED_PRIMARY_TEXT'
    except Exception:
        source_status = 'DISCOVERY_UNAVAILABLE'
    candidates = extract_candidates(ledger, limit=req.max_candidates)
    comparisons = compare_extracted(req.comparisons, candidates)
    result = {'version':'1.9', 'engine':'ATLAS_SOURCE_NUMERIC_EXTRACTION',
              'source_status':source_status, 'extraction_status':(
                  'SOURCE_ANCHORED_NUMERIC_MENTIONS_NOT_SCIENTIFICALLY_CLASSIFIED' if candidates else 'NO_SUPPORTED_NUMERIC_MENTIONS'),
              'research_question':req.research_question, 'candidates':candidates,
              'comparisons':comparisons, 'citation_ledger':ledger,
              'source_audit':{'execution_trace':trace, 'budgets':budgets},
              'scientific_truth': 'NOT_ESTABLISHED',
              'limitations':[
                  'Only short, checked primary-text excerpts in the v1.6 citation ledger are scanned; this is not whole-paper or table extraction.',
                  'Number-unit matching verifies literal wording and offsets, not a measurement, prediction, error model or correct scientific interpretation.',
                  'Comparison roles, observable equivalence and experimental conditions require independent domain review.',
                  'A new comparison request refetches its sources; stale candidate identifiers fail closed.',
                  'No AI model, p-value, theory endorsement, or autonomous claim promotion is performed.',
              ]}
    result['report_sha256'] = _hash(result)
    return result
