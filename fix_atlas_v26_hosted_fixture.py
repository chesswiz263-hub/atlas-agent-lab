"""Fix the original hosted-beta test fixture after installing ATLAS v2.6.

Only changes tests/test_hosted_beta.py. Intentionally never relaxes the
production gateway's required-static-assets, authentication, or CSRF checks.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent

OLD_LOOP = (
    "for src, out in [('atlas-chat-v25.html','atlas-chat-v25.html'),"
    "('atlas-chat-v25.js','atlas-chat-v25.js'),"
    "('atlas-chat-v25.css','atlas-chat-v25.css')]:"
)
NEW_LOOP = OLD_LOOP.replace('v25', 'v26')
OLD_COPY = "shutil.copy2(SOURCE.parent/'v25_assets'/src,base/out)"
NEW_COPY = OLD_COPY.replace('v25', 'v26')

# Match only the v2.5 copy fixture with the copy statement on the very next
# line. Preserve any CRLF line ending and its indentation in the patched file.
OLD_PATTERN = re.compile(re.escape(OLD_LOOP) + r'(\r?\n[ \t]+)' + re.escape(OLD_COPY))
NEW_PATTERN = re.compile(re.escape(NEW_LOOP) + r'(\r?\n[ \t]+)' + re.escape(NEW_COPY))


def apply(root: Path = ROOT) -> str:
    fixture = root / 'tests' / 'test_hosted_beta.py'
    gateway = root / 'atlas_hosted_beta.py'
    git = root / '.git'
    if not git.is_dir() or not fixture.is_file() or not gateway.is_file():
        raise RuntimeError('STOP: Run from the ATLAS Git repository root after installing v2.6.')
    gateway_text = gateway.read_text(encoding='utf-8')
    if 'atlas-chat-v26.html' not in gateway_text or 'csrf_for(token)' not in gateway_text:
        raise RuntimeError('STOP: Active gateway does not match expected authenticated v2.6 configuration.')
    for ext in ('html', 'js', 'css'):
        source = root / 'v26_assets' / f'atlas-chat-v26.{ext}'
        if not source.is_file():
            raise RuntimeError(f'STOP: Missing v2.6 source asset: {source.relative_to(root)}')

    original = fixture.read_bytes()
    try:
        content = original.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise RuntimeError('STOP: Test fixture is not UTF-8; refusing an unsafe edit.') from exc

    old_matches = list(OLD_PATTERN.finditer(content))
    new_matches = list(NEW_PATTERN.finditer(content))
    if not old_matches and len(new_matches) == 1:
        return 'Already fixed: hosted-beta fixture uses v2.6 assets. No changes.'
    if len(old_matches) != 1 or new_matches:
        raise RuntimeError('STOP: Fixture differs from the expected v2.5 version; no files changed.')

    changed = OLD_PATTERN.sub(lambda m: NEW_LOOP + m.group(1) + NEW_COPY, content, count=1)
    if changed == content or len(list(NEW_PATTERN.finditer(changed))) != 1:
        raise RuntimeError('STOP: Fixture patch failed verification; no files changed.')

    backup = git / 'atlas-v26-fixture-backups' / 'test_hosted_beta.pre_v26.py'
    if backup.exists() and backup.read_bytes() != original:
        raise RuntimeError('STOP: A different backup already exists; no files changed.')
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(fixture, backup)
    fixture.write_bytes(changed.encode('utf-8'))
    return 'Fixed tests/test_hosted_beta.py (v2.5 -> v2.6 assets). Backup saved inside .git.'


if __name__ == '__main__':
    try:
        print(apply())
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    print('Next: python -m pytest -q tests')
    print('No app code, secrets, dependencies, deployment or model settings changed.')
