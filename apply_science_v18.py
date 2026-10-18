"""Install cumulative ATLAS v1.8 quantitative analysis on an existing checkout.

Run from the original repository root after extracting the v1.8 ZIP contents.
Updates private app files only. No GitHub push, deployment or Pages change.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V18 = BUNDLE / 'v18'


def _once(body: str, old: str, new: str, label: str) -> str:
    if new in body:
        return body
    if body.count(old) != 1:
        raise RuntimeError(f'Unexpected {label}: refusing v1.8 patch; manual review required')
    return body.replace(old, new, 1)


def ensure_v17() -> None:
    api = ROOT / 'src/atlas/api.py'
    if not api.is_file():
        raise RuntimeError('Run from the existing ATLAS repository root')
    if 'from atlas.science_claims import ClaimAssessmentRequest, run_claim_assessment' in api.read_text(encoding='utf-8'):
        return
    installer = ROOT / 'apply_science_v17.py'
    if not installer.is_file():
        raise RuntimeError('Missing cumulative v1.7 installer')
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v17', installer)
    if spec is None or spec.loader is None:
        raise RuntimeError('Could not load v1.7 installer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT, module.BUNDLE, module.V17 = ROOT, BUNDLE, BUNDLE / 'v17'
    module.main()


def patch_api(body: str) -> str:
    body = _once(body,
        'from atlas.science_claims import ClaimAssessmentRequest, run_claim_assessment\n',
        'from atlas.science_claims import ClaimAssessmentRequest, run_claim_assessment\n'
        'from atlas.science_quantitative import QuantitativeResearchRequest, run_quantitative_research\n',
        'quantitative import')
    body = _once(body,
        '    @app.get("/api/embeddings/status")',
        '    @app.post("/api/science/quantitative")\n'
        '    async def science_quantitative(request: QuantitativeResearchRequest):\n'
        '        """Compare user-entered quantities and optional verified-identity excerpts."""\n'
        '        return await run_quantitative_research(request)\n\n'
        '    @app.get("/api/embeddings/status")',
        'quantitative route')
    return body.replace('version="1.7.0"', 'version="1.8.0"').replace('"version": "1.7.0"', '"version": "1.8.0"')


def patch_readme(body: str) -> str:
    section = '''## Version 1.8 — quantitative scientific consistency

The private **Quantitative Consistency** workspace (`/static/quantitative.html`)
compares explicit user-entered model predictions and measured quantities. Physical
unit conversion is performed only for a documented closed set of compatible units;
observable and experimental-condition labels must match exactly after basic text
normalization. An uncertainty-standardized residual is computed only if users
explicitly provide both Gaussian 1σ uncertainties and their covariance/independence
assumption. No p-values, theory rankings, significance verdicts or scientific truth
claims are inferred. Optionally, one bounded v1.6 primary-text search can return
source passages whose exact quoted wording may be checked against user-selected
citation IDs; this does **not** validate the transcription of numerical values.
See [v1.8 guide](docs/SCIENTIFIC_RESEARCH_V1_8.md).
All earlier private research workflows, original agent safeguards and offline
public GitHub Pages demonstration remain unchanged.

'''
    return _once(body, '## Version 1.7 — claim-level scientific evidence assessment',
                 section + '## Version 1.7 — claim-level scientific evidence assessment', 'README')


def patch_claim_page(body: str) -> str:
    section = '''<section class="panel"><h2>NEW · Quantitative consistency v1.8</h2><p>Compare predictions with numerical observations, convert supported physical units, and audit explicit uncertainty assumptions.</p><p><a href="/static/quantitative.html">Open quantitative consistency ↗</a></p></section>
'''
    return _once(body, '<div class="layout"><section class="panel input"><h2>Investigation</h2>',
                 section + '<div class="layout"><section class="panel input"><h2>Investigation</h2>',
                 'v1.7 workspace navigation')


def main() -> None:
    # Check v1.8 custom-file conflicts *before* running any older installer.
    copy_paths = (
        'src/atlas/science_quantitative.py', 'static/quantitative.html',
        'static/quantitative.js', 'tests/test_science_v18.py',
        'docs/SCIENTIFIC_RESEARCH_V1_8.md',
    )
    for rel in copy_paths:
        path = ROOT / rel
        desired = V18 / rel
        if not desired.is_file():
            raise RuntimeError(f'Missing bundled v1.8 source: {rel}')
        if path.is_file() and path.read_bytes() != desired.read_bytes():
            raise RuntimeError(f'Conflicting customized file {rel}; refusing to overwrite')
    ensure_v17()
    edits = (
        ('src/atlas/api.py', patch_api),
        ('pyproject.toml', lambda s: _once(s, 'version = "1.7.0"', 'version = "1.8.0"', 'version')),
        ('README.md', patch_readme),
        ('static/claims.html', patch_claim_page),
    )
    changes: dict[Path, bytes] = {}
    for rel, action in edits:
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f'Missing required existing ATLAS file: {rel}')
        changes[path] = action(path.read_text(encoding='utf-8')).encode('utf-8')
    for rel in copy_paths:
        changes[ROOT / rel] = (V18 / rel).read_bytes()
    # Preflight all v1.8 changes before writing them.
    for path, content in changes.items():
        if path.exists() and path.read_bytes() == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.8 installed locally. Run pytest and review git diff.')
    print('No commit, GitHub push, deployment, or public Pages modification performed.')


if __name__ == '__main__':
    main()
