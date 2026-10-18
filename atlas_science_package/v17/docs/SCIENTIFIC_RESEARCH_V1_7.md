# ATLAS v1.7 — Claim-level evidence assessment

Authenticated private endpoint: `POST /api/science/claims`.
Private workspace: `/static/claims.html`. Original retrieval demonstration unchanged.

## Purpose and trust boundary

Version 1.7 connects **explicit, user-supplied scientific assertions** to the
validated short primary-text excerpts produced by v1.6. It does **not** prove
that a claim is correct, establish experimental reproducibility, compute
scientific confidence or perform peer review. Existing OpenAlex/Crossref/Europe
PMC discovery and citation integrity controls remain in place.

In particular, distinguishing textual *signals* is not the same as establishing
whether a sentence describes a reliable physical measurement. Labels such as
`OBSERVATION_LANGUAGE`, `PREDICTION_LANGUAGE`, `INTERPRETATION_LANGUAGE` and
`LIMITATION_LANGUAGE` are **surface-language cues**, often overlapping. Excerpts
remain capped and may omit essential methods, statistics, or broader context.

The model-assisted option can **suggest** `MAY_SUPPORT`, `MAY_CHALLENGE`,
`CONTEXT_ONLY`, or `INSUFFICIENT`. A strict gate checks the claim ID, citation ID,
exact quote substring, allowed labels, structure and limits. Even successful
validation only yields `MODEL_QUOTE_LOCATORS_CHECKED_RELATION_UNVERIFIED`; claims
keep `NOT_VERIFIED` and `human_review_required=true`. A citation may be
verbatim yet scientifically misleading if read out of context.

## Example request

```json
{
  "question": "Compare dark matter and modified gravity for galaxy rotation curves",
  "claims": [
    "Dark matter halos predict approximately flat rotation curves in a class of galaxies.",
    "A modified gravity hypothesis predicts approximately flat rotation curves for some galaxies."
  ],
  "literature": "on",
  "arxiv": "on",
  "max_followups": 2,
  "max_evidence_per_claim": 3,
  "assessment_mode": "deterministic",
  "provider": "demo"
}
```

To request **unverified model suggestions**, explicitly select
`"assessment_mode":"model_suggestions"` and a configured provider
(`"provider":"openai"`, `"anthropic"`, or `"gemini"`; optionally specify
an approved model identifier). This may incur provider charges. This mode
suppresses v1.6 model synthesis and permits only one v1.7 provider call.

## Research budgets and limitations

- 0–4 explicit claims of 15–300 characters; no automatic hypothesis invention.
- 0–3 optional explicit subquestions (v1.6 rules).
- At most three topical excerpts per claim; ledger deduplicates citations and
  checks excerpt SHA-256 and publication/source verification status again.
- Default v1.6 caps remain: six candidate publication slots, four primary-source
  attempts and two targeted follow-up searches.
- Lexical passage ranking selects *candidates*, not evidence that a claim follows.
- Provider payload includes at most six candidates and no arbitrary code tools.
- Unexpected provider and remote failures yield sanitized abstention statuses.
- A missing excerpt does not establish that the literature has no evidence.
- Bibliographic identity/full-text verification is not a current exhaustive
  retraction search, metadata repository validation or full scientific audit.
- Fingerprints identify exact local report bytes, not independent scientific
  reproducibility of an experiment or causal interpretation.

## Installing

Copy the cumulative archive into the existing ATLAS repository root. Run:

```sh
python apply_science_v17.py
python -m pip install -e '.[dev,science]'
pytest -q
node --check static/claims.js
```

Start the existing authenticated backend and visit `/static/claims.html`.
The installer does not commit, push, deploy or modify public GitHub Pages.

## Developer verification

`tests/test_science_v17.py` includes tests for fabricated source digests,
invalid DOI/document metadata, ungrounded citation IDs, absent exact quotes,
model schema injection, missing-source abstention, budget modes, and single
model-call discipline. The mocked tests do not substitute for end-to-end live
API/service checks or verification against the original repository's suite.
