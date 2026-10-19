# ATLAS v2.2 release notes

**Conversational research and expanded, checked mathematics.**

- New authenticated `POST /api/atlas/chat` routes math and science queries with a conversational, source-aware answer contract.
- Live science reuses v1.9 discovery/decomposition/provenance, selects relevant primary-text passages and uses an optional, bounded OpenAI Responses adapter (no provider model call by default).
- Citations are checked against actual ledger IDs; unsupported outputs become abstentions rather than fabricated source claims. This is **not** semantic entailment verification.
- New bounded Python AST → isolated SymPy mathematics worker supports arithmetic, algebra, calculus I–III and a subset of advanced differential equations, series, Laplace and vector calculus, with explicit step descriptions and formal checks.
- Persistent SQLite model-call reservations, per-call and per-day estimated-cost caps, request quotas, token/output limits, no retries and no browser API keys.
- Chat-focused responses appear above an expandable **Sources, Methods & Verification** section. Legacy reports and official source links remain available.
- GitHub Pages remains an explicitly offline demo; hosted API remains password protected and single-operator.

**Status:** Packaged and offline regression tested; not pushed to GitHub, deployed to Render, or exercised with a paid model by this release package.
