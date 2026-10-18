"""Install ChatGPT-style ATLAS frontend without rewriting existing pages or private code.

Extract the release ZIP into the existing ATLAS repository root. Run this
script there. GitHub Pages source is docs/ (branch main /docs).

The existing private FastAPI static/ folder receives the same frontend at
/static/atlas-chat.html so its API requests can stay SAME-ORIGIN and authenticated.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "atlas_public_ui_source"
TARGETS = (
    ("index.html", "docs/index.html"),
    ("atlas-chat.css", "docs/atlas-chat.css"),
    ("atlas-chat.js", "docs/atlas-chat.js"),
    ("index.html", "static/atlas-chat.html"),
    ("atlas-chat.css", "static/atlas-chat.css"),
    ("atlas-chat.js", "static/atlas-chat.js"),
)


def main():
    if not (ROOT / 'pyproject.toml').is_file() or not (ROOT / 'static').is_dir():
        raise RuntimeError('Run from the existing ATLAS repository root (pyproject.toml and static/ expected).')
    proposed = []
    for src_name, rel in TARGETS:
        src = SOURCE / src_name
        target = ROOT / rel
        if not src.is_file():
            raise RuntimeError(f'Missing bundled frontend file: {src_name}')
        payload = src.read_bytes()
        if target.exists() and target.read_bytes() != payload:
            raise RuntimeError(f'Existing customized file {rel}: aborting BEFORE any changes. Merge manually after backing it up.')
        proposed.append((target, payload))
    nojekyll = ROOT / 'docs/.nojekyll'
    if nojekyll.exists() and not nojekyll.is_file():
        raise RuntimeError('docs/.nojekyll exists but is not a regular file')
    for target, payload in proposed:
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.is_file():
            target.write_bytes(payload)
            print('Installed', target.relative_to(ROOT))
        else:
            print('Already installed', target.relative_to(ROOT))
    if not nojekyll.exists():
        nojekyll.write_bytes(b'')
        print('Installed docs/.nojekyll')
    print('ATLAS browser installed locally. No git commit, GitHub push, hosting or Pages settings were changed.')
    print('Public Pages: Settings > Pages > Deploy from a branch > main > /docs.')
    print('Private backend: visit /static/atlas-chat.html on the running authenticated server.')


if __name__ == '__main__':
    main()
