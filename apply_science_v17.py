"""Cumulative ATLAS v1.0–v1.6 -> v1.7 claim-assessment installer.

Run inside an existing ATLAS checkout after extracting the entire v1.7 ZIP.
No GitHub commits, pushes, deployments, or public Pages modifications occur.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V17 = BUNDLE / 'v17'


def _once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f'Unexpected {label}: manual merge required; no v1.7 changes written')
    return text.replace(old, new, 1)


def ensure_v16() -> None:
    api = ROOT / 'src/atlas/api.py'
    if not api.is_file():
        raise RuntimeError('Run from an existing ATLAS repository root')
    if 'from atlas.science_decomposition import DecomposedResearchRequest, run_decomposed_research' in api.read_text(encoding='utf-8'):
        return
    installer = ROOT / 'apply_science_v16.py'
    if not installer.is_file():
        raise RuntimeError('Missing bundled v1.6 installer')
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v16', installer)
    if spec is None or spec.loader is None:
        raise RuntimeError('Could not load v1.6 installer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Earlier installers resolve everything relative to their own ROOT.
    module.ROOT, module.BUNDLE, module.V16 = ROOT, BUNDLE, BUNDLE / 'v16'
    module.main()


def patch_api(text: str) -> str:
    text = _once(text,
        'from atlas.science_decomposition import DecomposedResearchRequest, run_decomposed_research\n',
        'from atlas.science_decomposition import DecomposedResearchRequest, run_decomposed_research\n'
        'from atlas.science_claims import ClaimAssessmentRequest, run_claim_assessment\n',
        'claim API import')
    text = _once(text,
        '    @app.get("/api/embeddings/status")',
        '    @app.post("/api/science/claims")\n'
        '    async def science_claim_assessment(request: ClaimAssessmentRequest):\n'
        '        """Assess explicit claims against verified-identity excerpts, without truth verdicts."""\n'
        '        return await run_claim_assessment(request)\n\n'
        '    @app.get("/api/embeddings/status")',
        'claim API endpoint')
    return text.replace('version="1.6.0"', 'version="1.7.0"').replace('"version": "1.6.0"', '"version": "1.7.0"')


def patch_readme(text: str) -> str:
    block = '''## Version 1.7 — claim-level scientific evidence assessment

The authenticated **Claim Assessment** workspace (`/static/claims.html`) extends
v1.6 research decomposition with explicitly user-entered claims, a structured
claim-to-source matrix, conservative textual-role cues, and optionally one
provider call proposing source/claim relationships. Exact quotes, citation IDs,
and excerpt hashes are validated before any proposed relationship is displayed.
Crucially, passages, topical overlap, and model proposals NEVER automatically
establish scientific entailment, experimental validity, support or refutation.
All suggested relationships require human scientific review. The original agent,
all earlier research workspaces, and public offline GitHub Pages demo are unchanged.
See [v1.7 guide](docs/SCIENTIFIC_RESEARCH_V1_7.md).

'''
    return _once(text, '## Version 1.6 — bounded scientific research decomposition',
                 block + '## Version 1.6 — bounded scientific research decomposition', 'README')


def patch_decompose_page(text: str) -> str:
    block = '''<section class="panel"><h2>NEW · Claim assessment v1.7</h2><p>Track user-entered scientific claims against verified-identity text, review role cues, and validate exact quotation locators.</p><p><a href="/static/claims.html">Open claim assessment ↗</a></p></section>
'''
    return _once(text, '<div class="layout"><section class="panel input"><h2>Research configuration</h2>',
                 block + '<div class="layout"><section class="panel input"><h2>Research configuration</h2>',
                 'v1.6 navigation')


def main() -> None:
    ensure_v16()
    edits = (
        ('src/atlas/api.py', patch_api),
        ('pyproject.toml', lambda text: _once(text, 'version = "1.6.0"', 'version = "1.7.0"', 'version')),
        ('README.md', patch_readme),
        ('static/decompose.html', patch_decompose_page),
    )
    updates: dict[Path, bytes] = {}
    for rel, fn in edits:
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f'Missing required existing ATLAS file: {rel}')
        updates[path] = fn(path.read_text(encoding='utf-8')).encode('utf-8')
    for rel in (
        'src/atlas/science_claims.py', 'static/claims.html',
        'static/claims.js', 'tests/test_science_v17.py',
        'docs/SCIENTIFIC_RESEARCH_V1_7.md',
    ):
        path = ROOT / rel
        target = (V17 / rel).read_bytes()
        if path.is_file() and path.read_bytes() != target:
            raise RuntimeError(f'Conflicting {rel}: refusing to overwrite customized file')
        updates[path] = target
    # v1.7 changes are preflighted before any of its files are modified.
    for path, data in updates.items():
        if not path.exists() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.7 installed locally. Run pytest, check JS, and review git diff.')
    print('No GitHub push, deployment, or public GitHub Pages modifications occurred.')


if __name__ == '__main__':
    main()
