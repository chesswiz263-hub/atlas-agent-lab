# ATLAS 2.4 release notes

This release activates the existing real provider boundary in the hosted research answer path when the operator supplies **server-side** environment variables. It retains the v1.9 evidence engine, v2.2 quota ledger, and v2.3.1 math parser/renderer.

New: stricter source-ID, sentence and quantitative-literal validation; model status without leaking settings; coherent answer above an expandable provenance report; source card links for citations without trusted publication URLs; conservative fallback on insufficient evidence or rejected model output.

Security/limitations: no AI secret included, no model can perform independent browsing, scientific entailment not proven, estimated rather than guaranteed provider-level cost ceiling, single-operator authenticated beta only. Model enablement requires an operator-chosen provider model and persistent SQLite quota path. Rollback via Git commit/redeploy, not by deleting verified math files.

Offline tests in the reconstructed package: 84 passed spanning v2.2, v2.2 math hotfix, v2.3, v2.3.1 parser hotfix, and v2.4. Re-run your full checkout suite before pushing.
