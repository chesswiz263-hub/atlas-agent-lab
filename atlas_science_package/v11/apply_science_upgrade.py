"""One-time, idempotent ATLAS v1.0 -> v1.1 science API wiring.

Run from your atlas-agent-lab repository root AFTER copying the upgrade files there.
The script validates all anchors before editing any existing source files.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / 'src/atlas/api.py'
PROJECT = ROOT / 'pyproject.toml'
INDEX = ROOT / 'static/index.html'
README = ROOT / 'README.md'


def inject_once(text: str, marker: str, addition: str, unique: str) -> str:
    if unique in text:
        return text
    if text.count(marker) != 1:
        raise RuntimeError(f'Expected one exact anchor, got {text.count(marker)}: {marker[:75]!r}')
    return text.replace(marker, addition + marker, 1)


def patch_api(text: str) -> str:
    text = inject_once(text, 'from atlas.research import create_dossier\n',
        'from atlas.science import ScienceAskRequest, scientific_answer\n',
        'from atlas.science import ScienceAskRequest, scientific_answer')
    text = inject_once(text, '    @app.get("/api/embeddings/status")',
        '''    @app.post("/api/science/ask")
    async def science_ask(request: ScienceAskRequest):
        """Live literature discovery, DOI crosschecks and bounded scientific synthesis."""
        return await scientific_answer(request)

''', '@app.post("/api/science/ask")')
    text = inject_once(text, '    @app.get("/api/embeddings/status")',
        '''    @app.get("/api/science/papers")
    async def science_papers(q: str, limit: int = 5):
        from atlas.science import discover_papers
        if not 5 <= len(q.strip()) <= 500 or not 1 <= limit <= 6:
            raise HTTPException(422, "Invalid science discovery query or limit")
        return await discover_papers(q, limit)

''', '@app.get("/api/science/papers")')
    return text.replace('version="1.0.0"', 'version="1.1.0"').replace('"version": "1.0.0"', '"version": "1.1.0"')


def patch_pyproject(text: str) -> str:
    text = text.replace('version = "1.0.0"', 'version = "1.1.0"', 1)
    return inject_once(text, 'nli = ["transformers>=4.40,<6", "torch>=2.2"]',
                       'science = ["sympy>=1.13,<2"]\n', 'science = ["sympy>=1.13,<2"]')


def patch_index(text: str) -> str:
    return inject_once(text, '      </nav>',
        '        <a href="/static/science.html" class="nav-item"><span class="nav-icon">∑</span> Science research <span class="nav-hotkey">05</span></a>\n',
        'href="/static/science.html"')


def patch_readme(text: str) -> str:
    text = inject_once(text, '## Version 1.0 — evidence-first research foundation',
        '## Version 1.1 — scientific discovery preview\n\nThe **private** ATLAS backend now supports live scholarly discovery with OpenAlex,\nDOI/title/year crosschecking against Crossref metadata, bounded SymPy mathematics,\nstructured theory-mention comparisons and optional abstract-grounded synthesis.\nUse the **Science research** page in the private workbench or `POST /api/science/ask`.\nScientific claims, exact publisher quotations, and theory rankings are **not**\nindependently verified; see [v1.1 scientific integrity](docs/SCIENTIFIC_RESEARCH_V1_1.md).\nGitHub Pages remains the original offline public retrieval demonstration.\n\n', '## Version 1.1 — scientific discovery preview')
    return text.replace('v1.0.0 · Evidence relevance',
                        'v1.1.0 · Scientific discovery preview + evidence relevance', 1)


def main() -> None:
    newfiles = [ROOT / x for x in (
        'src/atlas/science.py', 'src/atlas/science_math.py',
        'static/science.html', 'static/science.css', 'static/science.js')]
    for file in [API, PROJECT, INDEX, README, *newfiles]:
        if not file.is_file():
            raise SystemExit(f'Missing required ATLAS file: {file.relative_to(ROOT)}')
    updates = [(API, patch_api), (PROJECT, patch_pyproject),
               (INDEX, patch_index), (README, patch_readme)]
    prepared = []
    for path, transform in updates:
        old = path.read_text(encoding='utf-8')
        new = transform(old)
        prepared.append((path, old, new))
    for path, old, new in prepared:
        if old != new:
            path.write_text(new, encoding='utf-8')
            print(f'Updated: {path.relative_to(ROOT)}')
        else:
            print(f'Already current: {path.relative_to(ROOT)}')
    print('ATLAS scientific-research upgrade wired. Run pytest -q and node --check static/science.js.')
    print('The offline docs/ GitHub Pages demo is intentionally unchanged.')


if __name__ == '__main__':
    main()
