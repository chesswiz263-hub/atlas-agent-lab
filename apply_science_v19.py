"""Install cumulative ATLAS v1.9 primary-text numerical extraction.

Extract the cumulative ZIP at your existing atlas-agent-lab checkout root,
then run ``python apply_science_v19.py`` from that root. Private ATLAS only.
No git actions, deployment, or public Pages changes are attempted.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V19 = BUNDLE / 'v19'


def _once(body: str, old: str, new: str, label: str) -> str:
    if new in body:
        return body
    if body.count(old) != 1:
        raise RuntimeError(f'Unexpected {label}; refusing v1.9 patch. Review changes manually.')
    return body.replace(old, new, 1)


def ensure_v18() -> None:
    api = ROOT / 'src/atlas/api.py'
    if not api.is_file():
        raise RuntimeError('Run from the original existing ATLAS repository root')
    if 'from atlas.science_quantitative import QuantitativeResearchRequest, run_quantitative_research' in api.read_text(encoding='utf-8'):
        return
    installer = ROOT / 'apply_science_v18.py'
    if not installer.is_file():
        raise RuntimeError('Missing bundled v1.8 cumulative installer')
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v18', installer)
    if spec is None or spec.loader is None:
        raise RuntimeError('Could not load cumulative v1.8 installer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT, module.BUNDLE, module.V18 = ROOT, BUNDLE, BUNDLE / 'v18'
    module.main()


def patch_api(body: str) -> str:
    body = _once(body,
        'from atlas.science_quantitative import QuantitativeResearchRequest, run_quantitative_research\n',
        'from atlas.science_quantitative import QuantitativeResearchRequest, run_quantitative_research\n'
        'from atlas.science_extraction import ExtractionResearchRequest, run_extraction_research\n',
        'scientific extraction import')
    body = _once(body,
        '    @app.get("/api/embeddings/status")',
        '    @app.post("/api/science/extract")\n'
        '    async def science_extraction(request: ExtractionResearchRequest):\n'
        '        """Source-anchored numerical spans and explicitly reviewed arithmetic."""\n'
        '        return await run_extraction_research(request)\n\n'
        '    @app.get("/api/embeddings/status")',
        'scientific extraction API route')
    return body.replace('version="1.8.0"', 'version="1.9.0"').replace('"version": "1.8.0"', '"version": "1.9.0"')


def patch_readme(body: str) -> str:
    section = '''## Version 1.9 — source-anchored scientific data extraction

The private **Scientific Data Extraction** workspace (`/static/extraction.html`)
uses one bounded, no-model primary-text discovery run to scan *verified-identity
source excerpts* for exact decimal number/unit mentions and optional printed ±
uncertainties. Candidates retain DOI, document/excerpt SHA-256, paragraph,
verbatim matched text and character offsets. This is not full-document figure,
table or scientific data validation, and printed errors are not presumed 1σ.
Users can explicitly map two candidates to prediction/measurement roles,
confirm context, and ask the existing v1.8 quantitative engine to compute a
unit-aware discrepancy. Each comparison reruns literature retrieval and fails
closed if either candidate is no longer matched. Statistical residuals require
explicit user confirmation of Gaussian 1σ uncertainties and the error model.
Neither extraction nor model calculations establish scientific truth.
See [v1.9 guide](docs/SCIENTIFIC_RESEARCH_V1_9.md).
All previous research engines and the original ATLAS security model remain.

'''
    return _once(body, '## Version 1.8 — quantitative scientific consistency',
                 section + '## Version 1.8 — quantitative scientific consistency', 'README')


def patch_quant_page(body: str) -> str:
    section = '''<section class="panel"><h2>NEW · Source data extraction v1.9</h2><p>Locate exact numerical mentions within checked primary-text excerpts and review their source context before comparing them quantitatively.</p><p><a href="/static/extraction.html">Open scientific data extraction ↗</a></p></section>
'''
    return _once(body, '<div class="layout"><section class="panel input"><h2>Comparisons</h2>',
                 section + '<div class="layout"><section class="panel input"><h2>Comparisons</h2>',
                 'v1.8 workspace navigation')


def main() -> None:
    # Refuse customized v1.9 targets *before* executing older installers.
    sources = ('src/atlas/science_extraction.py', 'static/extraction.html',
               'static/extraction.js', 'tests/test_science_v19.py',
               'docs/SCIENTIFIC_RESEARCH_V1_9.md')
    for rel in sources:
        desired, existing = V19 / rel, ROOT / rel
        if not desired.is_file():
            raise RuntimeError(f'Missing bundled v1.9 source {rel}')
        if existing.is_file() and existing.read_bytes() != desired.read_bytes():
            raise RuntimeError(f'Conflicting customized file {rel}; refusing overwrite')
    ensure_v18()
    edits = (
        ('src/atlas/api.py', patch_api),
        ('pyproject.toml', lambda s: _once(s, 'version = "1.8.0"', 'version = "1.9.0"', 'version')),
        ('README.md', patch_readme),
        ('static/quantitative.html', patch_quant_page),
    )
    changes: dict[Path, bytes] = {}
    for rel, action in edits:
        target = ROOT / rel
        if not target.is_file():
            raise RuntimeError(f'Missing existing ATLAS file {rel}')
        changes[target] = action(target.read_text(encoding='utf-8')).encode('utf-8')
    for rel in sources:
        changes[ROOT / rel] = (V19 / rel).read_bytes()
    for target, desired in changes.items():
        if target.exists() and target.read_bytes() == desired:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(desired)
        print('Installed:', target.relative_to(ROOT))
    print('ATLAS v1.9 installed locally. Run pytest -q tests and inspect git diff.')
    print('No GitHub push, commit, deployment, or public Pages change was made.')


if __name__ == '__main__':
    main()
