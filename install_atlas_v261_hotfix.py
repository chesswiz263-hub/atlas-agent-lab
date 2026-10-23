"""Guarded, offline ATLAS v2.6.1 repair. No network, keys, or gateway changes."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import shutil

ROOT = Path(__file__).resolve().parent
PATCH = ROOT / 'v261_patch'
FILES = {
    'atlas_retrieval_v26.py': (
        '7062ded73f28d794734f06b5fe6dad6a12f7bd3bed5828f49f855fc2c1e15290',
        'e74de7f8abc27d759b5c6cdfae30b7bb1c1adfe4e8252a202cebd1d5f074061b'),
    'atlas_conversation_v26.py': (
        '90b701b27df7a800210341baa406cd67891381ea4ab5f8cb8d9d999aeeec1f3c',
        '2dd099aa4ed91dce58313e3d7288681281ab8ab19c966fa8283c00a8d0d2afab'),
}
TEST = 'v26_tests/test_atlas_v26_live_regression.py'


def digest(path: Path) -> str:
    return sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main() -> int:
    if not (ROOT/'.git').is_dir() or not (ROOT/'pyproject.toml').is_file():
        print('STOP: Extract to an existing ATLAS Git repository root containing .git and pyproject.toml.');return 2
    # Check EVERYTHING before changing anything. Fail closed on local customizations.
    operations=[]
    for relative,(before,after) in FILES.items():
        dst=ROOT/relative; src=PATCH/relative
        if not dst.is_file() or not src.is_file() or digest(src)!=after or digest(dst) not in (before,after):
            print('STOP: unexpected or missing file:',relative,'; no changes made.');return 2
        if digest(dst)==before:operations.append((src,dst))
    test_src=PATCH/TEST;test_dst=ROOT/TEST
    if not test_src.is_file() or (test_dst.exists() and digest(test_src)!=digest(test_dst)):
        print('STOP: regression test differs or is missing; no changes made.');return 2
    backup_dir=ROOT/'.git'/'atlas-v261-backups'
    for _,dst in operations:
        backup=backup_dir/dst.name
        if backup.exists() and digest(backup)!=FILES[dst.name][0]:
            print('STOP: existing backup differs; no changes made.');return 2
    for src,dst in operations:
        backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/dst.name
        if not backup.exists():shutil.copy2(dst,backup)
        shutil.copy2(src,dst)
        print('Updated:',dst.name)
    if not test_dst.exists():
        test_dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(test_src,test_dst)
        print('Added regression test:',TEST)
    if not operations:print('The v2.6.1 source patch is already installed.')
    print('No gateway, mathematics, authentication, API keys, model settings, remote calls, or deployment changed.')
    print('Next: python -m pytest -q v26_tests v25_tests')
    return 0

if __name__=='__main__':raise SystemExit(main())
