"""Fail-closed additive installer for v2.5 on an exact v2.4.1 gateway."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import shutil

ROOT=Path(__file__).resolve().parent

def digest(path:Path)->str:
    return sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def install():
    if not (ROOT/'.git').is_dir() or not (ROOT/'pyproject.toml').is_file():
        raise SystemExit('Use the Git repository root containing .git and pyproject.toml.')
    source=ROOT/'atlas_hosted_beta_v25.reference.py'
    previous=ROOT/'atlas_hosted_beta_v241.reference.py'
    target=ROOT/'atlas_hosted_beta.py'
    required=[source,previous,target,
        ROOT/'atlas_conversation_v25.py',ROOT/'atlas_retrieval_v25.py',
        ROOT/'atlas_math_extension_v25.py',ROOT/'atlas_conversation_v241.py',
        ROOT/'atlas_conversation_v24.py',ROOT/'atlas_math_extension_v241.py',
        ROOT/'v25_assets/atlas-chat-v25.js',ROOT/'v25_assets/atlas-chat-v25.css',ROOT/'v25_assets/atlas-chat-v25.html']
    if any(not p.is_file() for p in required):
        raise SystemExit('Missing v2.4.1 prerequisites or incomplete v2.5 ZIP extraction.')
    old_sha='b6ba9911a2562fc1ebad618e6308cfa0813a5500ec6abc0acac167866184e504'
    if digest(previous)!=old_sha:
        raise SystemExit('v2.4.1 gateway reference differs from expected; no changes made.')
    orig=target.read_text(encoding='utf-8')
    new=source.read_text(encoding='utf-8')
    if 'from atlas_conversation_v25 import run_chat_v25 as run_chat' not in new or 'atlas-chat-v25.html' not in new:
        raise SystemExit('Invalid v2.5 reference gateway.')
    target_sha=digest(target)
    if target_sha not in (old_sha,digest(source)):
        raise SystemExit('Hosted gateway has custom/unrecognized changes; refusing to overwrite.')
    static=ROOT/'static'
    static.mkdir(exist_ok=True)
    copies=[(ROOT/f'v25_assets/atlas-chat-v25.{suffix}',static/f'atlas-chat-v25.{suffix}') for suffix in ['html','js','css']]
    # Validate ALL destinations before ANY mutation (installer is repeatable).
    for source_asset,dest in copies:
        if dest.exists() and digest(source_asset)!=digest(dest):
            raise SystemExit(f'Unrecognized local edit to {dest.name}; refusing to overwrite.')
    backup=ROOT/'.git'/'atlas-v25-backups'/'atlas_hosted_beta.v241.py'
    if target_sha==old_sha:
        backup.parent.mkdir(parents=True,exist_ok=True)
        if backup.exists() and digest(backup)!=old_sha:
            raise SystemExit('Unexpected earlier gateway backup; refusing to overwrite.')
        if not backup.exists():shutil.copy2(target,backup)
    for src,dst in copies:
        if not dst.exists():shutil.copy2(src,dst);print('Created',dst.relative_to(ROOT))
    if target_sha!=digest(source):
        shutil.copy2(source,target)
        print('Updated hosted gateway to v2.5; v2.4.1 backed up under .git.')
    else:print('v2.5 gateway already installed.')
    print('No commit, GitHub push, or Render deployment performed.')
    print('Install dependency: python -m pip install "pypdf>=5,<7"')
    print('Run: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests v241_tests v25_tests')

if __name__=='__main__':install()
