"""Cumulative ATLAS v1.0–v1.5 -> v1.6 controlled research decomposition installer.

Run from an existing ATLAS checkout after copying ALL ZIP contents into its root.
No commits, pushes, production deployment, or public Pages changes are made.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V16 = BUNDLE / 'v16'


def _once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f'Unexpected {label}: manual merge required; no v1.6 changes written')
    return text.replace(old, new, 1)


def ensure_v15() -> None:
    api = ROOT / 'src/atlas/api.py'
    if not api.exists():
        raise RuntimeError('Run from the root of an existing ATLAS repository')
    if 'from atlas.science_workflow import ResearchWorkflowRequest, run_scientific_workflow' in api.read_text(encoding='utf-8'):
        return
    installer = ROOT / 'apply_science_v15.py'
    if not installer.exists():
        raise RuntimeError('Missing bundled v1.5 cumulative installer')
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v15', installer)
    if spec is None or spec.loader is None:
        raise RuntimeError('Could not load bundled v1.5 installer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.BUNDLE = BUNDLE
    module.V15 = BUNDLE / 'v15'
    module.V14 = BUNDLE / 'v14'
    module.main()


def patch_api(text: str) -> str:
    text = _once(text,
        'from atlas.science_workflow import ResearchWorkflowRequest, run_scientific_workflow\n',
        'from atlas.science_workflow import ResearchWorkflowRequest, run_scientific_workflow\n'
        'from atlas.science_decomposition import DecomposedResearchRequest, run_decomposed_research\n',
        'API import')
    text = _once(text,
        '    @app.get("/api/embeddings/status")',
        '    @app.post("/api/science/decompose")\n'
        '    async def science_decompose(request: DecomposedResearchRequest):\n'
        '        """Execute gap-aware, bounded follow-up research and verified-text ledger."""\n'
        '        return await run_decomposed_research(request)\n\n'
        '    @app.get("/api/embeddings/status")',
        'API route')
    return text.replace('version="1.5.0"', 'version="1.6.0"').replace('"version": "1.5.0"', '"version": "1.6.0"')


def patch_readme(text: str) -> str:
    block = '''## Version 1.6 — bounded scientific research decomposition

The private **Research Decomposition** workspace (`/static/decompose.html`) extends
v1.5 with explicit user subquestions or a narrow comparison-question parser,
measures topic-level passage coverage, and performs at most two targeted follow-up
searches when text evidence is missing and the reserved research budget allows it.
Each retrieved and Crossref/primary-text-crosschecked passage gets an unambiguous
batch-qualified citation ID; exact-excerpt fingerprints and origin are retained.
A single optional model interpretation remains unverified even when references exist.
See [v1.6 guide](docs/SCIENTIFIC_RESEARCH_V1_6.md) for API examples and limits.
The public offline GitHub Pages demonstration is unchanged.

'''
    return _once(text, '## Version 1.5 — unified scientific research workflow',
                 block + '## Version 1.5 — unified scientific research workflow', 'README')


def patch_workflow_page(text: str) -> str:
    banner = '''<section class="panel"><h2>NEW · Research decomposition v1.6</h2><p>Evidence-gap analysis and up to two controlled follow-up literature searches.</p><p><a href="/static/decompose.html">Open v1.6 research decomposition ↗</a></p></section>
'''
    return _once(text, '<div class="layout">', banner + '<div class="layout">', 'v1.5 workspace navigation')


def main() -> None:
    # The cumulative v1.5 installer has its own baseline/conflict checks.
    ensure_v15()
    edits = (
        ('src/atlas/api.py', patch_api),
        ('pyproject.toml', lambda text: _once(text, 'version = "1.5.0"', 'version = "1.6.0"', 'version')),
        ('README.md', patch_readme),
        ('static/workflow.html', patch_workflow_page),
    )
    changes: dict[Path, bytes] = {}
    for rel, fn in edits:
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f'Missing required v1.5 file: {rel}')
        changes[path] = fn(path.read_text(encoding='utf-8')).encode('utf-8')
    for rel in (
        'src/atlas/science_decomposition.py', 'static/decompose.html',
        'static/decompose.js', 'tests/test_science_v16.py',
        'docs/SCIENTIFIC_RESEARCH_V1_6.md',
    ):
        path = ROOT / rel
        new = (V16 / rel).read_bytes()
        if path.exists() and path.read_bytes() != new:
            raise RuntimeError(f'Conflicting {rel}: v1.6 files not changed')
        changes[path] = new
    for path, data in changes.items():
        if not path.exists() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.6 installed locally; review git diff and run tests before committing.')
    print('No repository push, deployment, or public demo changes performed.')


if __name__ == '__main__':
    main()
