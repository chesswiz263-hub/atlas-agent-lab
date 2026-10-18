"""Cumulative local ATLAS v1.0–v1.3 -> v1.4 physics research upgrade.

No network/GitHub changes. New v1.4 edits are staged and checked before writing;
previous cumulative installer is used only if a previous upgrade is necessary.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V14 = BUNDLE / 'v14'
V13 = BUNDLE / 'v13'


def replace_once(text: str, old: str, new: str, context: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f'Unexpected {context}; local modification requires manual merge')
    return text.replace(old, new, 1)


def ensure_previous_upgrade() -> None:
    api = ROOT / 'src/atlas/api.py'
    if not api.is_file():
        raise RuntimeError('Run from the original atlas-agent-lab repository root')
    current = api.read_text(encoding='utf-8')
    if 'from atlas.science_theories import ScienceAskV13Request, scientific_answer_v13' in current:
        return
    path = ROOT / 'apply_science_v13.py'
    if not path.is_file():
        raise RuntimeError('Missing cumulative v1.3 installer')
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v13', path)
    if not spec or not spec.loader:
        raise RuntimeError('Unable to load cumulative v1.3 installer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.BUNDLE = BUNDLE
    module.V12 = BUNDLE / 'v12'
    module.V13 = V13
    module.main()


def patch_api(text: str) -> str:
    text = replace_once(
        text,
        'from atlas.science_theories import ScienceAskV13Request, scientific_answer_v13\n',
        'from atlas.science_theories import ScienceAskV13Request, scientific_answer_v13\n'
        'from atlas.science_physics import PhysicsResearchRequest, scientific_physics\n', 'API import')
    text = replace_once(text, '    @app.get("/api/embeddings/status")',
        '    @app.post("/api/science/physics")\n'
        '    async def science_physics(request: PhysicsResearchRequest):\n'
        '        """Bounded arXiv metadata and physics checks; no unsourced scientific verdicts."""\n'
        '        return await scientific_physics(request)\n\n'
        '    @app.get("/api/embeddings/status")', 'API route')
    return text.replace('version="1.3.0"', 'version="1.4.0"').replace('"version": "1.3.0"', '"version": "1.4.0"')


def patch_project(text: str) -> str:
    return replace_once(text, 'version = "1.3.0"', 'version = "1.4.0"', 'project version')


def patch_readme(text: str) -> str:
    block = '''## Version 1.4 — physics and mathematical research laboratory

The private **Physics laboratory** (`/static/physics.html`) adds arXiv Atom metadata discovery,
SI dimensional checking, bounded polynomial integration and roots, and reproducible
mechanics calculations with deterministic algorithm/inputs fingerprints. Publication
metadata does not establish primary-text verification, peer review or scientific truth;
unit consistency and a reproducible numerical run do not validate physical assumptions.
See [v1.4 scientific checks](docs/SCIENTIFIC_RESEARCH_V1_4.md). The existing v1.3 theory
comparison and public offline GitHub Pages demo remain unchanged.

'''
    return replace_once(text, '## Version 1.3 — structured competing-theory analysis',
                        block + '## Version 1.3 — structured competing-theory analysis', 'README')


def patch_science_html(text: str) -> str:
    insertion = '''    <section class="panel"><h2>NEW · Physics laboratory 1.4</h2><p>Search arXiv preprint metadata, check dimensions, and run audited symbolic and numerical calculations.</p><p><a href="/static/physics.html">Open Physics laboratory ↗</a></p></section>
'''
    return replace_once(text, '    <div class="layout">', insertion + '    <div class="layout">', 'science HTML')


def main() -> None:
    ensure_previous_upgrade()
    required = ['src/atlas/api.py', 'pyproject.toml', 'README.md', 'static/science.html']
    for rel in required:
        if not (ROOT / rel).is_file():
            raise RuntimeError(f'Missing required file: {rel}')
    stage: dict[Path, bytes] = {}
    for rel, transform in [
        ('src/atlas/api.py', patch_api), ('pyproject.toml', patch_project),
        ('README.md', patch_readme),
    ]:
        path = ROOT / rel
        stage[path] = transform(path.read_text(encoding='utf-8')).encode('utf-8')
    # Safeguard against editing a customized v1.3 research page.
    science_page = ROOT / 'static/science.html'
    baseline = (V13 / 'static/science.html').read_bytes()
    target = patch_science_html(baseline.decode('utf-8')).encode('utf-8')
    if science_page.read_bytes() not in (baseline, target):
        raise RuntimeError('Customized static/science.html; merge link manually; no v1.4 writes made')
    stage[science_page] = target
    for rel in ['src/atlas/science_arxiv.py', 'src/atlas/science_physics.py',
                'static/physics.html', 'static/physics.js', 'tests/test_science_v14.py',
                'docs/SCIENTIFIC_RESEARCH_V1_4.md']:
        path = ROOT / rel
        bundled = (V14 / rel).read_bytes()
        if path.exists() and path.read_bytes() != bundled:
            raise RuntimeError(f'Conflicting {rel}; no v1.4 writes made')
        stage[path] = bundled
    for path, content in stage.items():
        if not path.exists() or path.read_bytes() != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.4 ready in your local checkout. Run dependencies, tests and review git diff.')
    print('No push was performed. Public Pages demo remains offline and unchanged.')


if __name__ == '__main__':
    main()
