# ATLAS v1.3 — Structured theory comparison and scientific evidence audit

## Purpose

Adds structured, testable predictions to ATLAS v1.2's science endpoint. It **does not** replace the original local-first agent runtime, model providers, tool allowlists, evidence policies, mathematical checker, research dossiers, or public offline demo.

## Endpoint

`POST /api/science/ask` remains the endpoint. New optional fields:

```json
{
  "question": "What observations help distinguish two explanations of galactic dynamics?",
  "provider": "demo",
  "include_primary": true,
  "max_papers": 5,
  "max_primary_papers": 3,
  "theories": [
    {
      "name": "Model A",
      "description": "First user-specified model (replace with a real hypothesis)",
      "predictions": [
        {"observable": "galaxy rotation curves", "condition": "spiral galaxy outskirts", "expected_direction": "increase"}
      ]
    },
    {
      "name": "Model B",
      "predictions": [
        {"observable": "galaxy rotation curves", "condition": "spiral galaxy outskirts", "expected_direction": "decrease"}
      ]
    }
  ],
  "interpret_theories": false
}
```

**Important:** the toy directions in the example above are not factual assertions about dark matter or MOND. The caller must specify scientifically defensible assumptions and conditions. A potential conflict means the two *entered predictions* oppose each other under identical written conditions; it does not establish which physical model is right.

The `theories` input accepts at most four theories, at most five predictions each and at most twelve total predictions. Prediction fields are `observable` (required), `condition` (recommended), `expected_direction` (default `unspecified`) and `rationale` (optional). Directions: `increase`, `decrease`, `present`, `absent`, `zero`, `nonzero`, `positive`, `negative`, `unchanged`, `unspecified`.

The new `theory_comparison_v13` output contains:

- `theories` with every user-specified observable, condition, outcome, topical evidence IDs, and an explicit `NOT_ASSESSED` status.
- `evidence` entries with a DOI, article reference, short exact repository excerpt, repository XML SHA-256, paragraph SHA-256, section and paragraph locator.
- `prediction_conflicts` containing only explicit, standardized opposite outcomes on an identical normalized observable **and** a stated identical normalized condition.
- `model_assessments` with optional provider-proposed relations and checked literal quotations. These remain `MODEL_PROPOSAL_NOT_INDEPENDENTLY_ENTAILED`.
- `model_status` flags for abstention, rejected citations, unavailable providers or quote-checked proposals.

## Data path and guarantees

1. v1.1: OpenAlex discovers candidate works and Crossref checks DOI/title/year metadata; this is bibliographic verification, not content validation.
2. v1.2: DOI-matched, OA Europe PMC article XML is fetched with size and parsing limits; exact passages, document fingerprints and section/paragraph locators are tracked. A Crossref update notice blocks XML verification pending review; this is not a comprehensive retraction screen.
3. v1.3: user-supplied prediction terms are matched **lexically** against validated XML paragraphs. A match requires at least two distinct, nontrivial terms; up to two paragraphs per prediction are retained, and globally up to twenty evidence paragraphs. They are deduplicated across predictions.
4. Optional `interpret_theories=true` additionally requires a configured non-demo provider; it sends bounded text to that provider. Response must be strictly valid JSON, cite only evidence attached to that specific prediction, and quote exact contiguous words from its corresponding paragraph. Any invalid ID, nonliteral quotation, wrong association, duplicate or schema error rejects the *whole* interpretation.
5. Even an accepted interpretation is **not** independently checked for semantic entailment, scientific validity, representativeness, experimental design, or consistency with the wider literature.

## Explicit limitations

- Europe PMC primarily serves biomedical/life-science literature; the current full-text coverage is often poor for mathematical physics and engineering. A robust arXiv/APS/publisher-permissions adapter is a **future feature**, not built in this release.
- Keyword overlap does not tell whether the text favors, opposes, qualifies, or merely mentions a prediction. No auto-ranking or evidence strength score is produced.
- User-entered predictions and conditions are not externally validated for scientific correctness or dimensional consistency.
- Neither the absence of a publication update flag nor a matched XML passage proves a paper is unretracted, replicated, or correct. Validate retractions and corrections separately.
- The optional LLM can hallucinate an interpretation despite citing and quoting real text; its status expressly warns of this.
- Results are a bounded search-time snapshot; citations and source versions can later change. The document SHA-256 is supplied for reproducibility.
- Any absence of primary XML must yield no *primary* evidence. ATLAS preserves earlier abstract-only answer limitations and abstention.
- The original agent's cost limits and explicit tool restrictions remain; this module cannot safely fetch arbitrary user-submitted URLs.

## Local setup

1. Extract the cumulative upgrade ZIP **over a working local checkout**, retaining folders.
2. Run `python apply_science_v13.py` in the repository root.
3. Run `python -m pip install -e ".[dev,science]"`.
4. Run `pytest -q` and `node --check static/science.js`.
5. Start the existing *private* ATLAS backend using its normal documented method, sign in, and open `/static/science.html`.

Only local files are changed by the installer. Review `git diff` and commit/push manually. The installer checks source file anchors and refuses to overwrite customized UI and new module files. It does not back up a local checkout; using a clean branch or backup before installing is recommended.
