# ATLAS v2.6 Release Notes — Prototype

## Primary delta from v2.5

| Layer | v2.5 | v2.6 prototype |
|---|---|---|
| Dark matter planning | Rotation, Bullet, CMB, **MOND** | Rotation, generic cluster lensing, Bullet, CMB; MOND handled on follow-up |
| Discovery selection | Search result interleaving | Category-diverse, observation-favored paper ranking |
| Text acquisition | Bounded arXiv text | Same security boundary; per-category retrieval fallbacks |
| Evidence output | 6 topically ranked excerpts, uneven | Up to 8 category-balanced excerpts with category coverage/missingness |
| Synthesis | Freeform narrative + citation ID/number validation | One bounded JSON synthesis call + per-claim exact supporting-quote checks |
| Unsupported claims | Reject entire malformed narrative | Drop unsupported claims, explicitly mark missing categories |
| History | Client history mostly unused in retrieval | Uses bounded prior **user questions** to resolve topic follow-ups |
| Cost | v2.4 SQLite pre-call reservation | Same model reservation and opt-in limits |
| Mathematics | v2.5 SymPy worker | Preserved unchanged |
| UI | v2.5 report JSON | v2.6 coverage/claim check summary + expandable evidence JSON |

## Regression scope

23 offline tests passed from `v26_tests` and `v25_tests` in a reconstructed source-package environment. Tests cover original source ranking, category coverage with mock OpenAlex/arXiv transport, source hashes, disallowed citations, unsupported numbers, fabricated assertions, negation inversion, continuity, model calls with/without evidence, math preservation, login/CSRF source invariants, and a repeatable fail-closed installer.

**Outstanding acceptance gates:** live retrieval coverage for all four observational domains; verified provider configuration and actual spent budget; expert judgment that sampled claims are scientifically supported, not merely lexically close. The live probe records these gaps explicitly and must not be represented as an automatic proof of truth.
