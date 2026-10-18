# ATLAS v1.2 — Primary-publication evidence preview

**Scope:** additive extension to the private ATLAS scientific workbench. ATLAS's existing agent, retrieval safeguards, provider infrastructure, v1.1 mathematical checks, and offline GitHub Pages demo remain in place.

## Install (supports either v1.0 or v1.1)

1. Extract this package **into the repository root** (the folder containing `pyproject.toml`). Its new `atlas_science_package/` folder is intentionally self-contained. Do not delete existing ATLAS files.
2. Run `python apply_science_v12.py` from the repository root. The installer validates existing anchors, imports the bundled v1.1 source if needed, and applies v1.2 changes. Rerunning is safe. It refuses to overwrite customized v1.1 interface files or conflicting v1.2 code.
3. Run `python -m pip install -e ".[dev,science]"` and `pytest -q`. Verify `node --check static/science.js` if Node is available. Keep your release private until tests/CI succeed.
4. Launch the existing API locally: `uvicorn atlas.api:app --reload --host 127.0.0.1 --port 8000`, sign in to your private ATLAS workbench, then select **Science research**.
5. Commit changes and push after reviewing `git diff`. The installer **never** pushes to GitHub.

## What was added

- Live OpenAlex paper discovery and Crossref DOI/title/year metadata crosschecks from v1.1 are preserved.
- A second, independent DOI lookup in **Europe PMC** and full-text XML retrieval is now attempted for **up to 3** Crossref-crosschecked documents. The bounded public API supports the **open-access subset** of its corpus (primarily biomedical/life-sciences publications). Other scientific fields often have no coverage yet.
- A checked XML is associated with its own DOI, PMCID, retrieval timestamp, document SHA-256, licence tag where present, section, and paragraph location. Missing/mismatched text is marked unavailable, never fabricated.
- User-supplied quoted text can be literally checked against normalized full-text paragraphs by DOI. Output is `EXACT_TEXT_MATCH`, `EXACT_QUOTE_NOT_FOUND`, `SOURCE_NOT_VERIFIED`, or `DOI_NOT_IN_DISCOVERY` — not an entailment judgment.
- Relevance-selected repository snippets use IDs such as `[P1.1]`. Only a few short excerpts are displayed; primary XML is neither cached nor returned whole.
- With a configured live model, ATLAS may synthesize selected repository paragraphs and must use existing passage IDs. Invalid paper IDs are rejected. **Source-ID existence checking is not claim entailment checking.** It is explicitly labelled `PRIMARY_PASSAGE_GROUNDED_NOT_CLAIM_VERIFIED`.
- A detected Crossref editorial update causes `UPDATE_REVIEW_REQUIRED` and excludes the article from automatic passage synthesis pending manual review. Crossref signals are incomplete and are **not** a comprehensive retraction detector.
- If no accessible primary source is retrieved, ATLAS retains the clearly labelled v1.1 discovery/abstract-only fallback.

## JSON API

`POST /api/science/ask` (requires existing ATLAS authentication/CSRF controls):

```json
{
  "question": "What do galaxy rotation studies report about dark matter?",
  "hypotheses": ["dark matter", "modified gravity"],
  "provider": "demo",
  "max_papers": 5,
  "include_primary": true,
  "max_primary_papers": 3,
  "quote_candidates": [
    {"doi": "10.1234/example", "quote": "An exact sentence copied from the paper."}
  ],
  "math_tasks": [{"expression": "(x+1)**2 = x**2+2*x+1", "operation": "verify_equation"}]
}
```

Replace illustrative DOI and quotation with real source values. `GET /api/science/papers` continues to provide discovery and DOI metadata checks only.

## Interpretation and boundaries

1. A DOI/title/year match authenticates **metadata**, not publisher full text, correctness, or current editorial standing.
2. A Europe PMC article-id match authenticates a **repository-hosted XML record**, not whether it is the final version of record or has been retracted elsewhere.
3. A literal quote match proves only that the quoted words occur within a checked body paragraph. A quotation can be out of context or scientifically incorrect.
4. Passage IDs in model output are checked against actually retrieved passages; model-generated conclusions, predictions, and interpretations are **not independently verified**.
5. A disabled full-text check, inaccessible/copyright-restricted publication, non-Crossref DOI registry, or absent XML does **not** mean the cited science is false.
6. Article texts may have varying copyright and reuse rights. The workbench exposes only short passages and does not redistribute full texts. Respect each deposited license and API conditions.
7. No general source ranking, NLI claim-entailment, physics-unit validation, comprehensive retraction screening, arXiv full-text extraction, general scientific web browsing, or independent peer-review checking is included yet. Those are later iterations.

## Security and operational limits

- Fixed HTTPS endpoints only. Never follow external article URLs, XML-provided resource locations, redirects, or DOI resolve links.
- JSON/title/DOI validated; PMCID constrained; body XML parsed with `defusedxml`; streamed response capped at 4 MB; processing capped at 350 paragraphs; up to three documents per request; no XML persisted.
- Prompt and publication paragraphs are untrusted input, not executable model instructions. The existing operator authentication, provider credentials, and math safety controls remain in place.
- Tests use mocked OpenAlex, Crossref, and Europe PMC transports, not live calls. Run a manual integration test using an actual open-access paper before treating this as production-ready. API availability, licence metadata, XML formatting, and editorial update fields can change.

### Scientific source references

- [Europe PMC REST API](https://europepmc.org/RestfulWebService) — `/search`, `/{id}/fullTextXML` (open-access subset).
- [Europe PMC developers](https://europepmc.org/developers) — programmatic access and licensing.
- [Crossref Crossmark](https://www.crossref.org/services/crossmark/) — publisher-registered updates, corrections, and retractions where deposited.
- [OpenAlex API documentation](https://help.openalex.org/api/) — bibliographic discovery.
