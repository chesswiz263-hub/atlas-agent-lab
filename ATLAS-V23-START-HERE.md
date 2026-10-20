# ATLAS v2.3 — Conversational Mathematics & Scientific Presentation

**Upgrade, not a replacement.** Install on the same repository where ATLAS v2.2 and the v2.2 math-language hotfix are already passing. v2.3 keeps the v1.9 science engine, v2.1 paper-discovery gateway, v2.2 restricted symbolic solver, authenticated API, primary-source locators and strict model budget rules.

## 1. Copy and install on Windows

1. In GitHub Desktop, open the `atlas-agent-lab` repository and use **Repository → Show in Explorer**. Extract **the entire ZIP** into that folder, preserving `v23_assets/` and `v23_tests/`.
2. Click the File Explorer address bar, enter `cmd`, then press Enter.
3. From that repository folder run:

```cmd
python install_atlas_v23.py
python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests
```

The installer refuses to replace unfamiliar gateway revisions, requires the tested v2.2 math hotfix and saves the prior gateway in `.git/atlas-v23-backups/` (outside the Git commit). It copies the new `static/atlas-chat-v23.*` files and adapts the isolated hosted gateway test fixture. It does not modify `docs/` or the public GitHub Pages demo. Re-running it should be safe.

If **any test fails, do not push**. Send the failure text for diagnosis. On your actual repository, the original 112-test baseline plus new tests should be rerun. The reconstructed integration test environment (not your entire repo) passed 52 tests across hosted, v2.2, hotfix and v2.3 suites.

## 2. Commit in GitHub Desktop

Review the diff. Include `atlas_conversation_v23.py`, `atlas_math_v23.py`, `atlas_hosted_beta.py`, the new `static/atlas-chat-v23.*`, `v23_assets/`, `v23_tests/`, `install_atlas_v23.py`, and the modified gateway test fixture. Don't commit `.git` backups, `__pycache__`, `.env`, secrets, or local SQLite budget files.

Suggested commit summary:

`Release ATLAS v2.3 — Conversational Math & Textbook Typesetting`

Then **Commit to main → Push origin**.

## 3. Render

Retain the existing Render Python build command and Uvicorn start command. The established build command is compatible with v2.3 (do not remove any older research-upgrade steps):

```sh
python apply_science_v19.py && python -m pip install -e ".[science]" "uvicorn>=0.27,<1" "sympy>=1.13,<2" "openai>=1.70,<3" && python prepare_atlas_hosted_beta.py
```

Start command (unchanged):

```sh
uvicorn atlas_hosted_beta:app --host 0.0.0.0 --port $PORT --workers 1
```

After GitHub push and Render deployment, log in and open:

**https://atlas-research-beta.onrender.com/static/atlas-chat-v23.html**

The gateway's `/` and `/login` flows point to v2.3 after the upgrade. The browser uses native MathML (no external JS, CDN or browser API key) for exponents, roots, derivatives, integrals, fractions and matrices; browser support requires an up-to-date Chrome, Edge, Firefox or Safari. The raw SymPy form stays accessible through **Show raw symbolic result** and **Sources, Methods & Verification**.

## 4. Verify on the hosted service

Try each in the Mathematics workspace:

- `Integrate x^2*sin(x) and explain each step`
- `Differentiate x^3+2*x`
- `Integrate x^2 from 0 to 1`
- `Gradient of x^2+y^2+z^2`

Check whether you see typeset superscripts, a readable method explanation, numbered steps and the verification status. Math remains deterministic, even when model synthesis is disabled.

Next, ask a narrow scientific question where primary papers should be discoverable, such as `What have LIGO detections revealed about binary black hole mergers? Cite primary research.` The underlying bounded discovery will run first. **If source-text passages cannot be located or citation synthesis fails, ATLAS must abstain rather than fabricate a research answer.**

## 5. Optional: enable the real language model for science

**No paid calls are enabled by installing this ZIP.** The existing OpenAI Responses API adapter is one optional, replaceable provider; ATLAS remains model-agnostic at the tool/evidence layer. Model calls are made on the server only, never from HTML. To enable, configure these **server-side Render environment variables** after confirming the provider's model identifier and published token prices:

```text
ATLAS_LLM_ENABLED=1
ATLAS_LLM_PROVIDER=openai
OPENAI_API_KEY=(your secret; never commit)
ATLAS_LLM_MODEL=(supported model ID you select)
ATLAS_LLM_BUDGET_DB=/var/data/atlas_llm_budget.sqlite
ATLAS_LLM_INPUT_USD_PER_1M=(correct, conservative input token cost)
ATLAS_LLM_OUTPUT_USD_PER_1M=(correct, conservative output token cost)
ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL=0.025
ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY=0.25
ATLAS_LLM_MAX_CALLS_PER_DAY=40
ATLAS_LLM_MATH_EXPLAIN=0
```

`ATLAS_LLM_BUDGET_DB` **must use an absolute directory on a persistent Render disk** accessible to the service (the example assumes a disk mounted at `/var/data`; do not set this until you confirm the mount). Budget estimates are conservative reservations, **not hard provider billing controls**. Disable or lower quotas if cost is uncertain. A model answer is rejected when citation IDs are invalid or substantive sentences lack citation markers. Valid citations confirm source identity, **not scientific entailment**. The response falls back to an evidence-limited answer if source checks or the provider fail. Consult the latest provider pricing rather than guessing values.

If you also set `ATLAS_LLM_MATH_EXPLAIN=1`, a bounded extra call may polish the **introductory teaching paragraph only**. It cannot replace or calculate the equations, formal steps or result, and the UI labels it as model-written. Keep this off initially to minimize spend.

## 6. Scope and limitations

- v2.3 **does not expand math-topic coverage** beyond v2.2. Some problems, domains, branch choices and assumptions require manual review. The same symbolic worker remains the authority.
- MathML rendering is supported in modern browsers but appearance can vary by OS/browser/math font.
- Plain-language explanations are tied to checked method metadata, but natural-language sentences are not formal proofs.
- Model-written science is limited to located excerpts. Passage locators and allowed citation IDs do not establish that a claim is true.
- The previous chat history in local storage includes only small math presentation metadata, not provenance reports. The full report is transient and downloadable from the expanded report in an active session.
- The hosted beta remains single-operator, password-protected, CSRF-protected and rate-limited in-process. It is not a public multiuser SaaS, and API quotas are not a substitute for provider billing alerts.

**No GitHub push, Render deploy, OpenAI model activation or spend has been performed by this installer/package.**
