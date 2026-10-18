# ATLAS v1.8.0 — Quantitative Consistency and Uncertainty Audit

Cumulative private-backend upgrade for existing ATLAS v1.0–v1.7 checkouts.

New: `src/atlas/science_quantitative.py`, `POST /api/science/quantitative`, private `static/quantitative.html`, `static/quantitative.js`, network-free tests and detailed guide.

- Strict user-identified observation/prediction descriptors and conditions
- Finite Decimal arithmetic, closed unit conversion, dimension matching
- Explicit Gaussian one-standard-deviation uncertainties and user-specified independence/correlation
- Standardized residual only where its inputs are justified *as supplied assumptions*
- Abstention for descriptor mismatch, dimensional mismatch, and zero combined uncertainty
- Optional bounded scientific literature excerpts, exact-quote crosschecks and provenance fingerprints
- No AI model, no automatic number extraction from text, no theory truth/ranking/statistical-significance declarations

Public offline demo, agent runtime, and all v1.1–v1.7 capabilities remain unchanged. Nothing is committed or deployed. Full original-repository integration tests and live scholarly services require verification in the user's checkout.
