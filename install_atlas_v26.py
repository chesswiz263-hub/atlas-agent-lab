"""Fail-closed additive v2.6 gateway/assets switch. Does not run any network calls."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import shutil

ROOT=Path(__file__).resolve().parent

def digest(p:Path)->str:
    return sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def main()->int:
    target=ROOT/'atlas_hosted_beta.py'
    old=ROOT/'atlas_hosted_beta_v25.reference.py'
    new=ROOT/'atlas_hosted_beta_v26.reference.py'
    required=[ROOT/'.git',ROOT/'pyproject.toml',target,old,new,
              ROOT/'atlas_retrieval_v25.py',ROOT/'atlas_conversation_v25.py',
              ROOT/'atlas_claims_v26.py',ROOT/'atlas_retrieval_v26.py',ROOT/'atlas_conversation_v26.py']
    required += [ROOT/'v26_assets'/f'atlas-chat-v26.{ext}' for ext in ('html','css','js')]
    if any(not f.exists() for f in required):
        print('STOP: missing Git root, v2.5 prerequisites, or v2.6 files; no changes.');return 2
    source=new.read_text(encoding='utf-8')
    if ('from atlas_conversation_v26 import run_chat_v26 as run_chat' not in source or
        'csrf_for(token)' not in source or 'atlas-chat-v26.html' not in source):
        print('STOP: v2.6 reference gateway failed validation.');return 2
    if digest(target) not in (digest(old),digest(new)):
        print('STOP: custom/unrecognized hosted gateway. Review and merge manually; no changes.');return 2
    static=ROOT/'static';static.mkdir(exist_ok=True)
    copies=[(ROOT/'v26_assets'/f'atlas-chat-v26.{ext}',static/f'atlas-chat-v26.{ext}') for ext in ('html','css','js')]
    if any(dst.exists() and digest(src)!=digest(dst) for src,dst in copies):
        print('STOP: edited v2.6 static asset detected; no changes.');return 2
    backup=ROOT/'.git'/'atlas-v26-backups'/'atlas_hosted_beta.v25.py'
    if target.read_bytes()!=new.read_bytes():
        if backup.exists() and digest(backup)!=digest(old):
            print('STOP: v2.5 backup differs; no changes.');return 2
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():shutil.copy2(target,backup)
    for src,dst in copies:
        if not dst.exists():shutil.copy2(src,dst);print('Created',dst.relative_to(ROOT))
    if digest(target)!=digest(new):
        shutil.copy2(new,target);print('Activated v2.6 gateway; v2.5 backed up in .git.')
    else:print('v2.6 gateway already installed.')
    print('No deployment, credentials, API calls, model activation, commit, or Git push performed.')
    print('Run: python -m pytest -q v26_tests v25_tests')
    return 0

if __name__=='__main__':raise SystemExit(main())
