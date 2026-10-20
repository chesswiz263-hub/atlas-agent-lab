"""Conservative, repeatable ATLAS v2.3 on top of v2.2 + math hotfix.

Never replaces a customized gateway. Does not modify docs/ or public GitHub Pages.
The exact v2.2 gateway is backed up under .git (outside commits).
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'v23_assets'
SOURCE_GATEWAY = ROOT / 'atlas_hosted_beta_v23.reference.py'
V22_GATEWAY_SHA256 = '1c966245b446bb1dd5a0bda9dedf9a8226e8f334c9983dfb60cb2f6e63ba6dff'
V22_MATH_HOTFIX_SHA256 = '067728279dc569c1a895aa5bc44a77418176f56ca813c35c1c9b08e5cf519352'
ASSET_NAMES = ('atlas-chat-v23.html','atlas-chat-v23.js','atlas-chat-v23.css')


def digest(path: Path) -> str:
    # Windows Git may check out text files with CRLF: compare the normalized
    # source to the published known revisions, without relaxing other checks.
    return sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main():
    if not (ROOT/'pyproject.toml').exists() or not (ROOT/'src/atlas').is_dir():
        raise SystemExit('Run this in your atlas-agent-lab repository root.')
    required = [ROOT/'atlas_conversation_v22.py',ROOT/'atlas_math_v22.py',
                ROOT/'atlas_conversation_v23.py',ROOT/'atlas_math_v23.py',SOURCE_GATEWAY]
    required += [ASSETS/name for name in ASSET_NAMES]
    if any(not path.is_file() for path in required):
        raise SystemExit('Missing v2.2 or v2.3 source files; extract all ZIP contents to the repository root.')
    if digest(ROOT/'atlas_math_v22.py') != V22_MATH_HOTFIX_SHA256:
        raise SystemExit('Expected the verified v2.2 mathematics hotfix. No changes made.')
    gateway = ROOT / 'atlas_hosted_beta.py'
    if not gateway.is_file():
        raise SystemExit('Missing hosted gateway; install the v2.2 hosted upgrade first.')
    current = digest(gateway)
    new = digest(SOURCE_GATEWAY)
    if current not in (V22_GATEWAY_SHA256,new):
        raise SystemExit('Gateway is not the known v2.2 version or already-installed v2.3; refusing to overwrite customization.')
    static = ROOT / 'static'
    for name in ASSET_NAMES:
        target = static/name
        if target.is_file() and digest(target) != digest(ASSETS/name):
            raise SystemExit('Customized ' + str(target) + '; refusing to overwrite.')
    if current == V22_GATEWAY_SHA256:
        git_dir = ROOT/'.git'
        if not git_dir.is_dir():
            raise SystemExit('Expected .git directory so the original gateway can be backed up safely.')
        backup_dir = git_dir/'atlas-v23-backups'
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir/'atlas_hosted_beta.v22.py'
        if backup.is_file() and digest(backup)!=V22_GATEWAY_SHA256:
            raise SystemExit('Unexpected existing backup; refusing to overwrite.')
        shutil.copy2(gateway,backup)
    static.mkdir(exist_ok=True)
    for name in ASSET_NAMES:
        target=static/name
        if not target.exists():
            shutil.copy2(ASSETS/name,target)
            print('Created:',target.relative_to(ROOT))
    if current == V22_GATEWAY_SHA256:
        shutil.copy2(SOURCE_GATEWAY,gateway)
        print('Updated hosted gateway to v2.3; backed up v2.2 under .git.')
    else:
        print('Gateway already at v2.3; no overwrite needed.')
    fixture=ROOT/'tests/test_hosted_beta.py'
    if fixture.is_file():
        text=fixture.read_text(encoding='utf-8')
        old="for src, out in [('index.html','atlas-chat-v22.html'),('atlas-chat.js','atlas-chat-v22.js'),('atlas-chat.css','atlas-chat-v22.css')]:\n        shutil.copy2(SOURCE.parent/'atlas_v22_assets'/src,base/out)"
        new="for src, out in [('atlas-chat-v23.html','atlas-chat-v23.html'),('atlas-chat-v23.js','atlas-chat-v23.js'),('atlas-chat-v23.css','atlas-chat-v23.css')]:\n        shutil.copy2(SOURCE.parent/'v23_assets'/src,base/out)"
        if old in text:
            fixture.write_text(text.replace(old,new),encoding='utf-8')
            print('Updated isolated gateway regression fixture for v2.3 assets.')
        elif new not in text:
            print('WARNING: Hosted gateway fixture differs from expected v2.2; inspect tests/test_hosted_beta.py before pushing.')
    print('ATLAS v2.3 installed locally; nothing committed, pushed or deployed.')
    print('Run: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests')


if __name__ == '__main__':
    main()
