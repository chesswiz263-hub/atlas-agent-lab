"""Cumulative ATLAS v1.0–v1.4 -> v1.5 unified scientific workflow patch.

Run from a copy of the original atlas-agent-lab checkout with the bundled payload
at the top level. Does not touch remote GitHub or public GitHub Pages.
Any v1.5 edits are staged and checked before writing; earlier cumulative installers
remain responsible for their own changes. Always review `git diff` afterwards.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V15 = BUNDLE / 'v15'
V14 = BUNDLE / 'v14'


def replace_once(text: str, old: str, new: str, context: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f'Unexpected {context}: manual merge required (no v1.5 writes)')
    return text.replace(old, new, 1)


def ensure_v14() -> None:
    api = ROOT / 'src/atlas/api.py'
    if not api.is_file():
        raise RuntimeError('Run from the root of an existing ATLAS repository')
    if 'from atlas.science_physics import PhysicsResearchRequest, scientific_physics' in api.read_text(encoding='utf-8'):
        return
    installer = ROOT / 'apply_science_v14.py'
    if not installer.is_file():
        raise RuntimeError('Missing v1.4 cumulative installer')
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v14', installer)
    if spec is None or spec.loader is None:
        raise RuntimeError('Could not load cumulative v1.4 installer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT, module.BUNDLE, module.V14, module.V13 = ROOT, BUNDLE, V14, BUNDLE / 'v13'
    module.main()


def patch_api(text: str) -> str:
    text = replace_once(text,
        'from atlas.science_physics import PhysicsResearchRequest, scientific_physics\n',
        'from atlas.science_physics import PhysicsResearchRequest, scientific_physics\n'
        'from atlas.science_workflow import ResearchWorkflowRequest, run_scientific_workflow\n',
        'API import')
    text = replace_once(text,
        '    @app.get("/api/embeddings/status")',
        '    @app.post("/api/science/workflow")\n'
        '    async def science_workflow(request: ResearchWorkflowRequest):\n'
        '        """Run bounded scientific discovery, checks and report synthesis."""\n'
        '        return await run_scientific_workflow(request)\n\n'
        '    @app.get("/api/embeddings/status")',
        'API route')
    return (text.replace('version="1.4.0"', 'version="1.5.0"')
                .replace('"version": "1.4.0"', '"version": "1.5.0"'))


def patch_pyproject(text: str) -> str:
    return replace_once(text, 'version = "1.4.0"', 'version = "1.5.0"', 'project version')


def patch_readme(text: str) -> str:
    block = '''## Version 1.5 — unified scientific research workflow

The authenticated **Research workflow** (`/static/workflow.html`) makes one bounded
research request across OpenAlex/Crossref/eligible Europe PMC full-text, optional
arXiv preprint metadata, existing v1.3 theory comparisons and v1.4 formal checks.
Outputs include a deterministic plan, source ledger, execution trace, mathematical
results and SHA-256 dossier fingerprint. Explicit provider selection allows one
optional model interpretation only when crosschecked primary-text excerpts exist.
The model narrative remains unverified scientific interpretation and is never
presented as independently confirmed entailment. For manual examples, see
[the v1.5 research guide](docs/SCIENTIFIC_RESEARCH_V1_5.md). GitHub Pages stays
offline and unchanged. No publishing/push occurs during installation.

'''
    return replace_once(text, '## Version 1.4 — physics and mathematical research laboratory',
                        block + '## Version 1.4 — physics and mathematical research laboratory', 'README')


def patch_science_page(text: str) -> str:
    panel = '''    <section class="panel"><h2>NEW · Unified research workflow 1.5</h2><p>Ask one question, run a bounded evidence and calculations plan, and export a source-labeled report.</p><p><a href="/static/workflow.html">Open unified research workflow ↗</a></p></section>
'''
    return replace_once(text, '    <div class="layout">', panel + '    <div class="layout">', 'science navigation')


def main() -> None:
    ensure_v14()
    required = ('src/atlas/api.py', 'pyproject.toml', 'README.md', 'static/science.html')
    for rel in required:
        if not (ROOT / rel).is_file():
            raise RuntimeError(f'Missing required file: {rel}')
    stage: dict[Path, bytes] = {}
    for rel, patch in (
        ('src/atlas/api.py', patch_api),
        ('pyproject.toml', patch_pyproject),
        ('README.md', patch_readme),
    ):
        path = ROOT / rel
        stage[path] = patch(path.read_text(encoding='utf-8')).encode('utf-8')
    # A changed v1.4 page requires a manual link merge; do not clobber edits.
    science = ROOT / 'static/science.html'
    # v1.4 patches the bundled v1.3 science page instead of replacing its file.
    source_page = (BUNDLE / 'v13/static/science.html').read_text(encoding='utf-8')
    physics_panel = '''    <section class="panel"><h2>NEW · Physics laboratory 1.4</h2><p>Search arXiv preprint metadata, check dimensions, and run audited symbolic and numerical calculations.</p><p><a href="/static/physics.html">Open Physics laboratory ↗</a></p></section>
'''
    baseline = source_page.replace('    <div class="layout">', physics_panel + '    <div class="layout">', 1)
    upgraded = patch_science_page(baseline)
    if science.read_text(encoding='utf-8') not in (baseline, upgraded):
        raise RuntimeError('Customized static/science.html: merge link manually; no v1.5 writes')
    stage[science] = upgraded.encode('utf-8')
    for rel in (
        'src/atlas/science_workflow.py', 'static/workflow.html',
        'static/workflow.js', 'tests/test_science_v15.py',
        'docs/SCIENTIFIC_RESEARCH_V1_5.md',
    ):
        path = ROOT / rel
        new_bytes = (V15 / rel).read_bytes()
        if path.exists() and path.read_bytes() != new_bytes:
            raise RuntimeError(f'Conflicting {rel}: no v1.5 files were written')
        stage[path] = new_bytes
    for path, new_bytes in stage.items():
        if not path.exists() or path.read_bytes() != new_bytes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(new_bytes)
            print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.5 staged locally. Install dependencies, run tests, and review git diff.')
    print('No GitHub push, publishing, or public demo changes were performed.')


if __name__ == '__main__':
    main()
