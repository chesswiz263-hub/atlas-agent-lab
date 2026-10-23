# ATLAS v2.6.1 — CMB Retrieval and Model Diagnostics Hotfix

Based on the first actual ATLAS v2.6 research output (October 23, 2026).

## What the log showed

- Four fetched arXiv repository documents, but useful source text for **three** of four requested areas. The selected CMB lead was a **cosmic infrared background (CIB)** paper, NOT a CMB acoustic-peak measurement. No CMB source-text evidence was accepted.
- The model had `model_attempted: false` and `model_usage.synthesis_status: DISABLED`. Zero claims passed because zero model claims were generated. OpenAlex and OpenAI keys are different services.
- Several quotations began in the middle of words because the older passage windowing sliced on fixed character positions.

## What this changes

1. Blocks CIB titles from counting as CMB measurement sources and requires a plausible category-specific title AND fetched excerpt.
2. Searches up to **two extra metadata queries only when source-text coverage remains missing**, prioritizing CMB; stays within **six OpenAlex queries, eight fetched papers, twelve full-text attempts, four megabytes per download, eight PDF pages, and the existing ~65-second retrieval budget**.
3. If a paper's extracted text does not support the selected topic, tries another candidate instead of prematurely marking the category covered.
4. Prefers research-result phrasing over literature-review sentences when selecting passages, and creates word-aligned citation excerpts.
5. Returns distinct public-safe status for LLM **disabled**, LLM **attempted but unavailable**, and LLM **returned unsupported claims**. Provider error messages and keys are never returned.
6. Adds five-plus mocked regression scenarios reproducing CIB confusion and disabled-model diagnostics.

No configuration values, gateways, authentication, math workers, deployment scripts, provider cost quotas, or existing data stores are overwritten. The installer backs up changed code in `.git/atlas-v261-backups/`.

## Install — Windows Command Prompt

Back up or commit the current v2.6 code. Extract ZIP into the **root of `atlas-agent-lab`**, preserving subfolders. From that root:

```bat
python install_atlas_v261_hotfix.py
python -m pytest -q v26_tests v25_tests
```

If it prints `STOP`, **do not manually force an overwrite**; your local v2.6 code differs from the reviewed original. Report the message for a safe merge.

Review `git diff` and `git status`. Commit reviewed source and tests and push only after green tests. Redeploy on Render using your existing workflow.

## Activate model synthesis separately, in Render, only when desired

v2.6 model synthesis remains intentionally **opt-in**. In your Render service's environment settings, make sure the following are configured **on Render** (not merely in Windows CMD):

```text
ATLAS_LLM_ENABLED=1
ATLAS_LLM_PROVIDER=openai
OPENAI_API_KEY=<secret value, never commit>
ATLAS_LLM_MODEL=<available supported model name>
ATLAS_LLM_INPUT_USD_PER_1M=<verified current input price>
ATLAS_LLM_OUTPUT_USD_PER_1M=<verified current output price>
ATLAS_LLM_BUDGET_DB=<absolute path on actually persistent storage>
ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY=<app daily reserve cap>
ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL=<per-call reserve cap>
ATLAS_LLM_MAX_CALLS_PER_DAY=<integer cap>
```

`OPENALEX_API_KEY` authorizes OpenAlex literature discovery; it **does not** activate OpenAI model synthesis.

An **absolute path alone does not mean the path is persistent**. ATLAS needs a real persistent volume for the SQLite quota database; without one, DO NOT enable paid synthesis. Also use an independent provider-side spending control. The quota reserves conservative *estimated* charges rather than bounding provider billing itself. Your existing protected beta requires `ATLAS_BETA_PASSWORD` and `ATLAS_COOKIE_SECRET` unchanged.

For read-only settings diagnostics (in the **actual** Render service environment):

```bat
python check_atlas_v261_readiness.py
```

This prints missing **variable names only**, not secret values. It does not prove persistence or provider-side billing limits and makes **zero** provider calls. Locally, it inspects the local environment, not Render's settings.

Then explicitly run `python check_atlas_v26.py` on the configured service environment when you're ready to permit the bounded model call. Inspect categories, claim screening, and quoted papers for accuracy. A green text screen is NOT scientific semantic-entailment verification.

## Caveats

Tests use mocked OpenAlex/arXiv and a mocked language model and **do not prove real CMB retrieval, model call success, or scientific correctness**. ATLAS still cites arXiv-hosted copies only, and a paper with superficially relevant text may not actually establish the claim. Human reading remains a release gate.
