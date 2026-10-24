# ATLAS v2.6.3 — Full-text CMB recovery hotfix

## What the 2026-10-23 live report showed

The v2.6.2 precision guard correctly rejected CMB local-motion/dipole studies as substitutes for cosmological dark-matter evidence, but OpenAlex did not return a suitable eligible paper. The report fell back to 3/4 requested source categories. The LLM was separately DISABLED and made no calls.

## Change

A bounded, curated *discovery* fallback adds two independent, identifiable original Planck collaboration studies if OpenAlex fails to supply full-text CMB evidence:

- Planck 2018 results VI. Cosmological parameters, arXiv 1807.06209, DOI 10.1051/0004-6361/201833910.
- Planck 2018 results V. CMB power spectra and likelihoods, arXiv 1907.12875, DOI 10.1051/0004-6361/201936386.

For these two identifiers ONLY, ATLAS tries a full-text HTML rendering at `https://ar5iv.labs.arxiv.org/html/{id}` (a third-party rendering of the original arXiv source, **not** an independently peer-review-certified document). It uses the preexisting no-redirect, bounded-byte HTTP fetcher and shared attempt/time budgets. It checks the first actual HTML article heading against the expected paper title and insists on an abstract or introduction body marker and relevant passage. No embedded abstract, citation, or factual conclusion is substituted for a fetched passage. Thus a failed fetch is still a genuine missing-evidence result. Authors' lengthy affiliation blocks are skipped for passage selection.

It labels the fetched text's transformed provenance, preserves SHA-256 document and excerpt hashes and the other citation controls. It changes only the research retriever, one research disclaimer, and relevant tests. It does not activate paid models, modify the hosted gateway, or modify authentication. You can opt out with `ATLAS_V26_CMB_CURATED_FALLBACK=0`.

## Install

1. Unzip the contents into the root of the existing Git repository. It requires v2.6.2 to be present; it will stop if files have unexpected local changes.
2. Run `python install_atlas_v263.py`.
3. Run `python -m pytest -q v26_tests v25_tests` and `python -m pytest -q tests`.
4. Only if green, review `git diff`, `git add atlas_retrieval_v26.py atlas_conversation_v26.py v26_tests`, `git commit -m "Improve Planck CMB source recovery"`, then `git push`.
5. Retest the dark matter question in Render and inspect `research_diagnostics.curated_cmb_fulltext_attempts`, `curated_cmb_fulltext_accepted`, `categories_covered`, `fulltext_failures`, and `citation_ledger`.

## Conversational-model activation is a SEPARATE task

`model_configuration_status: DISABLED` means `ATLAS_LLM_ENABLED` is not `1` in the Render service. Do not enable it until `OPENAI_API_KEY`, `ATLAS_LLM_MODEL`, accurate per-million-token input/output prices, daily/per-call caps and call cap are configured, an *actually persistent* SQLite budget path is available, and a provider-side spending limit is confirmed. Do not put credentials into GitHub, a static frontend, or screenshots. Only edit those values in Render's secret environment configuration. Source retrieval can be evaluated while the model is off.

## Tests and limits

39 local offline tests passed against the v2.5+v2.6 subset (no live API calls). The 77-test historical `tests/` directory is not present in the isolated release fixture and was not run here. The external ar5iv service could still refuse, redirect, or return oversized content: the system must then abstain rather than invent evidence. Retrieved source text is NOT a verified scientific claim; model synthesis still requires separate validation.
