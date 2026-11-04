"""Build and smoke-test a portable Windows package; never publish it."""
from pathlib import Path
import hashlib
import importlib.metadata
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'win32':
        raise SystemExit('Windows is required to build the Windows executable.')
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', version):
        raise SystemExit('Invalid VERSION')
    subprocess.run([sys.executable, '-m', 'PyInstaller', str(ROOT / 'FileAtlas.spec'), '--noconfirm'], cwd=ROOT, check=True)
    exe = ROOT / 'dist' / 'FileAtlas' / 'FileAtlas.exe'
    with tempfile.TemporaryDirectory(prefix='fileatlas-smoke-') as directory:
        subprocess.run([str(exe), '--data-dir', directory, '--smoke'], check=True, timeout=45)
        if not (Path(directory) / 'preview.png').is_file():
            raise RuntimeError('EXE did not produce the smoke-test screenshot')
    out = ROOT / 'release'
    out.mkdir(exist_ok=True)
    name = f'FileAtlas-{version}-win64'
    archive = out / (name + '.zip')
    with tempfile.TemporaryDirectory(prefix='stage-', dir=out) as staging:
        stage = Path(staging).resolve()
        assert stage.is_relative_to(out.resolve())
        package = stage / name
        shutil.copytree(exe.parent, package)
        for file in ('README.md', 'README.en.md', 'LICENSE', 'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md'):
            shutil.copy2(ROOT / file, package / file)
        shutil.copytree(ROOT / 'docs', package / 'docs')
        shutil.copytree(ROOT / 'assets', package / 'assets')
        for distribution in ('PySide6-Essentials', 'shiboken6', 'watchdog', 'pypdf', 'python-docx', 'lxml', 'PyInstaller'):
            dist = importlib.metadata.distribution(distribution)
            for item in dist.files or []:
                if ('licenses' in item.parts or item.name in ('METADATA', 'COPYING', 'LICENSE', 'LICENSE.txt', 'LICENSE.md')
                        or item.name.lower().startswith(('license', 'copying', 'notice'))):
                    source = Path(dist.locate_file(item))
                    if source.is_file():
                        target = package / 'licenses' / distribution / Path(*item.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
        python_license = Path(sys.base_prefix) / 'LICENSE.txt'
        if python_license.is_file():
            shutil.copy2(python_license, package / 'licenses' / 'Python-LICENSE.txt')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for file in sorted(package.rglob('*')):
                if file.is_file():
                    z.write(file, Path(name) / file.relative_to(package))
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (out / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'Built and verified: {archive}')


if __name__ == '__main__':
    main()
