import os
from enum import StrEnum
from functools import partial
from pathlib import Path
import threading
import time
from PySide6.QtCore import QThread, Signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bundles import FolderWriting, snapshot
from core import inside


class SortMode(StrEnum):
    STOPPED = 'stopped'
    MONITORING = 'monitoring'
    MANUAL = 'manual'
    MANUAL_DONE = 'manual_done'

    @property
    def active(self):
        return self in (SortMode.MONITORING, SortMode.MANUAL)


class Worker(QThread):
    changed = Signal()
    message = Signal(str)
    progress = Signal(str, int, int)
    sorting_progress = Signal(str, int, int)
    sorting_state_changed = Signal()

    ACTIONS = {
        'apply': ('正在整理所选文件', '所选文件已整理'),
        'undo': ('正在撤销所选操作', '所选操作已撤销'),
        'import_tree': ('正在导入现有目录', '目录导入完成'),
        'export_tree': ('正在更新文件目录', '文件目录已更新'),
        'setup_cae_workspace': ('正在创建 CAE 工作空间', 'CAE 工作空间已创建'),
        'create_cae_project': ('正在创建 CAE 项目', 'CAE 项目已创建'),
    }

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.wake = threading.Event()
        self.busy = False
        self.actions = []
        self.guard = threading.Lock()
        self.last_progress = ('', 0.0)
        self.sort_mode = SortMode.STOPPED
        self.sort_paused = False
        self.sort_generation = 0
        self.sort_in_flight = False
        self.scan_requested = False
        self.blocked_folders = {}

    def enqueue(self, action, *args):
        with self.guard:
            self.actions.append((action, args))
        self.wake.set()

    def request_scan(self):
        with self.guard:
            if self.sort_paused:
                return
            if not self.sort_mode.active:
                self.sort_mode = SortMode.MANUAL
            self.scan_requested = True
        self.sorting_state_changed.emit()
        self.wake.set()

    def sorting_status(self):
        with self.guard:
            return self.sort_mode, self.sort_paused, self.sort_in_flight

    def start_sorting(self, *, continuous=False):
        with self.guard:
            if continuous or not self.sort_paused:
                self.sort_mode = SortMode.MONITORING
            self.sort_paused = False
            self.scan_requested = True
        self.sorting_state_changed.emit()
        self.wake.set()

    def pause_sorting(self):
        with self.guard:
            if not self.sort_mode.active or self.sort_paused:
                return
            self.sort_paused = True
        self.sorting_state_changed.emit()
        self.wake.set()

    def stop_sorting(self):
        with self.guard:
            self.sort_mode = SortMode.STOPPED
            self.sort_paused = False
            self.sort_generation += 1
            self.scan_requested = False
        self.sorting_state_changed.emit()
        self.wake.set()

    def can_sort(self, generation, *, begin=False):
        with self.guard:
            allowed = (generation == self.sort_generation and self.sort_mode.active
                       and not self.sort_paused and not self.isInterruptionRequested())
            if allowed and begin:
                self.sort_in_flight = self.busy = True
            return allowed

    def finish_sort_work(self):
        with self.guard:
            self.sort_in_flight = self.busy = False
            state_changed = self.sort_paused or not self.sort_mode.active
        if state_changed:
            self.sorting_state_changed.emit()

    def has_pending_work(self):
        with self.guard:
            return self.busy or bool(self.actions)

    def paths(self, generation, report):
        store = self.engine.store
        context = self.engine.folder_context()
        sources, excluded, *_ = context
        folder_first = store.get('folder_first', True)
        visited = set()
        packages = set()
        for source in sources:
            for root, dirs, files in os.walk(source, followlinks=False):
                current = Path(root)
                if current in packages:
                    dirs.clear()
                    continue
                if folder_first and current not in sources:
                    if not self.can_sort(generation, begin=True):
                        return
                    try:
                        plan = self.engine.folder_decision(current, context, progress=report)
                    except OSError:
                        plan = None
                    finally:
                        self.finish_sort_work()
                    if plan:
                        try:
                            original = snapshot(current, source=True)
                            self.blocked_folders.pop(current, None)
                        except FolderWriting:
                            dirs.clear()
                            packages.add(current)
                            yield current, None, None
                            continue
                        except (OSError, ValueError) as exc:
                            dirs.clear()
                            packages.add(current)
                            if self.blocked_folders.get(current) != str(exc):
                                self.blocked_folders[current] = str(exc)
                                store.event('警告', f'{current.name} 整包保留原位：{exc}')
                                self.changed.emit()
                            continue
                        if not self.engine.folder_conflict(original, plan, context):
                            dirs.clear()
                            packages.add(current)
                            if original.files:
                                yield current, original.signature, (original, plan)
                            continue
                dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not any(inside(current / d, x) for x in excluded)
                                 and not (current / d).is_symlink() and not (hasattr(current / d, 'is_junction') and (current / d).is_junction()))
                for name in files:
                    p = current / name
                    if p not in visited and self.engine.eligible(p):
                        visited.add(p)
                        try:
                            info = p.stat()
                        except FileNotFoundError:
                            continue
                        yield p, f'{info.st_size}:{info.st_mtime_ns}', None

    def report_progress(self, message='', done=0, total=0, *, sorting=False):
        now = time.monotonic()
        stage = message.partition(' · ')[0]
        if 0 < done < total and stage == self.last_progress[0] and now - self.last_progress[1] < .08:
            return
        self.last_progress = stage, now
        self.progress.emit(message, done, total)
        if sorting:
            self.sorting_progress.emit(message, done, total)

    def run_action(self, action, args):
        start, finish = self.ACTIONS[action]
        try:
            self.report_progress(start)
            result = getattr(self.engine, action)(*args, progress=self.report_progress)
            if action == 'export_tree' and args:
                finish = '目录已导出 · ' + str(result)
            self.message.emit(finish)
        except Exception as exc:
            self.engine.store.event('错误', str(exc))
            self.message.emit(start.removeprefix('正在') + '失败 · ' + str(exc))
        finally:
            self.busy = False
            self.report_progress()
            self.changed.emit()

    def scan_sources(self, candidates, failures, generation, show_scan, report):
        started = time.monotonic()
        reported_scan = show_scan
        if reported_scan:
            report('正在扫描源文件夹')
        present, ready = set(), []
        pending = completed = errors = 0
        try:
            for p, signature, bundle in self.paths(generation, report):
                if not self.can_sort(generation):
                    return False
                if not reported_scan and time.monotonic() - started >= .25:
                    report('正在扫描源文件夹')
                    reported_scan = True
                present.add(p)
                if signature is None:
                    candidates.pop(p, None)
                    pending += 1
                    continue
                old = candidates.get(p)
                now = time.monotonic()
                if self.engine.store.rows('SELECT id FROM files WHERE source=? AND signature=?', (str(p.resolve()), signature)):
                    continue
                if not old or old[0] != signature:
                    candidates[p] = (signature, now)
                    pending += 1
                elif now - old[1] < 3:
                    pending += 1
                elif now >= failures.get(p, 0):
                    ready.append((p, signature, bundle))

            total = len(ready)
            for p, signature, bundle in ready:
                if not self.can_sort(generation):
                    break
                try:
                    if bundle:
                        latest = snapshot(p, source=True).signature
                    else:
                        info = p.stat()
                        latest = f'{info.st_size}:{info.st_mtime_ns}'
                except FolderWriting:
                    candidates.pop(p, None)
                    pending += 1
                    continue
                except FileNotFoundError:
                    continue
                if latest != signature:
                    candidates[p] = (latest, time.monotonic())
                    pending += 1
                    continue
                if not self.can_sort(generation, begin=True):
                    break
                stage = ''

                def file_progress(message, done=0, count=0):
                    nonlocal stage
                    phase = message.partition(' · ')[0] if count else message
                    if phase == stage:
                        return
                    stage = phase
                    report(f'{phase} · {p.name}', completed, total)

                try:
                    if bundle:
                        file_progress('正在整理整个文件夹')
                        self.engine.process_folder(p, *bundle, progress=file_progress)
                    else:
                        file_progress('正在分析文件')
                        self.engine.process(p, progress=file_progress)
                except Exception as exc:
                    errors += 1
                    failures[p] = time.monotonic() + 60
                    self.engine.store.event('错误', p.name + '：' + str(exc))
                finally:
                    completed += 1
                    report(f'已处理 {completed} 项', completed, total)
                    self.finish_sort_work()
            for p in candidates.keys() - present:
                del candidates[p]
        except Exception as exc:
            self.engine.store.event('错误', '扫描失败：' + str(exc))
            self.message.emit('扫描失败 · ' + str(exc))
            self.changed.emit()
            return False
        finally:
            if completed:
                self.changed.emit()
        if completed:
            summary = f'本轮已处理 {completed} 项'
            if errors:
                summary += f' · {errors} 个失败，见整理记录'
            if completed == total and not pending:
                report(summary, completed, total)
            self.message.emit(summary)
        elif show_scan and not pending and self.can_sort(generation):
            self.message.emit('扫描完成 · 没有新的整理项')
        if pending and self.can_sort(generation):
            report(f'等待 {pending} 项写入稳定')
            return True
        return False

    def run(self):
        worker = self
        class Events(FileSystemEventHandler):
            def on_any_event(self, event):
                worker.wake.set()
        report_sorting = partial(self.report_progress, sorting=True)
        observer, watched = None, None
        candidates, failures = {}, {}
        last_scan, manual_until, last_index = 0, 0, 0
        initial_scan = False
        was_sorting = False
        previous_generation = -1
        while not self.isInterruptionRequested():
            with self.guard:
                mode, paused, generation = self.sort_mode, self.sort_paused, self.sort_generation
                requested = self.scan_requested
                self.scan_requested = False
            if previous_generation != generation:
                candidates.clear()
                failures.clear()
                last_scan = manual_until = 0
                previous_generation = generation
            sorting = not paused and mode.active
            if was_sorting and not sorting:
                report_sorting()
            was_sorting = sorting
            monitoring = mode == SortMode.MONITORING and not paused
            sources = tuple(self.engine.store.get('sources', [])) if monitoring else ()
            if watched != sources:
                if observer:
                    observer.stop()
                    if observer.is_alive():
                        observer.join()
                observer = Observer()
                for src in sources:
                    if not Path(src).is_dir():
                        self.engine.store.event('错误', '整理源无法访问：' + src)
                        self.changed.emit()
                        continue
                    try:
                        observer.schedule(Events(), src, recursive=True)
                    except OSError as exc:
                        self.engine.store.event('错误', '监控失败：' + str(exc))
                if sources:
                    try:
                        observer.start()
                    except OSError as exc:
                        observer.stop()
                        self.engine.store.event('错误', '目录事件监控启动失败，继续定时扫描：' + str(exc))
                        self.changed.emit()
                watched = sources
                last_scan = 0
                initial_scan = bool(sources)
            with self.guard:
                action = self.actions.pop(0) if self.actions else None
                if action:
                    self.busy = True
            if action:
                self.run_action(*action)
            if requested:
                if mode == SortMode.MANUAL:
                    manual_until = float('inf')
                last_scan = 0
            now = time.monotonic()
            if monitoring and now - last_index > 30 and self.can_sort(generation, begin=True):
                last_index = now
                try:
                    self.sorting_progress.emit('正在索引归档文件', 0, 0)
                    self.engine.index_archives(progress=self.report_progress)
                    self.changed.emit()
                except Exception as exc:
                    self.engine.store.event('错误', '目录索引：' + str(exc))
                    self.message.emit('目录索引失败 · ' + str(exc))
                    self.changed.emit()
                finally:
                    self.finish_sort_work()
                    report_sorting()
            if sorting and now - last_scan >= 2 and self.can_sort(generation):
                last_scan = now
                waiting = self.scan_sources(candidates, failures, generation, initial_scan or requested or mode == SortMode.MANUAL,
                                            report_sorting)
                initial_scan = False
                if mode == SortMode.MANUAL:
                    if manual_until == float('inf'):
                        manual_until = time.monotonic() + 10
                    if (not waiting or time.monotonic() >= manual_until) and self.finish_manual_scan(generation):
                        if waiting:
                            self.message.emit('本次扫描结束 · 仍有文件正在写入')
                        manual_until = 0
                        waiting = False
                if not waiting:
                    report_sorting()
            self.wake.wait(1)
            self.wake.clear()
        if observer:
            observer.stop()
            if observer.is_alive():
                observer.join()

    def finish_manual_scan(self, generation):
        with self.guard:
            if (generation != self.sort_generation or self.sort_mode != SortMode.MANUAL
                    or self.sort_paused or self.scan_requested):
                return False
            self.sort_mode = SortMode.MANUAL_DONE
        self.sorting_state_changed.emit()
        return True
