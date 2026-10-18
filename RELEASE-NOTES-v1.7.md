# ATLAS v1.7.0 — Scientific claim assessment

New, additive authenticated endpoint: `POST /api/science/claims`.
New private interface: `/static/claims.html`.

- Supply up to four scientific assertions explicitly; ATLAS will not manufacture
  unasked hypotheses from a general research question.
- Correlate each claim with at most three provenance-checked primary-text
  passages; preserve article DOI, source locator, excerpt fingerprint, batch ID.
- Show distinct textual cues for measurements, predictions, interpretations and
  uncertainty; these are word-pattern signals, **not scientific validation**.
- Optional one-call provider classification (MAY_SUPPORT, MAY_CHALLENGE,
  CONTEXT_ONLY, INSUFFICIENT) with strict citation/quote/schema checks.
- Model suggestions are **never promoted to established scientific entailment**.
- Preserve v1.6 bounded decomposition and previous mathematics, physics,
  literature discovery and research demos.
- Return explicit gaps, human-review flags, execution trace, request budgets
  and report SHA-256; export JSON from the browser.

Testing: network-free adversarial suite and installer smoke checks must pass
before integrating with actual ATLAS checkout. Live discovery, citation providers,
models and original project integration should be tested in your environment.

No GitHub commit/push, deployment or website change is performed.
