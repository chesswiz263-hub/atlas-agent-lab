# ATLAS v1.9 — Source-anchored scientific numerical extraction

## Purpose and provenance boundary

The authenticated `POST /api/science/extract` endpoint searches primary scientific
sources using the existing *bounded* v1.6 literature/full-text path. It consumes
only the v1.6 verified-identity citation ledger, revalidates excerpt SHA-256 and
other locator fields using v1.7 `verified_ledger`, and scans *those excerpts*
for numeric mentions. It does not scrape arbitrary URLs, evaluate code, call
an LLM, or process whole PDFs, tables, figures, or non-open-access articles.

A candidate is an **exact numerical expression printed in a retrieved source
passage**, not necessarily an observation or prediction. That source could be
wrong, hypothetical, outdated, or quoted out of context. A DOI match and
correct excerpt hash are provenance checks, not scientific validation.

## Bounded resources

- Up to **5** literature candidates, **3** primary-text attempts and **1**
  follow-up query through the existing v1.6 policy.
- At most **24** number–unit candidates returned; maximum **4** explicitly
  human-reviewed comparisons, per request.
- Candidate extraction accepts decimal/scientific notation and an optional
  printed `±` or `+/-` uncertainty, with a **closed list of v1.8 units**.
- Compound expressions beyond the v1.8 unit table, error intervals,
  superscript notation and statistical confidence metadata are not parsed.
- No model call or inferred scientific role, uncertainty distribution,
  significance, theory verdict, paper truth score or implicit data equivalence.
- No direct external links are accepted from API clients for fetching.

## Discovery request

```json
{
  "research_question": "What are measured galaxy rotation speeds and published model predictions?",
  "max_candidates": 16
}
```

Each returned numeric candidate includes:

- `candidate_id`: deterministic SHA-256-derived ID bound to DOI, document/excerpt
  fingerprint, literal span and offsets, **not** a permanent public citation.
- `literal`, `value`, `unit`, `printed_uncertainty`: exact literal and parsed
  strings. `uncertainty_interpretation` always says `NOT_ESTABLISHED`.
- `excerpt`, `excerpt_offset`, `excerpt_sha256`, `document_sha256` to allow
  independent verification that `excerpt[start:end] == literal` and the excerpt
  hash matches its text.
- `doi`, `source_url`, `section`, `paragraph`, `citation_id` for review. Citation
  IDs are scoped to a single retrieval, never a global paper identifier.

## Explicitly reviewed comparison

First locate two suitable mentions, inspect the source passage(s), and supply
both returned candidate IDs *with the same research question*:

```json
{
  "research_question": "What are measured galaxy rotation speeds and published model predictions?",
  "max_candidates": 16,
  "comparisons": [{
    "case_id": "Q1",
    "label": "Two carefully reviewed literature values",
    "prediction_candidate_id": "N00000000000000000000",
    "measurement_candidate_id": "N11111111111111111111",
    "observable": "orbital speed",
    "conditions": "same galaxy and radius, verified by the researcher",
    "user_confirms_roles_and_context": true,
    "uncertainty_model": "none"
  }]
}
```

**Illustrative IDs above are placeholders, not real source identifiers.**
The service performs fresh research with the v1.6 budget and revalidates both
candidate IDs. Missing, changed, or mismatched citations cause **abstention**.
The user supplies both the observable and experimental conditions: ATLAS does
not infer whether two papers refer to the same galaxy, epoch, instrument,
sample or theoretical quantity.

Optional `uncertainty_model` values: `independent_gaussian_1sigma` and
`correlation_supplied_gaussian_1sigma`. The user **must** set
`user_confirms_uncertainties_gaussian_1sigma: true` and supply correlation for
the latter model. Both cited values must explicitly print a ± uncertainty. An
unqualified printed ± value is **not automatically** interpreted as standard
uncertainty. No p-values or scientific truth verdicts are reported.

## Example of extraction (invented text, not a publication)

> The model predicted 220 ± 10 km/s. We measured 215 ± 8 km/s.

Extraction would produce two *literal* candidates. If the researcher validates
roles, comparability, and a Gaussian 1σ interpretation with independent errors,
v1.8 arithmetic yields a standardized residual near 0.3904. **It does not
validate the measurements, uncertainty model, or physical theory.**

## Deploy locally

Unpack the cumulative ZIP at your existing ATLAS repository root and run:

```bash
python apply_science_v19.py
python -m pip install -e '.[dev,science]'
pytest -q tests
node --check static/extraction.js
```

Open `/static/extraction.html` on the authenticated private app. No public
GitHub Pages asset is modified. The installer refuses unexpectedly customized
v1.9 paths and is safe to run twice with unmodified installed files.

## Unverified work

Automated tests use mocked source text. Re-run the existing original repo test
suite, live OpenAlex/Crossref/Europe PMC requests, provenance verification, and
live auth/CSRF flows in the real deployment before representing ATLAS as
scientifically production-ready.
