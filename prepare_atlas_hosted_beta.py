"""Copy v2.0 browser assets into static/, preserving unrelated ATLAS files."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'atlas_hosted_beta_assets'
TARGET = ROOT / 'static'


def main():
    if not (ROOT / 'pyproject.toml').is_file() or not (ROOT / 'src' / 'atlas').is_dir():
        raise SystemExit('Run from ATLAS repo root containing pyproject.toml and src/atlas')
    TARGET.mkdir(exist_ok=True)
    for src, dest in [('index.html', 'atlas-chat.html'), ('atlas-chat.js', 'atlas-chat.js'), ('atlas-chat.css', 'atlas-chat.css')]:
        origin = SOURCE / src
        target = TARGET / dest
        if not origin.is_file():
            raise SystemExit(f'Missing {origin}')
        if target.is_file():
            print('Preserving existing', target)
            continue
        shutil.copy2(origin, target)
        print('Created', target)
    print('Ready: static/atlas-chat.html. No GitHub changes were pushed.')


if __name__ == '__main__':
    main()
