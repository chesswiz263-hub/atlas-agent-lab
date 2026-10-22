"""Fix ATLAS v2.4 test's implicit Windows cp1252 source decoding.

This only changes two text reads in v24_tests/test_atlas_v24.py.
No runtime, gateway, authentication, mathematical or research files are edited.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'v24_tests' / 'test_atlas_v24.py'
REPLACEMENTS = (
    (b"(root/'atlas_hosted_beta_v24.reference.py').read_text()", b"(root/'atlas_hosted_beta_v24.reference.py').read_text(encoding='utf-8')"),
    (b"(root/'v24_assets/atlas-chat-v24.js').read_text()", b"(root/'v24_assets/atlas-chat-v24.js').read_text(encoding='utf-8')"),
)

def main():
    if not TARGET.is_file():
        print('ERROR: v24_tests/test_atlas_v24.py not found. Place this script in the repository root.')
        return 1
    original = TARGET.read_bytes()
    updated = original
    for old, new in REPLACEMENTS:
        if old in updated:
            if updated.count(old) != 1:
                print('ERROR: Unexpected duplicate test code; no changes made.')
                return 1
            updated = updated.replace(old, new)
        elif new not in updated:
            print('ERROR: Unexpected test content; no changes made. Please inspect v24_tests/test_atlas_v24.py.')
            return 1
    if updated == original:
        print('ATLAS v2.4 UTF-8 test fix is already installed. No files changed.')
    else:
        TARGET.write_bytes(updated)
        print('Fixed v24_tests/test_atlas_v24.py: two file reads now explicitly use UTF-8.')
    print('No ATLAS runtime or research files changed.')
    print('Next: python -m pytest -q tests v22_tests v22_hotfix_tests v23_tests v23_parser_hotfix_tests v24_tests')
    return 0

if __name__ == '__main__':
    sys.exit(main())
