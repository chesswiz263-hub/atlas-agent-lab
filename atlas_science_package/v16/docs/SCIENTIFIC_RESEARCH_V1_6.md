# ATLAS v1.6 — Controlled research decomposition

ATLAS v1.6 extends, rather than replaces, the private v1.5 scientific workflow.
The authenticated endpoint is `POST /api/science/decompose`, and the interface is
`/static/decompose.html`. The older v1.5 workflow and public offline Pages demo remain
unchanged.

## How to ask

The server accepts all v1.5 `ResearchWorkflowRequest` fields, plus:

- `subquestions`: 0–3 explicit user-specified search questions (10–240 chars).
- `auto_decompose`: when no subquestions are specified, conservatively parses only
  text shaped like `Compare A and B for C`; the resulting searches consist **only**
  of words from the user's original question. Otherwise it does not infer facets.
- `max_followups`: 0–2, default 2. Only gaps motivate a targeted follow-up.
- `max_total_papers`: maximum reserved discovery slots, default 6.
- `max_total_primary_papers`: maximum reserved full-text attempt slots, default 4.

Example:

```json
{
  "question": "Compare dark matter and modified gravity predictions for galaxy rotation curves",
  "provider": "demo",
  "literature": "on",
  "arxiv": "on",
  "max_followups": 2
}
```

Alternative with explicit facets:

```json
{
  "question": "Compare the predictions of two theories of material fatigue",
  "subquestions": [
    "What cyclic fatigue measurements are reported for alloy A?",
    "What cyclic fatigue measurements are reported for alloy B?"
  ],
  "max_followups": 2
}
```

## What coverage means (and does NOT mean)

An excerpt enters the citation ledger only if v1.3/v1.2 verifies a publication's
Crossref metadata match, source XML identity, literal excerpt locator and excerpt
SHA-256. The new orchestrator re-checks source identity labels and exact excerpt
hash before including it. Each locator gets a unique batch-qualified citation ID,
for example `B.P1.1`, `F1.P1.1`. Duplicate DOI/excerpt pairs do not count twice.

`TOPICAL_EXCERPT_LOCATED_NOT_CLAIM_VERIFIED` means overlapping terms were present
in a passage (and an automatically extracted named-theory anchor was present when
required). It does **not** mean the excerpt entails or even discusses the
scientific hypothesis correctly. `NO_VERIFIED_TOPICAL_EXCERPT` is an evidence gap
in ATLAS's retrieved material, **not** a conclusion that the literature lacks
relevant evidence. The runner never computes a truth ranking or Bayesian score.

The initial v1.5 run uses `provider=demo`, preventing a premature synthesis call.
The system may then perform at most two targeted discovery requests through the
existing guarded OpenAlex / Crossref / Europe PMC pipeline. arXiv stays metadata
only. A configured model is invoked at most **once**, explicitly opted in by
selecting a provider, and only receives crosschecked source-text excerpts.
Model citation IDs are syntactically crosschecked but **scientific entailment is
not verified**. Remote text is always data and never executable instructions.

## Budgets and failure behavior

Default slots: initial discovery up to 3 publication candidates / 2 full-text
attempts, first follow-up up to 2 / 1, second up to 1 / 1. Total <= 6 / 4.
Skipped steps do not consume their remaining reservations. Follow-up search
counts, reserved quotas and status are recorded in the report trace. These are
application-level caps on discovery calls, not a guarantee of actual HTTP
request count or elapsed time (network SDKs and provider infrastructure may
retry). The optional arXiv request and optional synthesis request are distinct
from these Crossref/Europe PMC attempt slots.

Invalid inputs fail fast. Unexpected provider and service errors are converted to
sanitized status labels, without serializing secrets from exceptions. If there
are no eligible crosschecked primary-text passages, no source-grounded scientific
answer is claimed. Symbolic, dimensional and numerical v1.4 checks remain
separate formal verification of **supplied inputs**, not scientific truth.

## Install and validate

Extract the cumulative v1.6 ZIP into an **existing** `atlas-agent-lab` checkout:

```sh
python apply_science_v16.py
python -m pip install -e '.[dev,science]'
pytest -q
node --check static/decompose.js
```

Confirm the authenticated backend is running and visit `/static/decompose.html`.
Inspect `git diff` before committing. Unit tests are mock-based; live endpoint
connectivity, the existing original repository suite, API credentials and actual
provider costs must be verified on your system. No repository push or deployment
is performed by this installer.
