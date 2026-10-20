"""ATLAS v2.2 math natural-language parser hotfix (offline, idempotent).

Only updates atlas_math_v22.py if it exactly matches the verified v2.2
release or the already-installed hotfix. Never touches hosted gateway,
credentials, Pages, Render settings, or any science research modules.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
ORIGINAL_SHA256 = '057a7206ab2c74663e98c33f7fbf0b3150e4a1829c8d756f137d40ee5434ce1c'
PATCHED_SHA256 = '067728279dc569c1a895aa5bc44a77418176f56ca813c35c1c9b08e5cf519352'


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    current = ROOT / 'atlas_math_v22.py'
    conversation = ROOT / 'atlas_conversation_v22.py'
    replacement = ROOT / 'atlas_hotfix_assets' / 'atlas_math_v22.py'
    if not current.is_file() or not conversation.is_file():
        raise SystemExit('Run from the ATLAS v2.2 repository root, which must contain atlas_math_v22.py and atlas_conversation_v22.py')
    if not replacement.is_file() or digest(replacement) != PATCHED_SHA256:
        raise SystemExit('Hotfix source is missing or modified; nothing was changed')
    status = digest(current)
    if status == PATCHED_SHA256:
        print('Math language hotfix already installed (no changes).')
    elif status == ORIGINAL_SHA256:
        backups = ROOT / '.git' / 'atlas-hotfix-backups' if (ROOT / '.git').is_dir() else ROOT
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / ('atlas_math_v22.original.backup' if backups != ROOT else 'atlas_math_v22.original.backup')
        if backup.exists() and digest(backup) != ORIGINAL_SHA256:
            raise SystemExit('Existing backup differs from v2.2 original; nothing was changed')
        if not backup.exists():
            shutil.copy2(current,backup)
        shutil.copy2(replacement,current)
        print('Applied safe math-language hotfix to atlas_math_v22.py.')
        print('Original backed up at:',backup)
    else:
        raise SystemExit('atlas_math_v22.py is customized or not the verified v2.2 version. Refusing overwrite; merge changes manually.')
    regression_source = ROOT / 'v22_hotfix_tests' / 'test_math_language_hotfix.py'
    if not regression_source.is_file():
        raise SystemExit('Missing hotfix regression tests; install was completed but tests are unavailable')
    print('Next: python -m pytest -q tests v22_tests v22_hotfix_tests')
    print('Review git diff, then commit and push only after all tests pass.')


if __name__ == '__main__':
    main()
