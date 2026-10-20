"""ATLAS v2.3.1 natural-language calculus parser hotfix.

Safe and idempotent on the verified v2.3 release. Refuses unknown customizations.
Installs no dependencies, does not touch the v1.9 science engine, v2.3 math worker,
Render settings, public Pages content, hosted authentication or model budgets.
"""
from hashlib import sha256
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'v231_hotfix_assets' / 'atlas_conversation_v23.py'
TARGET = ROOT / 'atlas_conversation_v23.py'
BASELINE = '62856cd319c2f802b111d7ce670882c97e0b02a3743c8f38b769da9007156c5f'
PATCHED = '97449146115c6e8628214a6c41960447f8e30aa54b7516fa88bef4b33a44012f'


def digest(path):
    return sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main():
    if not (ROOT/'pyproject.toml').is_file() or not (ROOT/'src/atlas').is_dir():
        raise SystemExit('Run this installer in the atlas-agent-lab repository root.')
    if not (ROOT/'.git').is_dir():
        raise SystemExit('Missing .git folder; refusing to overwrite without a private backup location.')
    if not TARGET.is_file() or not SOURCE.is_file():
        raise SystemExit('Missing ATLAS v2.3 source or patch. Extract the entire hotfix ZIP.')
    if not (ROOT/'atlas_math_v23.py').is_file():
        raise SystemExit('ATLAS v2.3 math worker missing; install v2.3 first.')
    if digest(SOURCE) != PATCHED:
        raise SystemExit('Patch payload did not match its published checksum; no files changed.')
    current=digest(TARGET)
    if current == PATCHED:
        print('ATLAS v2.3.1 math-question parser hotfix is already installed. No changes made.')
        return
    if current != BASELINE:
        raise SystemExit('Existing v2.3 conversation file differs from the expected release; refusing to overwrite a customization.')
    backup_dir=ROOT/'.git'/'atlas-v231-backups'
    backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/'atlas_conversation_v23.original.py'
    if backup.exists() and digest(backup)!=BASELINE:
        raise SystemExit('Unexpected existing backup; refusing to overwrite.')
    if not backup.exists():
        shutil.copy2(TARGET,backup)
    temp = ROOT/'atlas_conversation_v23.py.v231.tmp'
    if temp.exists():
        raise SystemExit('Unexpected temporary file; refusing to overwrite.')
    try:
        shutil.copy2(SOURCE,temp)
        if digest(temp) != PATCHED:
            raise SystemExit('Copy failed integrity check; original retained.')
        os.replace(temp,TARGET)
    finally:
        if temp.exists():
            temp.unlink()
    print('Applied ATLAS v2.3.1 natural-language math parser hotfix.')
    print('Prior v2.3 file backed up under .git/atlas-v231-backups (not committed).')
    print('Existing v2.3 interface, mathematical worker, research evidence, and cost safeguards preserved.')
    print('Run: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests')
    print('No GitHub push or Render deploy was performed.')


if __name__ == '__main__':
    main()
