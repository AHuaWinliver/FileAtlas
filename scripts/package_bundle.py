"""Bundle tracked source, installer, portable app, guides, and checksums."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    out = ROOT / 'release'
    required = [out / f'FileAtlas-{version}-Setup.exe', out / f'FileAtlas-{version}-win64.zip']
    if not all(p.is_file() for p in required):
        raise FileNotFoundError('Build the portable package and installer first.')
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    source = out / f'FileAtlas-{version}-source.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in filter(None, files):
            archive.write(ROOT / name, Path('FileAtlas') / name)
    bundle = out / f'FileAtlas-{version}-complete.zip'
    with tempfile.TemporaryDirectory(prefix='fileatlas-bundle-') as directory:
        folder = Path(directory) / f'FileAtlas-{version}'
        folder.mkdir()
        for p in [*required, source]:
            shutil.copy2(p, folder / p.name)
        shutil.copytree(ROOT / 'docs', folder / '使用说明')
        for name in ('README.md', 'README.en.md', 'LICENSE', 'CHANGELOG.md'):
            shutil.copy2(ROOT / name, folder / name)
        (folder / '先读我.txt').write_text(
            f'FileAtlas {version} 完整交付包\n\n'
            '1. 安装使用：运行 Setup.exe；也可解压 win64.zip 免安装使用。\n'
            '2. 工程模板：分类与目录 → 创建 CAE 工作空间 → 新建工程项目。\n'
            '3. 使用说明：双击 使用说明/QUICK_START.html；工程规则见 CAE_WORKFLOW.md。\n'
            '4. 源码：解压 source.zip，安装 requirements-dev.txt 后运行 app.py。\n'
            '5. AI 分类需自行安装并配置 Claude Code；数据保存在 %LOCALAPPDATA%\\FileAtlas。\n'
            '6. 安装程序已编译；未在此电脑执行真实安装/卸载，以免影响现有环境。\n'
            '7. SHA256SUMS.txt 用于校验文件完整性。\n', encoding='utf-8')
        checks = []
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                with p.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                checks.append(digest + '  ' + p.relative_to(folder).as_posix())
        (folder / 'SHA256SUMS.txt').write_text('\n'.join(checks) + '\n', encoding='utf-8')
        with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for p in sorted(folder.rglob('*')):
                if p.is_file():
                    archive.write(p, Path(folder.name) / p.relative_to(folder))
    with zipfile.ZipFile(bundle) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Bundle integrity check failed')
    print('Complete bundle:', bundle)


if __name__ == '__main__':
    main()
