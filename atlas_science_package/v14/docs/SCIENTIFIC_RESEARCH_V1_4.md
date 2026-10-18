# ATLAS v1.4 — Physics laboratory and mathematical checks

Adds a **private** physics endpoint and a dashboard linked from the existing science workspace; preserves v1.3 evidence comparisons, v1.2 full-text checks, v1.1 discovery, and the original offline GitHub Pages demonstration.

## Endpoint

`POST /api/science/physics` (same backend/session/operator-token protections as other private API routes). Example:

```json
{
  "question": "galaxy rotation curves dark matter",
  "search_arxiv": true,
  "arxiv_limit": 5,
  "dimensional_tasks": [{"expression": "F = mass*acc", "variable_units": {"F": "N", "mass": "kg", "acc": "m/s**2"}}],
  "symbolic_tasks": [{"operation": "integrate_polynomial", "variable": "x", "expression": "3*x**2 + 2*x + 1"}],
  "numerical_tasks": [{"kind": "damped_oscillator_rk4", "inputs": {"mass_kg": 1, "spring_N_m": 4, "damping_N_s_m": 0.3, "x0_m": 1, "v0_m_s": 0, "dt_s": 0.05, "steps": 100}}]
}
```

The endpoint returns `arxiv_discovery`, `dimensional_checks`, `symbolic_checks`, and `numerical_runs`. Each status and scope label must be carried into any downstream report. It does **not** generate a general research answer from arXiv abstracts. v1.3 remains the source-limited synthesis workflow.

## arXiv rules

- Queries are generated from bounded alphanumeric search terms; users cannot inject arbitrary arXiv API query expressions.
- Use official Atom metadata. Entries get canonical URLs only after validating arXiv identifiers; all fields are textual untrusted data.
- At most six entries returned; at most 1.5 MB of feed stored; defused XML parser; no redirects; HTTP timeout; one connection per own client; best-effort 3-second spacing within each backend process. A deployment with multiple workers needs a **shared** rate limiter/cache to respect arXiv rate policies.
- arXiv metadata and abstracts are not independent full-text/peer-review/DOI/claim validation. We do not fetch arbitrary paper PDFs or give metadata the verification label of v1.2 Europe PMC text.
- arXiv searches can be unavailable due to API rate limits, outages or query breadth. ATLAS returns an unavailable/no-results status, not invented papers.

## Mathematics and numerical methods

- Dimensional analysis uses **SI base dimensions only**, not numerical conversion factors (e.g. cm and km both have `L`). Support: `m`, `cm`, `km`, `mm`, `kg`, `g`, `s`, `ms`, `min`, `h`, `A`, `K`, `mol`, `cd`, `N`, `J`, `W`, `Pa`, `Hz`, `C`, `V`, `Ohm`, `rad`, `one`. Users must specify dimensions for each variable. `sin`, `cos`, `tan`, `exp`, `log` require dimensionless arguments. `sqrt` divides exponents by two. Equation sides are compared for dimensional consistency, not physical truth.
- v1.4 polynomial integration and root solving reuse v1.1's strict AST parser. Integration is differentiated for an exact check; roots are substituted back into the polynomial. No arbitrary SymPy strings or `eval`; exact polynomial coefficients and degrees are bounded. Existing simplify/differentiate/identity checks still operate as before.
- Numerical modules: kinetic energy `0.5*m*v**2` (classical nonrelativistic) and linear viscously damped harmonic oscillator integrated with fixed-step RK4. Oscillator steps ≤400, SI units required, conservative time-step resolution bound; output includes sampled trajectory, energies, input parameters, algorithm version and SHA-256 fingerprint. This is a deterministic calculation, **not** an independently verified simulation or a rigorous error bound. Numerical floating-point outputs are platform-dependent beyond the same environment/version.
- Input bounds and result caps apply. Do not use the results to make safety-critical engineering decisions without domain validation, convergence studies, uncertainty and appropriate independent review.

## Installation

1. Back up/branch your checkout; unpack the cumulative archive into the repository root.
2. `python apply_science_v14.py`
3. `python -m pip install -e ".[dev,science]"`
4. `pytest -q` and `node --check static/physics.js`.
5. Run your private ATLAS backend and open `/static/physics.html` (linked from `/static/science.html`).

No GitHub push is performed by this package. Every module includes explicit verification scope; the original agent architecture and public Pages demo are preserved.
