"""ATLAS v2.6.2: guarded, local-only CMB evidence precision patch.

Requires installed v2.6.1. Does not enable paid calls, deploy or modify gateway.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import shutil
ROOT=Path(__file__).resolve().parent
OLD='e74de7f8abc27d759b5c6cdfae30b7bb1c1adfe4e8252a202cebd1d5f074061b'
NEW='2a64a1f958982404cddc500de103aa0b66603f6d51a96a063d45e7a8650121f9'
TEST='424a3fdfa435bd2998d8cd86f9c32d4dd4cb33e311f505968ecb6fbc9591565d'

def digest(path):return sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def main():
    if not (ROOT/'.git').is_dir() or not (ROOT/'pyproject.toml').is_file():
        print('STOP: Extract this ZIP into the ATLAS Git repository root.');return 2
    src=ROOT/'v262_patch/atlas_retrieval_v26.py'
    dst=ROOT/'atlas_retrieval_v26.py'
    test_src=ROOT/'v262_patch/v26_tests/test_atlas_v262_cmb_precision.py'
    test_dst=ROOT/'v26_tests/test_atlas_v262_cmb_precision.py'
    if not all(p.is_file() for p in (src,dst,test_src)) or digest(src)!=NEW or digest(test_src)!=TEST:
        print('STOP: patch files are incomplete or altered.');return 2
    if digest(dst) not in (OLD,NEW):
        print('STOP: unrecognized ATLAS retrieval source; install v2.6.1 first, or review custom changes manually.');return 2
    if test_dst.exists() and digest(test_dst)!=TEST:
        print('STOP: existing v2.6.2 test differs; no files changed.');return 2
    backup=ROOT/'.git/atlas-v262-backups/atlas_retrieval_v26.py'
    if backup.exists() and digest(backup)!=OLD:
        print('STOP: backup differs; no files changed.');return 2
    if digest(dst)==OLD:
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():shutil.copy2(dst,backup)
        shutil.copy2(src,dst)
        print('Updated atlas_retrieval_v26.py')
    else:print('Retrieval patch already installed.')
    if not test_dst.exists():
        test_dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(test_src,test_dst)
        print('Added offline CMB precision tests.')
    print('No credentials, paid calls, gateway edits, commits, pushes, or deployment.')
    print('Next: python -m pytest -q v26_tests v25_tests')
    return 0
if __name__=='__main__':raise SystemExit(main())
