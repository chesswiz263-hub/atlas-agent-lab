# Release: ATLAS v2.5 — Scientific Discovery & Evidence Intelligence

## Goal
Move beyond arXiv metadata-only discovery toward bounded, source-located full-text evidence that can support readable model synthesis **without** loosening mathematical verification, provenance or cost controls.

## Key changes
1. Deterministic question-aware subsearches and per-subquery paper diversity.
2. OpenAlex discovery of papers with arXiv repository locations; restricted arXiv HTML/PDF fetching and limited PDF extraction (pypdf).
3. Exact passage excerpts with SHA-256, document URL, arXiv ID and source locator.
4. Strict citation/reference screening and existing LLM budget reservations; model stays off by default.
5. Existing v1.9 science engine preserved as a fallback; metadata remains metadata.
6. No `False` characteristic polynomial in the second-order constant-coefficient ODE teaching flow.

## Known limits
Metadata and fetched text are **not** independent verification of authorship, methods, truth, peer review or correct claim entailment. OpenAlex and arXiv requests can fail; source text may be absent; full-text support is currently arXiv only. Retrieval API queries may incur provider charges or quota consumption. Runtime limits are best-effort application limits, not absolute memory/CPU or vendor-billing guarantees. Live integration not confirmed; tests are offline/mocked.
