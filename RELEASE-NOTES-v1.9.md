# ATLAS Agent Lab v1.9.0 — Scientific Source Data Extraction

**Cumulative upgrade** — designed for original v1.0–v1.8 repository layouts.

New private workspace: `/static/extraction.html`. New authenticated endpoint:
`POST /api/science/extract`.

- Discovers bounded primary-text excerpts through existing v1.6 workflows.
- Locates literal number/unit expressions and optional printed ± uncertainties
  under a closed unit vocabulary and strict numeric bounds.
- Retains DOI, source excerpt, exact span offsets, passage location, source
  SHA-256 and document SHA-256 for audit.
- Requires human review before mapping numbers to prediction/measurement roles.
- Re-fetches and rechecks both candidates before v1.8 unit-aware comparison;
  missing candidates cause explicit abstention.
- Treats statistical models as user assertions, never source-verified truth.
- Preserves v1.0 security and all v1.1–v1.8 research tools.

**Limits:** not a full-PDF/table/chart extractor, not reliable scientific fact
checking, not autonomous uncertainty-model interpretation, and not a physics
theory validation system. Full live-provider integration remains unverified.

Install: extract over original checkout, then run `python apply_science_v19.py`,
`python -m pip install -e '.[dev,science]'`, `pytest -q tests` and
`node --check static/extraction.js`. Review `git diff`. No push occurs.
