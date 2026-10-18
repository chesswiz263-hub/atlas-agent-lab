# ATLAS v1.1 — Scientific literature and symbolic reasoning (first implementation)

This is an **additive** upgrade for the private FastAPI app. It does not change the GitHub Pages offline demo, remove any local-index or agent functionality, or turn crosschecked metadata into claims of scientific truth.

## Install

1. Unzip this package into the **root of your existing** `chesswiz263-hub/atlas-agent-lab` checkout, preserving the folder paths and allowing **new files** to be added. It does **not** contain replacements for your v1.0 files.
2. From the repository root: `python apply_science_upgrade.py`. The script validates expected v1.0 anchors and makes small edits to `src/atlas/api.py`, `static/index.html`, and `pyproject.toml`. It is idempotent. If the v1.0 source has changed, it fails before changing the existing files.
3. Install: `python -m pip install -e '.[dev,science]'` (PowerShell: `python -m pip install -e ".[dev,science]"`).
4. Test: `pytest -q` and, if installed, `node --check static/science.js`. Never publish a release before CI passes.
5. Start: `uvicorn atlas.api:app --reload --host 127.0.0.1 --port 8000` and open `http://127.0.0.1:8000/static/science.html` or choose **Science research** from the app sidebar.

For GitHub-only editing, add the five new code/static files and test/docs files, then run the installer in Codespaces; `apply_science_upgrade.py` changes your tracked old files locally, which must be committed alongside the new ones.

## API

`POST /api/science/ask` accepts a bounded JSON body:

```json
{
  "question": "What does research report about dark matter and modified gravity?",
  "hypotheses": ["dark matter", "modified Newtonian dynamics"],
  "math_tasks": [
    {"expression": "(x + 1)**2 = x**2 + 2*x + 1", "operation": "verify_equation"},
    {"expression": "x**3 + 2*x", "operation": "differentiate", "variable": "x"}
  ],
  "provider": "demo",
  "max_papers": 5
}
```

`GET /api/science/papers?q=dark%20matter&limit=5` returns research discovery and Crossref identity-check results. Both routes retain existing ATLAS authentication and CSRF protection.

Set `OPENALEX_API_KEY` server-side if necessary for API usage limits. Optionally set `ATLAS_RESEARCH_EMAIL` to identify your OpenAlex/Crossref requests. Never put secret keys into the public website or commit `.env`.

## What works now

- Live **OpenAlex** work lookup, titles, author names, venue, DOI, year, reconstructable indexed abstract. Fixed external hosts and bounded requests; no user-directed URL fetching.
- **Crossref** second-source DOI, title and date agreement checks for Crossref-registered publications. Status is `CROSSREF_METADATA_MATCH` (bibliographic identity), **not** verified content. Other DOI agencies may not be supported.
- Plain-language evidence discovery summary when `provider=demo` (no generative reasoning). With operator-configured server-side OpenAI/Anthropic/Gemini keys, optionally run an abstract-grounded model synthesis with numbered source references; model-generated conclusions are explicitly **not** independently verified.
- Structured hypothesis **mention comparison** with `NOT_EVALUATED` status. Keyword mention is not supporting or contradicting evidence.
- Narrow SymPy arithmetic, algebra simplification, differentiation, and formal equivalence checks via safe AST construction; **never** call `eval` or `parse_expr` on untrusted expressions. No unit analysis or physics-model validation yet.
- JSON dossier export in the private scientific UI, preserving the existing workbench and static public demo.

## Limitations and next scientific milestones

1. Primary-text acquisition from licensed open-access publisher or preprint endpoints; retain source URLs, version, dates, rights, per-excerpt hashes, and exact source spans.
2. Independent quoted-claim verification and retraction-aware publication tracking (Crossref metadata alone is **not** a retraction oracle).
3. Scientific claim graph: observations, assumptions, predictions, contradictions, uncertainties, and attributable evidence spans.
4. Evidence-for/evidence-against matrix for genuinely competing theories; never infer scientific merit from abstract keyword counts.
5. Dimension/unit safety, equations with assumptions, reproducible computational notebooks, math resource limits and physics expert review.
6. Live adversarial prompt-injection and scientific QA evaluations with real held-out papers.

## Security notes

Live bibliographic queries disclose the question to external providers and incur potential rate-limit or access costs. Configured synthesis models receive selected indexed abstracts and the question. `demo` stays deterministic. ATLAS remains a **single-operator research workbench**, not a public multi-tenant scientific search service. Keep it behind your private hosted auth or local port. The existing v1.0 tools' step budgets and audits remain intact but **do not automatically instrument this new synchronous endpoint**; durable scientific jobs and trace persistence are a subsequent integration milestone.
