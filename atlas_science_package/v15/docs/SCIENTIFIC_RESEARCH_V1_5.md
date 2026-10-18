# ATLAS v1.5 — Unified Scientific Research Workflow

Version 1.5 extends the private v1.0–v1.4 ATLAS application. It does not replace
its model provider runtime, allowlist, cost/step budgets, traceability facilities,
existing science pages, or the deterministic offline public Pages demonstration.

## New private surfaces

- `POST /api/science/workflow` accepts a `ResearchWorkflowRequest` JSON body.
- `/static/workflow.html` is a private interactive research workspace.
- Exports are complete user-triggered JSON downloads containing a report SHA-256
  fingerprint, bounded plan, execution trace, literature candidates, actual
  repository-text locators when available, theory comparisons, formal checks,
  assumptions, and explicit verification status labels.

## Example: compare two structured predictions

```json
{
  "question": "Compare two hypotheses for galaxy rotation curves in low-acceleration systems",
  "literature": "on",
  "arxiv": "on",
  "provider": "demo",
  "theories": [
    {"name": "Hypothesis A", "predictions": [{"observable": "rotation curve deviation", "condition": "under matched low-acceleration conditions", "expected_direction": "increase"}]},
    {"name": "Hypothesis B", "predictions": [{"observable": "rotation curve deviation", "condition": "under matched low-acceleration conditions", "expected_direction": "decrease"}]}
  ]
}
```

This *flags a conflict between the entered predictions*. It does not claim that
those physical models make those predictions; the researcher is accountable for
the entered observables, conditions and directions. Lexical source matches are
not experiments proving or disproving a theory.

## Example: solve mathematics without an external lookup

```json
{"question": "Differentiate x**2 + 3*x"}
```

The conservative parser can automatically recognize simple `differentiate`,
`integrate`, `solve`, and `simplify` requests with a bounded algebraic expression.
Do not expect automatic extraction of equations from prose, graphs or papers.
Alternatively provide `symbolic_tasks`, `dimensional_tasks` or
`numerical_tasks` as structured arrays. These use existing v1.4 validators.

## Verification semantics

1. OpenAlex candidate metadata is bibliographic *discovery only*.
2. Crossref DOI/title/year checks verify bibliographic record agreement, not
   correctness of reported methods or findings.
3. Matching eligible Europe PMC full-text XML establishes a repository source
   identity and literal passage location, not scientific entailment. The ledger
   checks exact excerpt SHA-256 fingerprints and provenance labels before use.
4. arXiv entries are preprint *metadata only*. They must never be presented as
   independently verified full-text passages or as peer-reviewed evidence.
5. Mathematical calculations check formal consistency for the stated
   expressions, units and idealized physical models, not physical truth.
6. Optional model interpretation is a single explicit-provider call, only when
   the ledger contains crosschecked source text. Literal citation IDs must match
   ledger entries; this DOES NOT prove that the text supports the model's claim.
7. If discovery or evidence is unavailable, the workflow reports it and abstains
   from a source-supported scientific answer. The report is deliberately not a
   general-reasoning scientific verdict.

## Bounded execution and costs

Four deterministic stages maximum: literature / arXiv metadata / calculations /
report. Up to three OpenAlex candidates, three Crossref lookups, two OA article
full-text attempts (each may require DOI lookup and XML retrieval), and three
arXiv records. At most one explicitly selected synthesis call. No user-provided
URLs, dynamic agent tool selection, arbitrary Python execution, or autonomous
additional searches. Existing backend authentication and CSRF middleware must
protect the new endpoint as they protect other `/api/science/*` endpoints.

The network-call estimate is a first-attempt bound for normal endpoints, not an
SLA; external HTTP libraries, model providers, or deployment-side infrastructure
may have their own retries or rate limits. arXiv pacing is per process; use an
external shared limiter for multi-worker deployments.

## Running the upgrade and tests

Copy the cumulative ZIP contents into an *existing repository clone* and run:

```sh
python apply_science_v15.py
python -m pip install -e '.[dev,science]'
pytest -q
node --check static/workflow.js
```

Open the private backend's `/static/workflow.html` after starting it in your
usual way. Check `git diff` before committing. Run the full app test suite and
live connectivity tests in your environment; package tests use mocked responses,
not a live Crossref, Europe PMC, arXiv, or model provider account.

No git commits, pushes or service deployments are performed by the installer.
