"""ATLAS v1.8: bounded, unit-aware, uncertainty-explicit quantitative audit.

Numbers are *user-provided*, never extracted from sources by this module.
Passage verification proves quote location, NOT correct numerical transcription,
probability calibration, independent errors, or a scientific hypothesis.
No arbitrary code evaluation, external URL ingestion, or implicit model call.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas.science_claims import verified_ledger
from atlas.science_decomposition import DecomposedResearchRequest, run_decomposed_research

VERSION = '1.8'
MAX_VALUE = Decimal('1E50')
# dimension, scale to SI; exact SI definitions where possible, marked approximate
# for astronomical units. Never silently parse compound unit expressions.
UNITS: dict[str, tuple[str, Decimal, str]] = {
    '1': ('dimensionless', Decimal('1'), '1'),
    '%': ('dimensionless', Decimal('.01'), '1'),
    'm': ('length', Decimal('1'), 'm'),
    'mm': ('length', Decimal('.001'), 'm'),
    'cm': ('length', Decimal('.01'), 'm'),
    'km': ('length', Decimal('1000'), 'm'),
    'AU': ('length', Decimal('149597870700'), 'm'),
    'pc': ('length', Decimal('3.0856775814913673e16'), 'm'),
    'kpc': ('length', Decimal('3.0856775814913673e19'), 'm'),
    'Mpc': ('length', Decimal('3.0856775814913673e22'), 'm'),
    's': ('time', Decimal('1'), 's'),
    'ms': ('time', Decimal('.001'), 's'),
    'min': ('time', Decimal('60'), 's'),
    'h': ('time', Decimal('3600'), 's'),
    'yr': ('time', Decimal('31557600'), 's'),
    'Myr': ('time', Decimal('31557600000000'), 's'),
    'Gyr': ('time', Decimal('31557600000000000'), 's'),
    'kg': ('mass', Decimal('1'), 'kg'),
    'g': ('mass', Decimal('.001'), 'kg'),
    'N': ('force', Decimal('1'), 'N'),
    'J': ('energy', Decimal('1'), 'J'),
    'eV': ('energy', Decimal('1.602176634e-19'), 'J'),
    'keV': ('energy', Decimal('1.602176634e-16'), 'J'),
    'MeV': ('energy', Decimal('1.602176634e-13'), 'J'),
    'Pa': ('pressure', Decimal('1'), 'Pa'),
    'kPa': ('pressure', Decimal('1000'), 'Pa'),
    'MPa': ('pressure', Decimal('1000000'), 'Pa'),
    'Hz': ('frequency', Decimal('1'), 'Hz'),
    'kHz': ('frequency', Decimal('1000'), 'Hz'),
    'K': ('temperature', Decimal('1'), 'K'),
    'm/s': ('speed', Decimal('1'), 'm/s'),
    'cm/s': ('speed', Decimal('.01'), 'm/s'),
    'km/s': ('speed', Decimal('1000'), 'm/s'),
    'm/s^2': ('acceleration', Decimal('1'), 'm/s^2'),
    'cm/s^2': ('acceleration', Decimal('.01'), 'm/s^2'),
    'km/s^2': ('acceleration', Decimal('1000'), 'm/s^2'),
    'W': ('power', Decimal('1'), 'W'),
}


def _number(raw: Decimal) -> Decimal:
    if type(raw) is bool or not isinstance(raw, Decimal):
        raise ValueError('Must be a decimal number')
    if not raw.is_finite() or abs(raw) > MAX_VALUE or (raw and abs(raw) < Decimal('1e-100')):
        raise ValueError('Values must be finite and between 1e-100 and 1e50 in nonzero magnitude')
    return raw


def _str(value: Decimal) -> str:
    # Stable, finite, JSON-portable; never serialize Decimal as binary float.
    if not value.is_finite():
        raise ValueError('Non-finite computed result')
    return str(value.normalize()) if value else '0'


def _display_derived(value: Decimal) -> str:
    # Round computed square roots/ratios to 12 significant digits to avoid
    # misleading display precision from a 55-digit working context.
    if not value.is_finite():
        raise ValueError('Non-finite derived result')
    return format(value, '.12g') if value else '0'


def _key(value: str) -> str:
    return ' '.join(value.strip().casefold().split())


class Quantity(BaseModel):
    model_config = ConfigDict(extra='forbid')
    observable: str = Field(min_length=3, max_length=110)
    conditions: str = Field(min_length=3, max_length=200)
    value: Decimal
    unit: str
    standard_uncertainty: Decimal | None = None  # asserted 1-sigma by user

    @field_validator('value', 'standard_uncertainty')
    @classmethod
    def number_range(cls, raw: Decimal | None) -> Decimal | None:
        if raw is None:
            return None
        value = _number(raw)
        return value  # Signed observations are valid; uncertainty is validated separately.

    @field_validator('standard_uncertainty')
    @classmethod
    def positive_error(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError('Standard uncertainty cannot be negative')
        return value

    @field_validator('unit')
    @classmethod
    def unit_known(cls, value: str) -> str:
        if value not in UNITS:
            raise ValueError('Unsupported or ambiguous unit; choose an exact unit from the supported list')
        return value

    @field_validator('observable', 'conditions')
    @classmethod
    def text_nonblank(cls, value: str) -> str:
        value = ' '.join(value.split())
        if len(value) < 3:
            raise ValueError('Observable and conditions cannot be whitespace')
        return value


class QuantitativeCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(pattern=r'^Q[1-6]$')
    label: str = Field(min_length=3, max_length=130)
    prediction: Quantity
    measurement: Quantity
    uncertainty_model: Literal['none', 'independent_gaussian_1sigma', 'correlation_supplied_gaussian_1sigma'] = 'none'
    correlation: Decimal | None = None

    @model_validator(mode='after')
    def valid_uncertainty_model(self):
        if self.uncertainty_model == 'correlation_supplied_gaussian_1sigma':
            if self.correlation is None or not self.correlation.is_finite() or not -1 <= self.correlation <= 1:
                raise ValueError('Correlation must be a finite value from -1 to +1')
        elif self.correlation is not None:
            raise ValueError('Correlation is permitted only with correlation_supplied_gaussian_1sigma')
        if self.uncertainty_model != 'none' and (self.prediction.standard_uncertainty is None or self.measurement.standard_uncertainty is None):
            raise ValueError('Both 1-sigma uncertainty values are required for a standardized residual')
        return self


class SourceQuoteCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(pattern=r'^Q[1-6]$')
    side: Literal['prediction', 'measurement']
    citation_id: str = Field(pattern=r'^(?:B|F[12])\.P[1-3]\.[12]$')
    exact_quote: str = Field(min_length=20, max_length=240)


class QuantitativeResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    comparisons: list[QuantitativeCase] = Field(min_length=1, max_length=6)
    research_question: str | None = Field(default=None, min_length=15, max_length=500)
    source_checks: list[SourceQuoteCheck] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def consistent(self):
        ids = [c.case_id for c in self.comparisons]
        if len(ids) != len(set(ids)):
            raise ValueError('Case IDs must be unique')
        if self.source_checks and not self.research_question:
            raise ValueError('Source checks require research_question for bounded primary-text discovery')
        seen = set()
        for s in self.source_checks:
            k = (s.case_id, s.side)
            if s.case_id not in ids or k in seen:
                raise ValueError('Source checks must refer to a unique existing case and side')
            seen.add(k)
        if self.research_question and not self.research_question.strip():
            raise ValueError('Research question must not be blank')
        return self


def compare_case(case: QuantitativeCase) -> dict:
    pred, measured = case.prediction, case.measurement
    result = {'case_id': case.case_id, 'label': case.label,
              'prediction_input': pred.model_dump(mode='json'),
              'measurement_input': measured.model_dump(mode='json'),
              'uncertainty_model': case.uncertainty_model,
              'calculation_status': 'NOT_COMPUTED',
              'scientific_validity': 'NOT_ESTABLISHED',
              'source_transcription': 'USER_ENTERED_NOT_INDEPENDENTLY_VERIFIED',
              'limitations': []}
    if _key(pred.observable) != _key(measured.observable) or _key(pred.conditions) != _key(measured.conditions):
        result['calculation_status'] = 'ABSTAINED_OBSERVABLE_OR_CONDITIONS_DIFFER'
        result['limitations'].append('Comparison requires exactly matching user-supplied observables and conditions; equivalence is not inferred.')
        return result
    pred_dim, pred_scale, canonical = UNITS[pred.unit]
    meas_dim, meas_scale, _ = UNITS[measured.unit]
    if pred_dim != meas_dim:
        result['calculation_status'] = 'ABSTAINED_DIMENSION_MISMATCH'
        result['limitations'].append('Incompatible physical dimensions; numeric discrepancy not computed.')
        return result
    with localcontext() as ctx:
        ctx.prec = 55
        p = pred.value * pred_scale
        m = measured.value * meas_scale
        d = m - p  # measurement minus prediction
        out = {'dimension': pred_dim, 'canonical_unit': canonical,
               'prediction_si': _str(p), 'measurement_si': _str(m),
               'measurement_minus_prediction_si': _str(d),
               'absolute_difference_si': _str(abs(d)),
               'standardized_residual': None, 'combined_standard_uncertainty_si': None}
        result['calculation_status'] = 'ARITHMETIC_CHECKED_ASSUMPTIONS_UNVERIFIED'
        if case.uncertainty_model == 'none':
            result['limitations'].append('No statistical comparison: explicit stochastic uncertainty model not supplied.')
        else:
            u1 = pred.standard_uncertainty * pred_scale
            u2 = measured.standard_uncertainty * meas_scale
            rho = Decimal(0) if case.uncertainty_model == 'independent_gaussian_1sigma' else case.correlation
            var = u1 * u1 + u2 * u2 - Decimal(2) * rho * u1 * u2
            # Decimal rounding can leave a tiny negative result at rho = +1.
            if var < 0 and abs(var) <= Decimal('1e-45') * max(u1*u1 + u2*u2, Decimal('1e-90')):
                var = Decimal(0)
            if var < 0:
                result['calculation_status'] = 'ABSTAINED_NUMERICAL_COVARIANCE_FAILURE'
                result['limitations'].append('Combined variance evaluated below zero.')
                return result
            u = var.sqrt()
            out['combined_standard_uncertainty_si'] = _display_derived(u)
            if u == 0:
                result['limitations'].append('Combined standard uncertainty is zero: standardized residual undefined.')
            else:
                out['standardized_residual'] = _display_derived(abs(d) / u)
            result['limitations'].append('The 1-sigma Gaussian model and error correlation/independence are user assertions, not experimentally verified.')
            result['limitations'].append('Standardized residual is descriptive only; no p-value, theory rejection, or multiple-testing adjustment is inferred.')
        result['calculation'] = out
        result['limitations'].append('Even exact numerical agreement does not independently validate physical assumptions or a scientific theory.')
        return result


def audit_quotes(checks: list[SourceQuoteCheck], ledger: list[dict]) -> list[dict]:
    checked = {r['citation_id']:r for r in verified_ledger(ledger)}
    output = []
    for link in checks:
        source = checked.get(link.citation_id)
        matched = source is not None and link.exact_quote in source['excerpt']
        rec = {'case_id': link.case_id, 'side': link.side,
               'citation_id': link.citation_id,
               'status': 'VERBATIM_QUOTE_LOCATED_NUMERIC_TRANSCRIPTION_UNVERIFIED' if matched else 'NO_VERIFIED_QUOTE_MATCH',
               'scientific_claim': 'NOT_VERIFIED',
               'numerical_value_extracted_or_verified': False}
        if matched:
            rec.update({'quote': link.exact_quote, 'doi': source['doi'],
                        'source_url': source['source_url'], 'section':source['section'],
                        'paragraph':source['paragraph'], 'excerpt_sha256':source['excerpt_sha256'],
                        'document_sha256':source['document_sha256']})
        output.append(rec)
    return output


async def run_quantitative_research(req: QuantitativeResearchRequest, *, research_runner=None, client=None) -> dict:
    """Reproducible local math; optional one bounded no-model research run.

    No truth verdicts, automated paper-number transcription or provider spending.
    """
    cases = [compare_case(c) for c in req.comparisons]
    ledger, trace, budgets = [], [], {}
    source_status = 'NOT_REQUESTED'
    if req.research_question:
        research_runner = research_runner or run_decomposed_research
        source_status = 'SOURCE_DISCOVERY_UNAVAILABLE'
        params = DecomposedResearchRequest(question=req.research_question, literature='on',
                                            arxiv='off', provider='demo', max_followups=1,
                                            max_total_papers=5, max_total_primary_papers=3,
                                            max_papers=3, max_primary_papers=2,
                                            auto_decompose=False)
        try:
            data = await research_runner(params, client=client)
            if not isinstance(data, dict):
                raise ValueError('Invalid research response')
            ledger = verified_ledger(data.get('citation_ledger', []))
            trace = data.get('execution_trace', []) if isinstance(data.get('execution_trace'), list) else []
            budgets = data.get('budgets', {}) if isinstance(data.get('budgets'), dict) else {}
            source_status = 'SOURCE_TEXT_CANDIDATES_LOCATED' if ledger else 'NO_VERIFIED_SOURCE_TEXT'
        except Exception:
            source_status = 'SOURCE_DISCOVERY_UNAVAILABLE'
    links = audit_quotes(req.source_checks, ledger)
    report = {'version':'1.8', 'engine':'ATLAS_QUANTITATIVE_CONSISTENCY',
              'quantitative_status':'USER_INPUT_ARITHMETIC_NO_SCIENTIFIC_TRUTH_VERDICT',
              'cases':cases,
              'source_audit':{'status':source_status,'source_count':len(ledger),
                              'quotes':links,'citation_ledger':ledger,
                              'execution_trace':trace,'budgets':budgets},
              'uncertainty_convention':'Each input standard_uncertainty is asserted to be a Gaussian 1σ value; no model is assumed unless explicitly selected.',
              'limitations':[
                  'All predictions, measurements, uncertainties, observables and conditions are user-entered, not extracted from papers.',
                  'Matching descriptions are a strict textual check, not independent experimental comparability verification.',
                  'Source quote presence does not validate transcription of numbers, error bars, units or context.',
                  'No causal conclusions, statistical significance declarations, theory rankings, p-values, or physical truth claims.',
                  'Source checks use best-effort upstream publication provenance; retraction/update monitoring is not guaranteed.',
              ]}
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    report['report_sha256'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return report
