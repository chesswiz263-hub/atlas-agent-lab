"""Guarded v2.6.3 retrieval patch. No API/network/deploy/credential side effects."""
from pathlib import Path
from hashlib import sha256
import shutil

ROOT=Path(__file__).resolve().parent
FILES={
    'atlas_retrieval_v26.py':(
        '2a64a1f958982404cddc500de103aa0b66603f6d51a96a063d45e7a8650121f9',
        'fa680945c645556e486374bcfd8628e4221f81582a2aaa3d66c12dd6eb3eeecc'),
    'atlas_conversation_v26.py':(
        '2dd099aa4ed91dce58313e3d7288681281ab8ab19c966fa8283c00a8d0d2afab',
        'b1b5cb9639850feccba3d6a55ca4edf4d62ea41d6a4960067bae53e4e07079de'),
    'v26_tests/test_atlas_v262_cmb_precision.py':(
        '424a3fdfa435bd2998d8cd86f9c32d4dd4cb33e311f505968ecb6fbc9591565d',
        '87501d1a958a4fee0a6027f03d2f47c440521937a28c4fee46e211a8031f96e5'),
    'v26_tests/test_atlas_v263_curated_fulltext.py':(
        None,
        'ae077c6b7219106537551d9296428ec5f7e7525f5ad96c53855a1fb1fce0b044'),
}

def digest(path:Path)->str:
    return sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def main()->int:
    if not (ROOT/'.git').is_dir() or not (ROOT/'pyproject.toml').is_file():
        print('STOP: Extract ZIP into ATLAS repository root (containing .git and pyproject.toml).')
        return 2
    actions=[]
    for name,(before,after) in FILES.items():
        source=ROOT/'v263_patch'/name
        destination=ROOT/name
        backup=ROOT/'.git/atlas-v263-backups'/name
        if not source.is_file() or digest(source)!=after:
            print(f'STOP: Missing/altered patch file: {name}');return 2
        if destination.exists():
            observed=digest(destination)
            if observed not in ((before,after) if before else (after,)):
                print(f'STOP: Existing source differs from expected v2.6.2: {name}')
                return 2
        elif before is not None:
            print(f'STOP: Existing v2.6.2 file missing: {name}');return 2
        if backup.is_file() and before is not None and digest(backup)!=before:
            print(f'STOP: Existing backup differs from expected: {name}');return 2
        if not destination.exists() or digest(destination)!=after:
            actions.append((source,destination,backup,before))
    for source,destination,backup,before in actions:
        if before is not None and not backup.exists():
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(destination,backup)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        print('Updated',destination.relative_to(ROOT))
    if not actions:print('Already installed; no changes.')
    print('No model activation, API calls, credentials, gateway edits, commit, push, or deployment performed.')
    print('Next: python -m pytest -q v26_tests v25_tests')
    print('Then: python -m pytest -q tests')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
