"""Conservative v2.2 installer for the prior v2.1 hosted ATLAS gateway.

Refuses unfamiliar or customized gateway revisions rather than overwriting them.
Creates an exact backup and never touches the GitHub Pages files under docs/.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
BASE_GATEWAY_SHA='174b07d407bcfc8de1b42c1b9af652800ec6ae06c72eaba2fb210345504e2350'
SRC=ROOT/'atlas_v22_assets'


def digest(file:Path):return sha256(file.read_bytes()).hexdigest()


def main():
    if not (ROOT/'pyproject.toml').is_file() or not (ROOT/'src'/'atlas').is_dir():
        raise SystemExit('Run from the atlas-agent-lab root containing pyproject.toml and src/atlas')
    target=ROOT/'atlas_hosted_beta.py'
    incoming=ROOT/'atlas_hosted_beta_v22.py'
    if not incoming.is_file() or not target.is_file():
        raise SystemExit('Missing gateway file; install the v2.1 hosted research beta first')
    if not all((ROOT/name).is_file() for name in ('atlas_math_v22.py','atlas_conversation_v22.py')):
        raise SystemExit('Missing v2.2 mathematical and conversational engine files')
    if not all((SRC/name).is_file() for name in ('index.html','atlas-chat.js','atlas-chat.css')):
        raise SystemExit('Missing v2.2 browser assets')
    state='already-v22' if digest(target)==digest(incoming) else ('original-v21' if digest(target)==BASE_GATEWAY_SHA else 'unrecognized')
    if state=='unrecognized':
        raise SystemExit('Current atlas_hosted_beta.py is customized or not v2.1. Not overwriting it. Merge atlas_hosted_beta_v22.py manually after review.')
    assets={'index.html':'atlas-chat-v22.html','atlas-chat.js':'atlas-chat-v22.js','atlas-chat.css':'atlas-chat-v22.css'}
    static=ROOT/'static'
    for name,dest in assets.items():
        path=static/dest
        if path.is_file() and digest(path)!=digest(SRC/name):
            raise SystemExit(f'Unexpected customized {path}: refusing to overwrite')
    static.mkdir(exist_ok=True)
    for name,dest in assets.items():
        path=static/dest
        if not path.exists():
            shutil.copy2(SRC/name,path)
            print('Created',path.relative_to(ROOT))
    if state=='original-v21':
        backup=ROOT/'atlas_hosted_beta.v21.backup.py'
        if backup.exists() and digest(backup)!=BASE_GATEWAY_SHA:
            raise SystemExit('Backup name is already in use; rename backup before installing')
        shutil.copy2(target,backup)
        shutil.copy2(incoming,target)
        print('Updated hosted gateway; backed up v2.1 gateway')
    # Keep existing regression tests valid after versioned UI assets replace the login destination.
    tests=ROOT/'tests'/'test_hosted_beta.py'
    if tests.is_file():
        content=tests.read_text()
        old="for src, out in [('index.html','atlas-chat.html'),('atlas-chat.js','atlas-chat.js'),('atlas-chat.css','atlas-chat.css')]:\n        shutil.copy2(SOURCE.parent/'atlas_hosted_beta_assets'/src,base/out)"
        new="for src, out in [('index.html','atlas-chat-v22.html'),('atlas-chat.js','atlas-chat-v22.js'),('atlas-chat.css','atlas-chat-v22.css')]:\n        shutil.copy2(SOURCE.parent/'atlas_v22_assets'/src,base/out)"
        if old in content:
            tests.write_text(content.replace(old,new))
            print('Adapted existing v2.1 auth/CSRF regression fixture for v2.2')
        elif new not in content:
            print('WARNING: Existing hosted beta test fixture customized; review it manually')
    print('ATLAS v2.2 installed locally. No GitHub push or Render deploy performed.')
    print('Run: python -m pip install -e ".[dev,science]" "openai>=1.70,<3"')
    print('Then: python -m pytest -q tests && python -m pytest -q v22_tests')

if __name__=='__main__':main()
