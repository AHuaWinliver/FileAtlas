"""Compile a per-user Windows installer from the verified portable package."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc', help='Path to an installed Inno Setup 6/7 compiler')
    args = parser.parse_args()
    candidates = [args.iscc, shutil.which('ISCC.exe')]
    for base in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        for version in ('Inno Setup 7', 'Inno Setup 6'):
            candidates.append(str(Path(os.environ.get(base, '')) / version / 'ISCC.exe'))
            candidates.append(str(Path(os.environ.get(base, '')) / 'Programs' / version / 'ISCC.exe'))
    compiler = next((Path(p).resolve() for p in candidates if p and Path(p).is_file()), None)
    if not compiler:
        parser.error('Install Inno Setup, or pass --iscc with the compiler path.')
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not __import__('re').fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid release version')
    release = ROOT / 'release'
    portable = release / f'FileAtlas-{version}-win64.zip'
    if not portable.is_file():
        raise FileNotFoundError('Run scripts/build.py first.')
    with tempfile.TemporaryDirectory(prefix='fileatlas-installer-') as directory:
        stage = Path(directory).resolve()
        with zipfile.ZipFile(portable) as archive:
            for name in archive.namelist():
                if not (stage / name).resolve().is_relative_to(stage):
                    raise ValueError('Unsafe archive path')
            archive.extractall(stage)
        package = stage / f'FileAtlas-{version}-win64'
        subprocess.run([str(compiler), f'/DAppVersion={version}', f'/DPackageRoot={package}',
                        f'/DOutputRoot={release}', str(ROOT / 'installer' / 'FileAtlas.iss')], check=True)
    output = release / f'FileAtlas-{version}-Setup.exe'
    if output.read_bytes()[:2] != b'MZ':
        raise RuntimeError('Invalid installer output')
    print('Installer compiled:', output)


if __name__ == '__main__':
    main()
