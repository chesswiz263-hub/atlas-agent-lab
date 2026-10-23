# ATLAS v2.6.2 — evidence-precision hotfix + model-activation checklist

The 2026-10-23 live dark-matter report covered 4 categories by keyword, but used
*Bayesian estimation of our local motion from the Planck-2018 CMB temperature map*
for CMB. That is not a primary test of cosmic dark-matter density via acoustic
peaks and the temperature/polarization power spectra.

## What is patched

- Only `atlas_retrieval_v26.py`, plus an additional `v26_tests/` offline fixture.
- Excludes CMB local-motion, dipole, kinematic, foreground, and CIB papers as
  replacements for the requested cosmological evidence.
- Keeps Planck 2018 CMB **power spectra/likelihoods** and **cosmological parameters**
  eligible, even where the latter title omits the explicit acronym CMB.
- Favors measured spectra, acoustic peaks, and model-parameter results.
- Maintains bounded requests, the arXiv allowlist, hash provenance, and abstention.
- A weak selection cannot turn into a fake 4/4 success. When primary support is
  absent, return a gap instead. No paper text is invented or preloaded.
- Leaves the gateway, CSRF, login, math engine, provider adapter, and budget controls untouched.

## Install

From `C:\Users\Piano\OneDrive\Documents\GitHub\atlas-agent-lab`, extract the ZIP
with original folder paths, then run:

```bat
python install_atlas_v262.py
python -m pytest -q v26_tests v25_tests
python -m pytest -q tests
```

The installer expects the v2.6.1 source hash; refuses unexpected modifications.
Commit/push only after `git diff` review and all three suites pass. Running the
installer twice is safe.

## Enable ATLAS's real LLM on Render (separate operator action)

Your log says `model_configuration_status=DISABLED`, so no model could have
been called. v2.6.2 does NOT change that setting. To enable, you must first
attach a real **persistent Render disk** to the service, e.g. mounted at
`/var/data`. Without a persistent disk, SQLite quota history resets on deploy,
which invalidates the intended spending guard. Render persistent disks require
an eligible paid service; do not fake persistence by only writing an absolute path.

Under Render Dashboard > your service > Environment, set these only after
reviewing cost safeguards:

```text
ATLAS_LLM_ENABLED=1
ATLAS_LLM_PROVIDER=openai
OPENAI_API_KEY=<your private API key; never commit it>
ATLAS_LLM_MODEL=gpt-5.4-mini
ATLAS_LLM_INPUT_USD_PER_1M=0.75
ATLAS_LLM_OUTPUT_USD_PER_1M=4.50
ATLAS_LLM_BUDGET_DB=/var/data/atlas_model_quota.sqlite3
ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY=0.15
ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL=0.015
ATLAS_LLM_MAX_CALLS_PER_DAY=20
```

Prices above are standard text-input/output rates for the named model,
checked against the OpenAI model page on 2026-10-23; verify current regional,
priority, and long-context pricing before enabling. Keep a separate OpenAI
project-level billing/spend alert/control: the local quota is a best-effort
reservation estimator, not a hard vendor spending limit. If model access is
unavailable for your API account, select a supported model and update both rates.

IMPORTANT: A Render *free* instance with an ephemeral filesystem cannot meet
this release's persistent SQLite quota requirement. Leave `ATLAS_LLM_ENABLED=0`
until a durable quota backend is configured. Never expose the beta key or
`ATLAS_COOKIE_SECRET` in browser JavaScript or Git.

After deployment, query the original dark-matter prompt and inspect
`research_diagnostics.model_configuration_status`, `model_attempted`,
`model_usage.calls`, `claim_validation.checks`, and the exact primary citations.
A `READY_TO_ATTEMPT` status does not guarantee a working model or accepted claims.

## Verification completed locally

`python -m pytest -q v26_tests v25_tests`: **34 passed**, mocked evidence / model;
no paid call or live OpenAlex/arXiv/Render request. The full original repository
CI suite must still pass in your GitHub Actions environment.

## Primary literature targets

- Planck Collaboration, *Planck 2018 results. V. CMB power spectra and likelihoods*,
  arXiv:1907.12875.
- Planck Collaboration, *Planck 2018 results. VI. Cosmological parameters*,
  arXiv:1807.06209.

These are ranking/search targets; ATLAS **must fetch the actual text before citing**.
