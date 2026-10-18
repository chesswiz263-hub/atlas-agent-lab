"""Cumulative, idempotent ATLAS v1.0/v1.1 -> v1.2 installation.

No GitHub network or destructive overwrites. Validate all patch anchors and
unmodified bundled-v1.1 replacements BEFORE writing any tracked file.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V11 = BUNDLE / 'v11'
V12 = BUNDLE / 'v12'


def _v11_module():
    spec = importlib.util.spec_from_file_location('atlas_legacy_upgrade', V11 / 'apply_science_upgrade.py')
    if spec is None or spec.loader is None:
        raise RuntimeError('Missing bundled v1.1 upgrade source')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_one(data: str, old: str, new: str, field: str) -> str:
    if new in data:
        return data
    if data.count(old) != 1:
        raise RuntimeError(f'Unexpected {field} content; merge changes manually, leaving your code untouched')
    return data.replace(old, new, 1)


def api_12(data: str) -> str:
    data = replace_one(data, 'from atlas.science import ScienceAskRequest, scientific_answer',
                       'from atlas.science_v12 import ScienceAskV12Request, scientific_answer_v12', 'API imports')
    data = replace_one(data, 'async def science_ask(request: ScienceAskRequest):',
                       'async def science_ask(request: ScienceAskV12Request):', 'science ask signature')
    data = replace_one(data, 'return await scientific_answer(request)',
                       'return await scientific_answer_v12(request)', 'science ask handler')
    return data.replace('version="1.1.0"', 'version="1.2.0"').replace('"version": "1.1.0"', '"version": "1.2.0"')


def pyproject_12(data: str) -> str:
    data = replace_one(data, 'science = ["sympy>=1.13,<2"]',
                       'science = ["sympy>=1.13,<2", "defusedxml>=0.7.1,<1"]', 'science dependencies')
    return replace_one(data, 'version = "1.1.0"', 'version = "1.2.0"', 'project version')


def readme_12(data: str) -> str:
    introduction = '''## Version 1.2 — primary publication evidence preview

The private **Science research** workspace now retrieves bounded full-text XML
from the Europe PMC open-access subset where available, validates the DOI inside
the repository article, records SHA256 provenance, surfaces exact short passages
and supports literal quotation verification. Configured synthesis providers may
use numbered repository passages, but entailment and scientific truth are still
**not** automatically verified. Unavailable publisher/full text is not invented.
See [v1.2 verification notes](docs/SCIENTIFIC_RESEARCH_V1_2.md).

'''
    return replace_one(data, '## Version 1.1 — scientific discovery preview',
                       introduction + '## Version 1.1 — scientific discovery preview', 'README v1.2 section')


def main() -> None:
    api = ROOT / 'src/atlas/api.py'
    project = ROOT / 'pyproject.toml'
    index = ROOT / 'static/index.html'
    readme = ROOT / 'README.md'
    for path in (api, project, index, readme):
        if not path.exists():
            raise SystemExit(f'Missing original repository file: {path.relative_to(ROOT)}')
    patch11 = _v11_module()
    oldapi = api.read_text(encoding='utf-8')
    need_11 = '@app.post("/api/science/ask")' not in oldapi
    stage = {}
    if need_11:
        # v1.1 code files are not overwritten when the repo already contains them.
        for rel in ('src/atlas/science.py', 'src/atlas/science_math.py',
                    'static/science.html', 'static/science.js', 'static/science.css'):
            path, bundled = ROOT / rel, V11 / rel
            if path.exists() and path.read_bytes() != bundled.read_bytes():
                raise RuntimeError(f'Existing {rel} conflicts with expected v1.1 baseline')
            stage[path] = bundled.read_bytes()
    else:
        for rel in ('src/atlas/science.py', 'src/atlas/science_math.py',
                    'static/science.html', 'static/science.js', 'static/science.css'):
            if not (ROOT / rel).is_file():
                raise RuntimeError(f'Partially installed v1.1: missing {rel}; repair before upgrading')
    originals = {p: p.read_text(encoding='utf-8') for p in (api, project, index, readme)}
    if need_11:
        originals[api] = patch11.patch_api(originals[api])
        originals[project] = patch11.patch_pyproject(originals[project])
        originals[index] = patch11.patch_index(originals[index])
        originals[readme] = patch11.patch_readme(originals[readme])
    stage[api] = api_12(originals[api]).encode()
    stage[project] = pyproject_12(originals[project]).encode()
    stage[index] = originals[index].encode()
    stage[readme] = readme_12(originals[readme]).encode()

    for rel in ('static/science.html', 'static/science.css', 'static/science.js'):
        path = ROOT / rel
        current = stage.get(path, path.read_bytes() if path.exists() else None)
        target = (V12 / rel).read_bytes()
        baseline = (V11 / rel).read_bytes()
        if current not in (baseline, target):
            raise RuntimeError(f'Customized {rel}; review and merge the v1.2 UI changes manually')
        stage[path] = target

    for rel in ('src/atlas/science_primary.py', 'src/atlas/science_v12.py',
                'tests/test_science_v12.py', 'docs/SCIENTIFIC_RESEARCH_V1_2.md'):
        target = (V12 / rel).read_bytes()
        path = ROOT / rel
        if path.exists() and path.read_bytes() != target:
            raise RuntimeError(f'File collision: {rel}; existing changes left intact')
        stage[path] = target

    for rel in ('tests/test_science_v11.py', 'docs/SCIENTIFIC_RESEARCH_V1_1.md'):
        path, bundled = ROOT / rel, V11 / rel
        if not path.exists():
            stage[path] = bundled.read_bytes()

    # Preflight completed; commit changes to the local checkout only, not remote GitHub.
    for path, content in stage.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)
            print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.2 ready locally. Run python -m pip install -e ".[dev,science]" and pytest -q.')
    print('The offline GitHub Pages demonstration remains unchanged.')


if __name__ == '__main__':
    main()
