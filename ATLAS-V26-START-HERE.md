# ATLAS v2.6 — Evidence-Grounded Conversational Intelligence

**Upgrade type:** additive on top of a **fully installed and committed v2.5 + your existing hotfixes**. v2.5 math, the older science workflow, login/CSRF, and model quota code are not replaced.

## What this kit does

- Makes four **separate observational research objectives** for the full dark-matter acceptance prompt: galaxy rotation curves; generic cluster weak lensing; the Bullet Cluster's separation of mass/gas signals; and CMB measurements. **MOND is not a fourth substitute for an observation.** On a MOND follow-up, ATLAS researches MOND separately and references the user's preceding question as non-evidentiary context.
- Uses a bounded OpenAlex search per research objective, with optional `ATLAS_OPENALEX_API_KEY` **or** `OPENALEX_API_KEY`. Ranks papers by observational/original-research title cues, penalizes reviews and modified-gravity papers when searching for observations, and deduplicates arXiv copies.
- Allows citations only when ATLAS has fetched an arXiv-hosted HTML/PDF copy, corroborated document title text, and extracted a precise passage. No metadata-only citations. Retains v2.5 HTTPS host restrictions, anti-redirect and byte/page limits. The old limitation to arXiv-hosted papers still applies; publisher-only landmark studies may be missed.
- Sends passages to the **existing** OpenAI adapter only if `ATLAS_LLM_ENABLED=1` and its entire quota configuration is valid. Exactly one optional reserved synthesis call per eligible research request, bounded output, no automatic retries. This is not a hard provider billing cap.
- Requires a strict JSON claim list with **exact source quotes**, category alignment, lexical similarity, numeric consistency, negation checks and an observation/interpretation/uncertainty label. Drops failing claims and reports omissions. It does **not** independently prove scientific truth, causal entailment, or peer review.
- Reuses the versioned chat UI's existing bounded `history` request field for contextual follow-ups; user history is **never** scientific evidence. No server-side personal conversation database is added.

## Install on Windows CMD, from your Git repository root

1. Commit or back up your current working tree. Preserve all v2.5 and previous upgrade files. Make sure `atlas_hosted_beta.py` is the **unmodified v2.5 reference gateway**. If you've customized it, the installer will refuse to overwrite it—merge manually instead.
2. Extract this ZIP **into your Git repository root**, preserving the `v26_assets` and `v26_tests` directories. Files are v2.6-specific; the installation does not replace v2.5 code.
3. Run:

   ```bat
   python -m pip install "httpx>=0.27,<1" "pypdf>=5,<7" "pytest>=8,<10"
   python install_atlas_v26.py
   python -m pytest -q v26_tests v25_tests
   ```

4. Run your complete regression suite using the folders **you actually have** (for example):

   ```bat
   python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests v25_tests v251_openalex_tests v26_tests
   ```

   You can omit test directories that do not exist. **Do not push if existing tests fail.**
5. Inspect `git diff` and `git status`. Commit only reviewed source and test assets; never commit `.env`, API keys, databases, `__pycache__`, `.pytest_cache`, or backups under `.git`.
6. Deploy using your existing Render build/start commands. The gateway start command remains:

   ```sh
   uvicorn atlas_hosted_beta:app --host 0.0.0.0 --port $PORT --workers 1
   ```

7. After Render reports Live, use **`/static/atlas-chat-v26.html`**. The root route and old chat redirect also lead there.

The installer fails closed if it sees a modified gateway or modified destination assets. It **never** commits, pushes, deploys, changes keys, or enables paid inference.

## OpenAlex configuration

Keep your existing `OPENALEX_API_KEY` environment variable. This release also supports `ATLAS_OPENALEX_API_KEY`, which takes precedence if both are set. Neither value is included in the diagnostics or response. API/HTTP errors are reduced to safe status codes or exception class names.

## Activate conversational synthesis **only after retrieval succeeds**

v2.6 reuses the opt-in settings already established in v2.4/v2.5:

```text
ATLAS_LLM_ENABLED=1
ATLAS_LLM_PROVIDER=openai
OPENAI_API_KEY=<in server secrets only>
ATLAS_LLM_MODEL=<your supported OpenAI model>
ATLAS_LLM_INPUT_USD_PER_1M=<verified current input price>
ATLAS_LLM_OUTPUT_USD_PER_1M=<verified current output price>
ATLAS_LLM_BUDGET_DB=<absolute SQLite path on persistent disk>
ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY=<your modest cap>
ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL=<your modest cap>
ATLAS_LLM_MAX_CALLS_PER_DAY=<your cap>
```

Obtain accurate model pricing from the current provider documentation; do not copy illustrative values blindly. Set an independent **provider-side** spending control because ATLAS reservations bound estimates, not final invoices. Keep `ATLAS_BETA_PASSWORD` and `ATLAS_COOKIE_SECRET` configured as before. Do not expose hosted beta without the existing authentication, CSRF and server rate protections.

## Live acceptance test (may incur one provider charge)

From your configured server/workspace, run:

```bat
python check_atlas_v26.py
```

The probe prints source categories located, category-specific accepted claims, missing claims, quota information, and a **textual coverage pass/fail**. A failure exits nonzero. It is intentionally stricter than just "received 4 PDFs" and does not mark a literature claim as scientifically proven.

**Human review remains a separate gate:** inspect each `citation_ledger` excerpt in the browser's *Sources, Methods & Verification* panel and read the linked primary paper. Verify observational/inferential distinctions and whether each paraphrase is actually entailed. The automated lexical screen can miss subtle inversions or mistakes.

## Troubleshooting

- `NO_ARXIV_OPENALEX_CANDIDATES`: OpenAlex results did not expose a permitted arXiv version. Inspect `openalex_results`, source-category gaps and safe `fulltext_failures`; `OPENALEX_API_KEY` is recognized here.
- `FULLTEXT_UNAVAILABLE`: Permitted article copies could not be fetched/extracted. The retriever does not scrape arbitrary publisher websites or turn abstracts into citations.
- `NO_RELEVANT_PASSAGES`: Text was extracted, but no sufficient category-specific excerpt was found.
- `SOURCE_TEXT_LOCATED_MODEL_NOT_USED`: Model is disabled, unavailable, failed, or no claims passed the textual support screen. Check `model_usage.synthesis_status` and `claim_validation.checks` without exposing keys.
- `EVIDENCE_SUMMARY_ABSTENTION`: No acceptable full-text passages were found. Missing evidence is not evidence for/against dark matter.
- Math routes remain on the preexisting SymPy process and do not require OpenAlex or a model key.

## Scope and honest limits

This kit was locally exercised against deterministic HTTP/model mocks. It was **not** installed into your live GitHub/Render account, and no paid OpenAI call or successful live OpenAlex/arXiv round trip was performed here. Sources can be original observational studies without covering the earliest publisher-only landmark studies. Claim validation is source-text matching, *not* independent semantic or peer-review verification. Continue to call it **v2.6 prototype** until the live acceptance probe and scientific spot-review pass.
