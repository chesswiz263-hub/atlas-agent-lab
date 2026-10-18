"""Cumulative ATLAS v1.0/1.1/1.2 -> v1.3 upgrade for a local checkout.

Install in the repository root. Preflight is fail-closed for customized v1.2 files;
no remote Git operations occur. The older cumulative v1.2 installer is invoked
only when needed (it performs its own preflight and writes v1.2 locally).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'atlas_science_package'
V12 = BUNDLE / 'v12'
V13 = BUNDLE / 'v13'


def replace_once(data: str, old: str, new: str, name: str) -> str:
    if new in data:
        return data
    if data.count(old) != 1:
        raise RuntimeError(f'{name} differs from expected v1.2 code; do not overwrite customized files')
    return data.replace(old, new, 1)


def upgrade_base_if_needed():
    api = ROOT / 'src/atlas/api.py'
    if not api.exists():
        raise RuntimeError('Run installer in the root of the original atlas-agent-lab checkout')
    text = api.read_text(encoding='utf-8')
    if ('from atlas.science_v12 import ScienceAskV12Request, scientific_answer_v12' in text or
            'from atlas.science_theories import ScienceAskV13Request, scientific_answer_v13' in text):
        return
    spec = importlib.util.spec_from_file_location('atlas_cumulative_v12', V12 / 'apply_science_v12.py')
    if not spec or not spec.loader:
        raise RuntimeError('Missing bundled v1.2 installer')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT, mod.BUNDLE, mod.V11, mod.V12 = ROOT, BUNDLE, BUNDLE / 'v11', V12
    mod.main()


def patch_api(text: str) -> str:
    if 'from atlas.science_theories import ScienceAskV13Request, scientific_answer_v13' not in text:
        text = replace_once(text, 'from atlas.science_v12 import ScienceAskV12Request, scientific_answer_v12',
                            'from atlas.science_theories import ScienceAskV13Request, scientific_answer_v13', 'API import')
        text = replace_once(text, 'async def science_ask(request: ScienceAskV12Request):',
                            'async def science_ask(request: ScienceAskV13Request):', 'API request')
        text = replace_once(text, 'return await scientific_answer_v12(request)',
                            'return await scientific_answer_v13(request)', 'API handler')
    return text.replace('version="1.2.0"', 'version="1.3.0"').replace('"version": "1.2.0"', '"version": "1.3.0"')


def patch_pyproject(text: str) -> str:
    if 'version = "1.2.0"' in text:
        return text.replace('version = "1.2.0"', 'version = "1.3.0"', 1)
    if 'version = "1.3.0"' in text:
        return text
    raise RuntimeError('Unexpected pyproject project version')


def patch_readme(text: str) -> str:
    heading = '## Version 1.3 — structured competing-theory analysis'
    if heading in text:
        return text
    anchor = '## Version 1.2 — primary publication evidence preview'
    intro = '''## Version 1.3 — structured competing-theory analysis

The private **Science research** workspace can now compare user-specified,
observable predictions for up to four competing theories. It locates bounded
passages from DOI-crosschecked, open-access repository XML and builds an evidence
matrix with article fingerprints and paragraph locators. Deterministic prediction
conflict checks only compare explicitly opposed outcomes under identical written
conditions. Optional, explicitly enabled model interpretation requires exact
source excerpts and correct evidence IDs, but is not independently claim-verified.
See [v1.3 methodology and limitations](docs/SCIENTIFIC_RESEARCH_V1_3.md).
The public GitHub Pages demonstration remains offline and unchanged.

'''
    return replace_once(text, anchor, intro + anchor, 'README')


def patch_v12(text: str) -> str:
    text = replace_once(text, 'client: httpx.AsyncClient | None = None) -> dict:',
                        'client: httpx.AsyncClient | None = None,\n                                *, _segments_sink: dict[int, list[dict]] | None = None) -> dict:',
                        'v1.2 internal signature')
    return replace_once(text, '        quote_checks = verify_quotes(request.quote_candidates, papers, segments_by_id)',
                        '        if _segments_sink is not None:\n            _segments_sink.update(segments_by_id)\n'
                        '        quote_checks = verify_quotes(request.quote_candidates, papers, segments_by_id)',
                        'v1.2 internal evidence handoff')


def main() -> None:
    upgrade_base_if_needed()
    required = ['src/atlas/api.py', 'src/atlas/science_v12.py', 'pyproject.toml', 'README.md',
                'static/science.html', 'static/science.js', 'static/science.css']
    for item in required:
        if not (ROOT / item).is_file():
            raise RuntimeError(f'Missing required original file: {item}')
    patches = {'src/atlas/api.py': patch_api, 'src/atlas/science_v12.py': patch_v12,
               'pyproject.toml': patch_pyproject, 'README.md': patch_readme}
    stage: dict[Path, bytes] = {}
    for relative, fn in patches.items():
        path = ROOT / relative
        stage[path] = fn(path.read_text(encoding='utf-8')).encode('utf-8')
    for rel in ('static/science.html', 'static/science.css', 'static/science.js'):
        target, baseline = (V13 / rel).read_bytes(), (V12 / rel).read_bytes()
        path = ROOT / rel
        if path.read_bytes() not in (baseline, target):
            raise RuntimeError(f'Customized {rel}: no changes written by v1.3. Merge UI manually')
        stage[path] = target
    for rel in ('src/atlas/science_theories.py', 'tests/test_science_v13.py',
                'docs/SCIENTIFIC_RESEARCH_V1_3.md'):
        target = (V13 / rel).read_bytes()
        path = ROOT / rel
        if path.exists() and path.read_bytes() != target:
            raise RuntimeError(f'Existing {rel} differs; no changes written by v1.3')
        stage[path] = target
    # v1.2 creates original 1.1/1.2 tests and docs; our v1.3 files are additive.
    for path, target in stage.items():
        if not path.exists() or path.read_bytes() != target:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(target)
            print('Installed:', path.relative_to(ROOT))
    print('ATLAS v1.3 ready locally. Install dependencies and run pytest -q before pushing.')
    print('This installer did not access GitHub or change the offline GitHub Pages demo.')


if __name__ == '__main__':
    main()
