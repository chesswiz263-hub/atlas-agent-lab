# ATLAS v2.4.1 — Math Route Repair & Honest Research Diagnostics

This is a **targeted compatibility patch**, not a new paper-discovery engine and not a general-purpose promise for all mathematics questions.

## Fixes

- Normalizes the user-reported long integration prompt to a restricted math-only request. Converts elementary `e^x` into `exp(x)`; SymPy still parses and verifies it in the original isolated v2.3 math worker.
- Adds isolated, time-limited, **checked** routines for: (a) polynomial stationary points in exactly `x,y`, with first and second derivatives and Hessian classification; and (b) second-order linear constant-coefficient ODE initial-value problems at `x=0` with numeric `y(0)` and `y'(0)`. All input is processed by the original restricted AST parser or by fixed ODE notation; no arbitrary Python evaluation or untrusted arbitrary SymPy parsing.
- Adds `research_diagnostics` to hosted research JSON: literature status, arXiv metadata status, whether independently located primary text exists, whether lexical passage ranking rejected text, and whether model synthesis was attempted.
- **Does not claim to solve astrophysics source discovery.** v1.9 citation indexing only accepts Crossref-matched metadata with eligible repository full text. arXiv metadata alone is not used as full-text proof. This needs a separate future source-retrieval upgrade (e.g. astronomy-appropriate open access full text or validated primary passages with traceable locators).
- Reuses v2.4's model budget, provider validation, secure login, CSRF, web interface and protected science engine. No new paid model calls.

## Installation on Windows

1. Commit/back up pending changes and extract this entire ZIP into the `atlas-agent-lab` repository root, beside `pyproject.toml`.
2. Make sure **v2.4 is already installed**. Run `python install_atlas_v241.py`. It only replaces `atlas_hosted_beta.py` when the existing gateway matches the verified v2.4 release or is already v2.4.1. It backs up the old gateway under `.git/atlas-v241-backups/`.
3. Run the *whole existing repository suite*:

```cmd
python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests
```

4. Confirm a green result before committing. In GitHub Desktop exclude `.git` backups, `.env`, keys, generated databases and caches. Commit summary: `Hotfix ATLAS v2.4.1 — Math Routing and Research Diagnostics`.
5. Push, then let Render deploy. **Retain** existing v1.9 `apply_science_v19.py` build step, SymPy and OpenAI dependencies, and Uvicorn start command. Continue using the existing authenticated `/static/atlas-chat-v24.html` URL; no frontend asset change is needed.

## Verification prompts

- `Evaluate the indefinite integral of x^3 * e^x. Explain why integration by parts is appropriate, show every application of the method, explain why the polynomial degree decreases, and verify the antiderivative by differentiation.` Expected: `exp(x)*(x**3 - 3*x**2 + 6*x - 6) + C`, with differentiation checking.
- `Find and classify all stationary points of f(x,y)=x^3-3*x+y^2-4*y. Explain the gradient, solve for stationary points, apply the Hessian test, and verify the classification.` Expected: `(-1, 2)` saddle, `(1, 2)` local minimum.
- `Solve the differential equation y'' + 4*y = 0 subject to y(0)=2 and y'(0)=0. Explain the characteristic equation, how the initial conditions determine the constants, and verify the solution by substitution.` Expected: `y(x)=2cos(2x)`.
- Ask dark matter research again and open `Sources, Methods & Verification` raw report. Inspect `research_diagnostics`. `NO_SOURCE_TEXT_LOCATED` means no eligible full-text excerpt; `SOURCE_TEXT_NOT_TOPICALLY_SELECTED` means passages were present but selected out. **Neither means dark matter lacks evidence.**

## Scope / limitations

The mathematical extension solves only those explicitly recognized forms. The Hessian classification reports inconclusive results when the standard second-derivative test is indeterminate. The ODE extension checks the differential equation and initial conditions by substitution. The original math solver and original model planner handle other supported questions. Full conversational scientific answers still depend on real crosschecked primary passages and an explicitly enabled, budgeted server-side model. Citation locator matching alone does not establish factual entailment.

Never paste API keys into GitHub or chat. Never enable a paid model before configuring durable provider and application spending caps. The present patch does not change any model settings.

## Validation of this package

The bundled v2.4/v2.4.1 tests passed 29/29 in a reconstructed environment. Older version-specific tests passed 69/69 separately. The user's full repository-level regression tests were **not** run in this environment; run the command above locally before deploying.
