"""Safe local installer for ATLAS v2.4 on verified v2.3.1."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'v24_assets'
SOURCE=ROOT/'atlas_hosted_beta_v24.reference.py'
GATEWAY_V23='33565e151cd133c738e956a6fdc7d118a78008867a5921066692f08c107da020'
PARSER_V231='97449146115c6e8628214a6c41960447f8e30aa54b7516fa88bef4b33a44012f'
NAMES=('atlas-chat-v24.html','atlas-chat-v24.js','atlas-chat-v24.css')

def digest(path):return sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def main():
    if not (ROOT/'pyproject.toml').exists() or not (ROOT/'src/atlas').is_dir():
        raise SystemExit('Run in the atlas-agent-lab repository root.')
    required=[ROOT/'atlas_conversation_v22.py',ROOT/'atlas_math_v22.py',
              ROOT/'atlas_conversation_v23.py',ROOT/'atlas_math_v23.py',
              ROOT/'atlas_conversation_v24.py',SOURCE,*[ASSETS/n for n in NAMES]]
    if any(not p.is_file() for p in required):
        raise SystemExit('Required v2.3.1/v2.4 files missing. Extract complete ZIP first.')
    if digest(ROOT/'atlas_conversation_v23.py') != PARSER_V231:
        raise SystemExit('v2.3.1 parser does not match the verified hotfix. Refusing overwrite.')
    gateway=ROOT/'atlas_hosted_beta.py'
    if not gateway.is_file():raise SystemExit('Missing hosted gateway')
    curr=digest(gateway);new=digest(SOURCE)
    if curr not in (GATEWAY_V23,new):
        raise SystemExit('Unexpected hosted gateway; refusing to overwrite custom code.')
    for name in NAMES:
        dest=ROOT/'static'/name
        if dest.exists() and digest(dest)!=digest(ASSETS/name):
            raise SystemExit('Customized v2.4 static file detected: '+name)
    fixture=ROOT/'tests/test_hosted_beta.py'
    old="for src, out in [('atlas-chat-v23.html','atlas-chat-v23.html'),('atlas-chat-v23.js','atlas-chat-v23.js'),('atlas-chat-v23.css','atlas-chat-v23.css')]:\n        shutil.copy2(SOURCE.parent/'v23_assets'/src,base/out)"
    new_line="for src, out in [('atlas-chat-v24.html','atlas-chat-v24.html'),('atlas-chat-v24.js','atlas-chat-v24.js'),('atlas-chat-v24.css','atlas-chat-v24.css')]:\n        shutil.copy2(SOURCE.parent/'v24_assets'/src,base/out)"
    fix_text=None
    if fixture.is_file():
        t=fixture.read_text(encoding='utf-8')
        if old in t:fix_text=t.replace(old,new_line)
        elif new_line not in t:raise SystemExit('Hosted regression fixture unexpected; inspect before installing v2.4.')
    if curr==GATEWAY_V23:
        if not (ROOT/'.git').is_dir():raise SystemExit('Missing .git backup folder.')
        backup=ROOT/'.git'/'atlas-v24-backups'/'atlas_hosted_beta.v23.py'
        backup.parent.mkdir(exist_ok=True)
        if backup.exists() and digest(backup)!=GATEWAY_V23:
            raise SystemExit('Unexpected existing backup; refusing to overwrite.')
        shutil.copy2(gateway,backup)
        shutil.copy2(SOURCE,gateway)
        print('Updated hosted gateway to v2.4; backed up v2.3 under .git.')
    for name in NAMES:
        dest=ROOT/'static'/name
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists():shutil.copy2(ASSETS/name,dest);print('Created',dest.relative_to(ROOT))
    if fix_text is not None:
        fixture.write_text(fix_text,encoding='utf-8')
        print('Updated hosted authentication test fixture for v2.4.')
    print('ATLAS v2.4 installed locally; not committed, pushed or deployed.')
    print('Run: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests')

if __name__=='__main__':main()
