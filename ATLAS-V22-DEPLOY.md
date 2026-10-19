# ATLAS v2.2 — conversational science + mathematics

**Additive upgrade for the installed v2.1 hosted beta.** It preserves the original scientific workflow, exact source-text checks, numerical and symbolic checks, private operator login, and the offline GitHub Pages site. **Do not replace the old scientific modules.** This installation only updates the hosted gateway, adds two isolated engine files and new versioned chat assets.

## Install (GitHub Desktop workflow)

1. In GitHub Desktop, make sure your current changes are committed; optionally create a new branch called `atlas-v22`.
2. Extract the ZIP **into the root of `chesswiz263-hub/atlas-agent-lab`**, alongside `pyproject.toml` and `atlas_hosted_beta.py`.
3. In a terminal at the repo root, run:

   ```bash
   python install_atlas_v22.py
   python -m pip install -e ".[dev,science]" "openai>=1.70,<3"
   python -m pytest -q tests v22_tests
   node --check static/atlas-chat-v22.js
   ```

   `install_atlas_v22.py` refuses unknown modifications to the gateway, creates `atlas_hosted_beta.v21.backup.py`, and leaves existing `/docs` and static v2.0 files untouched. Delete the backup file from the commit **after reviewing** it, or add it to `.gitignore` (it does not contain passwords if environment setup was correct). The legacy tests are adjusted only if the expected original fixture is found.
4. Check your diff. Commit and push to GitHub using GitHub Desktop. The **hosted Render service** should rebuild on `main` if its deploy settings enable automatic deployment. Otherwise deploy the new commit manually in Render.
5. Your existing Render start command remains:

   ```bash
   uvicorn atlas_hosted_beta:app --host 0.0.0.0 --port $PORT --workers 1
   ```

   Change its build command to install SymPy and the OpenAI client:

   ```bash
   python -m pip install -e ".[science]" "uvicorn>=0.27,<1" "openai>=1.70,<3"
   ```

6. Open your **private authenticated** Render URL. `/login` and `/` now lead to `/static/atlas-chat-v22.html`. The previous `/static/atlas-chat.html` redirects to the new private chat. GitHub Pages stays an offline demo.

## Turn on conversational synthesis without uncontrolled provider calls

Math calculations and live literature discovery remain available even with synthesis off. **Model synthesis defaults to off**, as required by v2.1's private-beta safety design. If you have a persistent Render disk and a paid model account, configure the following as **Render environment variables**, never as repository files or browser settings:

| Variable | Example / meaning |
| --- | --- |
| `ATLAS_LLM_ENABLED` | `1` to opt into paid synthesis |
| `ATLAS_LLM_PROVIDER` | `openai` (adapter boundary is replaceable; more providers may be added) |
| `OPENAI_API_KEY` | Your secret server-side credential |
| `ATLAS_LLM_MODEL` | An actual Responses-API-compatible model ID enabled on your account |
| `ATLAS_LLM_BUDGET_DB` | **Absolute path on a persistent mounted disk**, e.g. `/var/data/atlas-model-budget.sqlite3` |
| `ATLAS_LLM_INPUT_USD_PER_1M` | Conservative input token price for **your selected model** (USD/million) |
| `ATLAS_LLM_OUTPUT_USD_PER_1M` | Conservative output token price for **your selected model** (USD/million) |
| `ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL` | Defaults to `0.025` (estimate only) |
| `ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY` | Defaults to `0.25` (estimate only) |
| `ATLAS_LLM_MAX_CALLS_PER_DAY` | Defaults to `40` |

The model is **not called** when keys, pricing, quota DB or opt-in are absent. A **single Responses API call** can synthesize a research answer *only after* the deterministic engine has found relevant primary-source excerpts. Synthesis has at most 6 excerpts, 9,000 prompt characters, 550 output tokens and zero automatic retries. A SQLite transaction reserves a conservative cost estimate **before** making the call. Failures do not refund the reservation. The original per-session hourly request throttling and two-run concurrency limit remain. For maths, no model call is needed for supported expressions.

**Important limits:** The app-managed estimated quota is **not a guaranteed ceiling on your provider invoice**, and a Render environment without a persistent disk can lose quota history on a restart. Use your provider's own spending limits and project controls as additional safeguards. `ATLAS_LLM_ENABLED=0` provides a true no-provider-call default for this new chat flow.

## How answers work

```text
Question → workspace router
    ├── Math → restricted AST → isolated, time-limited SymPy process
    │            → step-by-step derivation → explicit verification status
    └── Research → existing v1.9 discovery, provenance and math checks
                    → lexical-anchor relevance ranking + source diversity
                    → bounded model synthesis (only when enabled)
                    → citation-ID checks → readable answer or abstention
                    → expandable Sources, Methods & Verification
```

### Example mathematics questions

- `Calculate (3+4)*7` — exact arithmetic
- `Solve x^2-4=0` — real roots with substitution checks
- `Differentiate sin(x^2)` — chain rule
- `Integrate 3*x^2+2*x+1` — term-by-term reverse power rule, derivative check
- `Integrate x^2 from 0 to 1` — definite integral
- `Limit of sin(x)/x as x -> 0` — limits
- `Series of sin(x) around x=0 order 6` — Taylor series
- `Sum of 1/n^2 from n=1 to oo` — convergent infinite sum
- `Gradient of x^2+y^2+z^2` — multivariable partial derivatives
- `Divergence of [x^2, y^2, z^2]` or `Curl of [y,z,x]` — vector calculus
- `Double integral of x+y; x=0..1; y=0..2` — iterated integrals
- `Solve ode y''+y=0` — simple second-order ODE
- `Laplace transform of sin(t)` — transform calculus

The API also accepts an explicit bounded `math_task` JSON for triple integrals, advanced limits and derivatives where natural-language routing is ambiguous. Not all arithmetic, algebra or Calculus I–IV problems can be solved: e.g. geometry word problems, piecewise domains, numerical PDEs, unconstrained integrals, rigorous proofs, many specialized ODEs and vector surface integrals are beyond this release. It **abstains rather than inventing** an answer; the explanatory steps document actual symbolic operations, not a comprehensive textbook-style derivation of every technique.

### Research verification boundaries

Citations in model output are clickable **only if their IDs match the returned primary-source ledger**. This confirms identity, not scientific entailment or truth. The passage ranker requires at least two substantive question-anchor overlaps for most questions; false-negative abstentions are possible. No scientific claims are invented when discovery fails. The full deterministic report remains accessible from **Sources, Methods & Verification** and is exportable as JSON.

## Verification run included in this package

Tests exercise private gateway authentication + CSRF, offline mathematics, unsafe-input rejection, passage selection, cited-ID gating and persisted daily call quota. They do **not** establish actual Render deployment, live provider charging behavior, scholarly source availability, or independent mathematical proof over every domain.
