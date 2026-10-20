# ATLAS v2.3 release notes

## What changed

- Presentation of symbolic mathematics is now native MathML with exact LaTeX serialized alongside each SymPy expression, including superscripts and fractional notation.
- Clear result / why this method / numbered steps / verification / optional raw symbolic sections replace the debug-report-first mathematical answer.
- Integration-by-parts examples explain polynomial degree reduction and the reason multiple applications are needed; redundant final check steps are collapsed in the teaching view without modifying the raw solver output.
- An optional model-assisted tutoring sentence may be generated under the existing budget gate; it cannot replace formulas or verification and is off by default.
- Evidence-first scientific synthesis prompt emphasizes conversational clarity, source-limited claims and uncertainty; validated source IDs and per-sentence citation checks are maintained. The old technical report remains accessible in a details panel.
- No external script, JS math engine, server-side arbitrary code execution, API key in browser, CORS changes or GitHub Pages changes were introduced.
- Conservative repeat-safe installer upgrades known v2.2 gateway and tests with a `.git` backup.

## Verification

Validated in a reconstructed prior-version environment with v2.2 and math-hotfix modules, hosted gateway authentication/CSRF fixture and v2.3 tests: **52 passed**. JavaScript syntax checked with Node. The user's actual full repository baseline and hosted Render behavior must still be checked after installation.
