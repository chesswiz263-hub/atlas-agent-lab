"""ATLAS v2.5 Windows-compatible, fail-closed hosted fixture update.

Only edits tests/test_hosted_beta.py. Does not modify ATLAS app code.
"""
from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent

OLD = ("for src, out in [('atlas-chat-v24.html','atlas-chat-v24.html'),"
       "('atlas-chat-v24.js','atlas-chat-v24.js'),"
       "('atlas-chat-v24.css','atlas-chat-v24.css')]:\n"
       "        shutil.copy2(SOURCE.parent/'v24_assets'/src,base/out)")
NEW = ("for src, out in [('atlas-chat-v25.html','atlas-chat-v25.html'),"
       "('atlas-chat-v25.js','atlas-chat-v25.js'),"
       "('atlas-chat-v25.css','atlas-chat-v25.css')]:\n"
       "        shutil.copy2(SOURCE.parent/'v25_assets'/src,base/out)")


def apply(root: Path = ROOT) -> str:
    fixture = root / 'tests/test_hosted_beta.py'
    gateway = root / 'atlas_hosted_beta.py'
    git = root / '.git'
    if not git.is_dir() or not fixture.is_file() or not gateway.is_file():
        raise RuntimeError('Run this script from the atlas-agent-lab repository root, with v2.5 already installed.')
    if 'atlas-chat-v25.html' not in gateway.read_text(encoding='utf-8'):
        raise RuntimeError('The active gateway is not v2.5. Aborting without changing files.')
    for extension in ('html', 'js', 'css'):
        asset = root / 'v25_assets' / f'atlas-chat-v25.{extension}'
        if not asset.is_file():
            raise RuntimeError(f'Missing v2.5 test fixture source: {asset}')
    content = fixture.read_text(encoding='utf-8')
    if NEW in content and OLD not in content:
        return 'Hosted regression fixture already uses v2.5 assets. No changes made.'
    if content.count(OLD) != 1 or NEW in content:
        raise RuntimeError('Hosted regression fixture is customized or unexpected; refusing to overwrite it.')
    backup = git / 'atlas-v25-fixture-backups/test_hosted_beta.pre_v25.py'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists() and backup.read_text(encoding='utf-8') != content:
        raise RuntimeError('A different fixture backup already exists; refusing to overwrite it.')
    if not backup.exists():
        shutil.copy2(fixture, backup)
    fixture.write_text(content.replace(OLD, NEW), encoding='utf-8')
    return 'Updated tests/test_hosted_beta.py to copy v2.5 static assets. Backup saved inside .git.'


if __name__ == '__main__':
    try:
        print(apply())
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    print('Next: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests v25_tests')
