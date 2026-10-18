# ATLAS v1.8 — Quantitative scientific consistency

## Scope

The authenticated API route `POST /api/science/quantitative` provides **arithmetic and provenance auditing**, not an experimental truth verdict. The private interface is `/static/quantitative.html`. No model provider is invoked.

- Up to six named, user-supplied prediction/measurement comparisons.
- Explicit exact matching of observables and experimental conditions (after whitespace/case normalization). Unmatched descriptions trigger abstention, not inference of equivalence.
- Closed unit vocabulary (dimension/scale table in `science_quantitative.py`); incompatible units abstain. This is not a general dimensional-expression parser.
- Standardized residual computed only when *both* input standard uncertainties (user-asserted Gaussian 1σ) and an explicitly asserted independence or error-correlation model are supplied. Derived square-root and ratio results are displayed with at most 12 significant digits; this is a formatting ceiling, not a claim of real-world measurement precision.
- Combined variance for prediction error `u_p` and observation error `u_m`: `u² = u_p² + u_m² − 2ρ u_p u_m`. The residual is `|measurement - prediction| / u`, undefined when `u = 0`.
- Optional bounded primary-literature discovery through v1.6, with no model call and limits of five candidates, three primary-text attempts, and one follow-up.
- `source_checks` link user-supplied verbatim substrings to citation IDs. Exact checks do **not** verify a numerical value, uncertainty, instrument reading, confidence interval, model applicability, or truth of a scientific claim.

## API example

```json
{
  "comparisons": [
    {
      "case_id": "Q1",
      "label": "Illustrative speed comparison",
      "prediction": {
        "observable": "orbital speed",
        "conditions": "galaxy radius 10 kpc",
        "value": "220",
        "unit": "km/s",
        "standard_uncertainty": "10"
      },
      "measurement": {
        "observable": "orbital speed",
        "conditions": "galaxy radius 10 kpc",
        "value": "215000",
        "unit": "m/s",
        "standard_uncertainty": "8000"
      },
      "uncertainty_model": "independent_gaussian_1sigma"
    }
  ]
}
```

**Illustrative only:** above numbers are not derived from publications or observations. ATLAS should report a measurement-minus-prediction residual of −5000 m/s, combined uncertainty `sqrt(10,000² + 8,000²)` m/s and standardized residual approximately `0.3904344047`. A residual is not a probability or independent confirmation of any theory.

To look up source text, add `"research_question": "Find published primary measurements relevant to ..."`. To audit an exact quote in a subsequent call, add:

```json
"source_checks": [
  {"case_id":"Q1", "side":"measurement", "citation_id":"B.P1.1", "exact_quote":"an exact 20–240 character substring of the citation ledger excerpt"}
]
```

Research is repeated on each request. Citation IDs are scoped to each *individual* run; they are not persistent database identifiers. Record source DOI, document and excerpt SHA-256 fingerprints, and paragraph locator in any exported report. Don't assume the next discovery will return the same batch and IDs.

## Interpretation guardrails

This release does not infer equivalent physical conditions, correlations, instrument calibration, repeated measurement dependence, sample size, selection effects, statistical significance, multiple-testing adjustments, reliability of uncertainty estimates, or theoretical truth. The source passage check verifies *verbatim substring presence only*. Correlated uncertainties must be explicitly entered. A standardized residual may be useful as a descriptive diagnostic but cannot establish a discovery or refutation by itself.

## Install

Unpack the cumulative v1.8 package into an existing checkout and run:

```bash
python apply_science_v18.py
python -m pip install -e '.[dev,science]'
pytest -q
node --check static/quantitative.js
```

No public GitHub Pages modifications or Git operations are made.
