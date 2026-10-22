# ATLAS v2.4 — Source-Grounded Conversational Research

This is a **small additive upgrade** for an existing, working v2.3.1 checkout. It does not overwrite the SymPy worker, research discovery engine, source-verification logic, v2.3 MathML renderer, GitHub Pages demo, or credentials. A prior v2.3 hosted gateway is copied into `.git/atlas-v24-backups/` before replacement.

## What changes

- The hosted chat invokes the existing OpenAI **Responses API adapter** *after* ATLAS's bounded primary-text discovery. The scientific model receives a limited set of the source excerpts and cannot issue tool or web searches itself.
- The main scientific answer is fluent prose with bracketed source IDs. Every substantive sentence needs a valid source ID at its end. Unknown IDs, unsupported numeric literals, suspicious markup and ungrounded citations trigger the deterministic evidence-limited fallback. **Citation-ID validation is not proof of scientific entailment, truth or peer review.**
- Citations without a verified external URL can open the matching source excerpt in the expandable `Sources, Methods & Verification` section. The section retains the full raw research report.
- The host advertises `model_enabled` only when the required secrets, model, prices, caps and absolute SQLite ledger path are configured. Its public status never returns credentials.
- v2.3.1 numerical math, natural-language parsing, step explanations, formal verification and math rendering remain unchanged. Math-only problems do not require paid synthesis. Optional model-written math intros remain disabled by default.

## Installation (Windows)

1. **Back up or commit current work.** Extract this ZIP at the repository root, beside `pyproject.toml`, `atlas_hosted_beta.py`, `atlas_conversation_v23.py`.
2. In that folder, run:

   ```cmd
   python install_atlas_v24.py
   python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests
   ```

3. If all tests pass, inspect changes in GitHub Desktop. Include the new module, gateway, v2.4 static files, installer, and tests. Do **not** commit `.env`, key files, backup directories, caches, database files, or secrets.
4. Commit: `Release ATLAS v2.4 — Evidence-Grounded Conversational Research`, and Push origin.
5. Render: retain your current science-installing Build Command and the `uvicorn atlas_hosted_beta:app --host 0.0.0.0 --port $PORT --workers 1` Start Command. Ensure the build installs `"openai>=1.70,<3"` and `"sympy>=1.13,<2"`, otherwise append those package requirements to the existing pip command. **Do not remove `apply_science_v19.py`.**
6. Wait for Render to report Live. Open `/static/atlas-chat-v24.html` on your private Render service and log in normally.

The installer refuses unknown gateway or parser versions; it does not attempt to guess a merge. If it refuses, preserve the current files and inspect differences before changing anything.

## Activation — complete only after deployment succeeds

**This installer does not connect your account or turn on paid API calls.** Set these values using **Render → your ATLAS service → Environment** (never paste an API key into chat, GitHub, or the frontend). Use the following as an illustrative configuration; verify current prices and model availability in the provider's dashboard.

| Environment name | Example | Notes |
|---|---|---|
| `OPENAI_API_KEY` | `your-secret-key` | **Secret value entered only in Render** |
| `ATLAS_LLM_ENABLED` | `1` | `0` disables all model calls |
| `ATLAS_LLM_PROVIDER` | `openai` | v2.4 ships one real adapter, with separable provider boundary |
| `ATLAS_LLM_MODEL` | `gpt-4o-mini` | A small non-reasoning model; check provider availability and pricing |
| `ATLAS_LLM_INPUT_USD_PER_1M` | `0.15` | Conservative configured input price, USD/million tokens |
| `ATLAS_LLM_OUTPUT_USD_PER_1M` | `0.60` | Conservative output price; set higher if warranted |
| `ATLAS_LLM_BUDGET_DB` | `/var/data/atlas-model-budget.sqlite` | **Absolute path on a persistent Render disk**. Must exist/writable at runtime; do not store in Git |
| `ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL` | `0.01` | Estimated reservation per call (not guaranteed provider bill) |
| `ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY` | `0.10` | Budget-limiter reservations per UTC day |
| `ATLAS_LLM_MAX_CALLS_PER_DAY` | `20` | Maximum model call attempts per UTC day |
| `ATLAS_LLM_MATH_EXPLAIN` | `0` | Keep math LLM introductions off until research synthesis is validated |

Prices shown above were published for `gpt-4o-mini` as of the v2.4 preparation; the model is marked deprecated, so choose another supported model **and its current documented prices** if this model is unavailable. The model name may be changed without code changes. For lower-risk initial testing, set a conservative daily cap and explicitly limit provider-project spend in your OpenAI billing settings. **The application ledger is an estimated app-managed quota, not a hard vendor billing cap. Failed calls consume a reservation.**

### Persistent storage matters

The previous v2.2 quota is a SQLite ledger. If the disk holding `ATLAS_LLM_BUDGET_DB` is ephemeral, redeployment or container restart can reset the ledger. Do **not** activate a paid model without a persistent mounted directory or a replacement remote budget store. An absolute path alone is not sufficient to guarantee persistence.

### What to test

1. With `ATLAS_LLM_ENABLED=0`, ask a calculus question. It should still render and check the result without an API call.
2. Ask a narrow scientific question which should retrieve a relevant source-text passage. Open `Sources, Methods & Verification`: confirm source IDs and excerpts actually exist.
3. Turn on the model **only after budget storage is confirmed**. For a source-backed question, expect a conversational answer with inline `[B.P…]` references, rather than a raw report. For a question with no located relevant text, expect an abstention without a model call.
4. If the model returns unknown IDs, unsupported numbers, or text that cannot pass validation, expect a source-limited fallback. This is intended behavior, not a citation generator failure.
5. Check the model status in Tools. It reports whether configuration is ready, not whether billing and entitlements have been independently verified.

## Boundaries

- v2.4 is a **private, single-operator beta**, not a public multi-tenant product. The Python server remains password gated, HTTPS same-origin, CSRF protected and rate limited in process.
- **No live provider test was executed in this offline package build.** API keys, billing permissions, provider network calls and Render deployments are entirely up to you.
- Source IDs and lexical passage selection are provenance/attribution controls, **not semantic entailment verification**. Model outputs can still misinterpret located text. Audit every scientific conclusion.
- Published source titles/excerpts can contain hostile prompts. They are marked untrusted; do not assume instruction-following or model output checks fully eliminate prompt injection.
- Source discovery and article text must be available and relevant. Enabling a language model cannot solve `DISCOVERY_UNAVAILABLE`, missing source text, or incomplete primary-text extraction.
- Use an actual billing/provider budget as a second safety layer. Even when the model request uses `store=False`, review the provider's data handling policies for research data.

## Sources for operator verification

- OpenAI Responses API: https://developers.openai.com/api/docs/guides/text
- OpenAI GPT-4o Mini model page and token pricing: https://developers.openai.com/api/docs/models/gpt-4o-mini
- OpenAI model catalog: https://developers.openai.com/api/docs/models
- Render disk/runtime docs: https://render.com/docs/disks
