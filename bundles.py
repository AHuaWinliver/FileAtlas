"""Filesystem snapshots and verified transfers for intact folder archives."""
from dataclasses import dataclass
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile


TEMP_SUFFIXES = {'.tmp', '.part', '.crdownload', '.download'}


class FolderWriting(ValueError):
    pass


def is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def path_exists(path):
    return os.path.lexists(path)


def shallow_names(folder, limit=32):
    """Give each direct branch a small sample and refuse very broad AI candidates."""
    top = sorted(islice(folder.iterdir(), limit + 1), key=lambda p: p.name.casefold())
    if len(top) > limit:
        return (), False
    names = []
    for child in top:
        info = child.lstat()
        if is_link(info):
            return (), False
        if stat.S_ISDIR(info.st_mode):
            names.append(child.name + '/')
            nested = sorted(islice(child.iterdir(), 7), key=lambda p: p.name.casefold())
            names.extend(f'{child.name}/{p.name}' for p in nested[:6])
            if len(nested) > 6:
                names.append(f'{child.name}/…')
        else:
            names.append(child.name)
    return tuple(names), True


@dataclass(frozen=True)
class FolderSnapshot:
    directories: tuple[str, ...]
    files: tuple[tuple[str, int, int], ...]

    @property
    def signature(self):
        return 'folder:' + self._hash((self.directories, self.files))

    @staticmethod
    def _hash(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()

    def digest(self, root):
        hashes = []
        for name, _, _ in self.files:
            path = root / name
            if is_link(path.lstat()) or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('文件夹内的链接无法校验：' + str(path))
            with path.open('rb') as stream:
                hashes.append((name, hashlib.file_digest(stream, 'sha256').hexdigest()))
        return self._hash((self.directories, hashes))


def snapshot(folder, *, source=False):
    info = folder.lstat()
    if is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError('只支持普通文件夹，链接和联接点保留原位')
    dirs, files, pending = [], [], [folder]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(folder).as_posix()
                info = entry.stat(follow_symlinks=False)
                if is_link(info):
                    raise ValueError('整包中存在链接或联接点：' + relative)
                if stat.S_ISDIR(info.st_mode):
                    dirs.append(relative)
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    if source and (entry.name.startswith('~$') or path.suffix.casefold() in TEMP_SUFFIXES):
                        raise FolderWriting('整包中有临时文件：' + relative)
                    files.append((relative, info.st_size, info.st_mtime_ns))
                else:
                    raise ValueError('整包中存在特殊文件：' + relative)
    return FolderSnapshot(tuple(sorted(dirs)), tuple(sorted(files)))


def verified_copy(src, dest, original, digest, progress):
    """Publish a verified directory from a temporary sibling on the target volume."""
    with tempfile.TemporaryDirectory(prefix='.fileatlas-', dir=dest.parent) as staging:
        package = Path(staging) / 'payload'
        package.mkdir()
        for name in original.directories:
            (package / name).mkdir()
        progress('正在复制整个文件夹')
        for name, _, _ in original.files:
            source = src / name
            if is_link(source.lstat()) or not source.resolve().is_relative_to(src.resolve()):
                raise ValueError('复制期间发现链接：' + str(source))
            target = package / name
            with source.open('rb') as inp, target.open('xb') as out:
                shutil.copyfileobj(inp, out, 1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
            shutil.copystat(source, target, follow_symlinks=False)
        progress('正在校验整包及子目录结构')
        if snapshot(package).digest(package) != digest or snapshot(src) != original or original.digest(src) != digest:
            raise ValueError('整包校验失败或源目录发生变化，源目录已保留')
        if path_exists(dest):
            raise FileExistsError('目标目录已被占用：' + str(dest))
        package.rename(dest)


def detach_verified(root, digest):
    """Take a verified directory out of view before deleting it."""
    holding = Path(tempfile.mkdtemp(prefix='.fileatlas-', dir=root.parent))
    payload = holding / 'payload'
    try:
        root.rename(payload)
        expected = snapshot(payload)
        if expected.digest(payload) != digest or snapshot(payload) != expected:
            raise ValueError('文件夹内容或层级已变化')
    except Exception as exc:
        if path_exists(payload):
            try:
                restore_detached((holding, None), root)
            except RuntimeError as restore_error:
                raise restore_error from exc
        else:
            holding.rmdir()
        raise
    return holding, expected


def restore_detached(detached, root):
    holding, _ = detached
    payload = holding / 'payload'
    try:
        if path_exists(root):
            raise FileExistsError(str(root))
        payload.rename(root)
    except OSError as exc:
        raise RuntimeError(f'原目录保留在 {payload}，请手动恢复：{exc}') from exc
    holding.rmdir()


def remove_detached(detached):
    holding, expected = detached
    payload = holding / 'payload'
    try:
        if snapshot(payload) != expected:
            raise ValueError('隔离目录中出现了新内容')
        for name, size, mtime in expected.files:
            path = payload / name
            info = path.lstat()
            if is_link(info) or info.st_size != size or info.st_mtime_ns != mtime:
                raise ValueError('隔离目录中的文件发生变化：' + name)
            path.unlink()
        for name in reversed(expected.directories):
            (payload / name).rmdir()
        payload.rmdir()
        holding.rmdir()
    except (OSError, ValueError) as exc:
        return f'已完成归档操作，临时副本需手动清理：{holding}（{exc}）'
    return ''
