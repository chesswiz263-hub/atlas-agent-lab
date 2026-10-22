"""Fail-closed installer for ATLAS v2.4.1 on an unmodified v2.4 gateway."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
OLD_GATEWAY_SHA='056e832f4976c1e8b726a9c4423f5550cf3ad6145b06e1a1b72c2571e043f310'
NEW_GATEWAY_SHA='b6ba9911a2562fc1ebad618e6308cfa0813a5500ec6abc0acac167866184e504'


def checksum(file:Path)->str:
    return sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def install():
    if not (ROOT/'.git').is_dir() or not (ROOT/'pyproject.toml').is_file():
        raise SystemExit('Run from the ATLAS Git checkout (root beside pyproject.toml).')
    source=ROOT/'atlas_hosted_beta_v241.reference.py'
    gateway=ROOT/'atlas_hosted_beta.py'
    files=[source,gateway, ROOT/'atlas_conversation_v241.py', ROOT/'atlas_math_extension_v241.py',
           ROOT/'atlas_conversation_v24.py', ROOT/'atlas_conversation_v23.py',ROOT/'atlas_math_v23.py',
           ROOT/'static'/'atlas-chat-v24.html', ROOT/'static'/'atlas-chat-v24.js']
    if any(not p.is_file() for p in files):
        raise SystemExit('Missing v2.4 dependencies or v2.4.1 files. Extract the complete ZIP before installation.')
    if checksum(source)!=NEW_GATEWAY_SHA:
        raise SystemExit('New gateway source differs from tested v2.4.1 reference; refusing install.')
    status=checksum(gateway)
    if status==NEW_GATEWAY_SHA:
        print('ATLAS v2.4.1 gateway already installed. No changes made.');return
    if status!=OLD_GATEWAY_SHA:
        raise SystemExit('Hosted gateway has customized/unrecognized edits. Nothing overwritten; review or merge manually.')
    backup=ROOT/'.git'/'atlas-v241-backups'/'atlas_hosted_beta.v24.py'
    backup.parent.mkdir(parents=True,exist_ok=True)
    if backup.exists() and checksum(backup)!=OLD_GATEWAY_SHA:
        raise SystemExit('Unexpected prior backup; refusing to overwrite.')
    if not backup.exists():shutil.copy2(gateway,backup)
    shutil.copy2(source,gateway)
    print('Updated hosted gateway to v2.4.1; backed up v2.4 under .git.')
    print('No push or Render deployment performed. Research and model configuration unchanged.')
    print('Next: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests')

if __name__=='__main__':install()
