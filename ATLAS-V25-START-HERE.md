# ATLAS v2.5 — Scientific Discovery & Evidence Intelligence

A deliberately bounded upgrade over ATLAS v2.4.1. Installs an additive retrieval/router module, a versioned hosted chat interface, and a **small mathematics presentation correction**. Preserves the v2.4.1 math worker, the v1.9 science routes, v2.4 LLM provider/budget ledger and the existing login/CSRF gateway.

## Install (Windows CMD in the GitHub repository root)

1. Commit or back up any unrelated work first; do not unzip over uncommitted customizations.
2. Extract the **whole ZIP into the repository root**. Preserve subdirectories `v25_assets/` and `v25_tests/`.
3. `python -m pip install "pypdf>=5,<7"`
4. `python install_atlas_v25.py`
5. `python -m pytest -q v241_tests v25_tests`
6. **Full local suite** (with all earlier upgrades installed):

   `python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests v25_tests`

7. Inspect `git status` and `git diff`; do not commit `.env`, local databases, API keys, `__pycache__`, `.pytest_cache` or `.git` backups.
8. Commit and push *only if all local tests pass*. Suggested summary: `Release ATLAS v2.5 — Scientific Discovery & Evidence Retrieval`.

The installer checks that the active gateway is **exactly** the unmodified v2.4.1 gateway, and checks all target UI assets before copying. It does not overwrite customized files, push to GitHub, deploy Render, create accounts, or set keys. Repeated installation is safe.

## Render deployment

Keep the existing **start command**:

`uvicorn atlas_hosted_beta:app --host 0.0.0.0 --port $PORT --workers 1`

Add **only** the `pypdf` constraint to your existing **build command**. An example retaining the previously used v1.9 preparation:

`python apply_science_v19.py && python -m pip install -e ".[science]" "uvicorn>=0.27,<1" "sympy>=1.13,<2" "openai>=1.70,<3" "pypdf>=5,<7" && python prepare_atlas_hosted_beta.py`

**Do not replace your build command blindly** if your own command has further changes. Importantly, preserve v1.9 science dependencies and the command that prepared the original gateway; the v2.5 gateway was committed during local installation, and must not be overwritten by deployment scripts.

After Render reports Live, visit:

`https://atlas-research-beta.onrender.com/static/atlas-chat-v25.html`

### Optional server-side environment variables

- `ATLAS_V25_RETRIEVAL_ENABLED=1` (default; use `0` to disable v2.5 retrieval)
- `ATLAS_V25_LEGACY_FALLBACK=1` (default; reuses the older v1.9/v2.4.1 retrieval path when new full-text evidence is unavailable). This adds time and upstream requests. Use `0` during diagnosis if latency becomes excessive.
- `ATLAS_OPENALEX_API_KEY` — optional OpenAlex API key, entered in Render only, depending on current API quotas and plan. Never commit it.

**Real LLM synthesis remains opt-in**. These variables must be configured from our previous v2.4 setup on the server, using a persistent budget DB on a persistent disk:

`ATLAS_LLM_ENABLED=1`, `OPENAI_API_KEY`, `ATLAS_LLM_PROVIDER=openai`, `ATLAS_LLM_MODEL`, `ATLAS_LLM_INPUT_USD_PER_1M`, `ATLAS_LLM_OUTPUT_USD_PER_1M`, `ATLAS_LLM_BUDGET_DB` (absolute path on persistent disk), `ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY`, `ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL`, `ATLAS_LLM_MAX_CALLS_PER_DAY`.

Choose actual provider model and accurate pricing from its current documentation. Start with a small daily estimated budget and a separate provider-side billing limit. App reservations are estimated, not a guaranteed vendor billing cap. **Do not enable paid synthesis before checking the retrieval diagnostics.**

## What changed

- **Question planning**: explicit subqueries for common multi-observation dark matter questions; a conservative general-purpose planner for other topics. Max four subqueries and four returned records per subquery. No autonomous unbounded planning.
- **Full-text source acquisition**: OpenAlex discovers works; a candidate must expose an arXiv-hosted location. Fetches arXiv HTML or falls back to arXiv PDF and extracts up to eight pages. No redirects, no arbitrary paper-host URLs, max 4 MB per response, max four papers.
- **Passage ranking**: lexical overlap with planned subquestions, up to six selected source excerpts with at most two per document/subquestion. An excerpt has a content hash, document hash, source URL and passage/page locator if available.
- **Answer generation**: existing v2.4 strict model configuration and SQLite quota reservation; only located excerpts are supplied. Existing citation ID/numeric-literal validation is retained. No model call if zero passages, no citations invented. A model-generated sentence that passes these checks is **still not scientifically entailed/verified**.
- **Fallback**: existing original science workflow is retained as an opt-in/default fallback, not removed; no abstracts or publication records are upgraded to full-text evidence.
- **Mathematics**: repaired the `False` characteristic-equation step in a new isolated v2.5 worker, retaining v2.4.1's verified result and handling. Removes repeated headings from some math presentation steps.

## Diagnostic labels

Look under **Sources, Methods & Verification → research_diagnostics**:

- `NO_ARXIV_OPENALEX_CANDIDATES`: searches ran, but no selected OpenAlex works offered permitted arXiv copy identifiers.
- `FULLTEXT_UNAVAILABLE`: candidates found, but all arXiv HTML/PDF copies failed retrieval or identity checks.
- `NO_RELEVANT_PASSAGES`: source text was extracted but passage selection found insufficient topical overlap.
- `PASSAGES_LOCATED`: at least one citeable exact source span was recorded.
- `model_usage.synthesis_status: OFF`: paid model synthesis is disabled; research can still retrieve evidence.

Tests use **mock HTTP transport** and a simulated model. We did **not** make a successful live OpenAlex/arXiv full-text round trip or charge an LLM in the build environment. Live deployment must be measured, especially for astrophysics papers lacking HTML or whose PDFs are not extractable. Publisher PDFs, non-arXiv copies, HTML with scripts, and scanned image-only papers are outside this initial retriever.

## Validation scope

`python -m pytest -q v241_tests v25_tests`: **27 passed** in our reconstructed package environment, including gateway login/CSRF checks, URL restrictions, byte/redirect limits, mock full-text extraction, source identity, citations and ODE regression. The much larger historical combined suite was not completed here due to a timeout during an older v2.4 math test. Your actual Git checkout must complete its full suite before pushing.
