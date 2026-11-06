import os
from pathlib import Path
import threading
import time
from PySide6.QtCore import QThread, Signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core import inside


class Worker(QThread):
    changed = Signal()
    message = Signal(str)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.monitoring = False
        self.scan = threading.Event()
        self.wake = threading.Event()
        self.busy = False
        self.actions = []
        self.guard = threading.Lock()

    def enqueue(self, action, *args):
        with self.guard:
            self.actions.append((action, args))
        self.wake.set()

    def request_scan(self):
        self.scan.set()
        self.wake.set()

    def paths(self):
        store = self.engine.store
        excluded = [store.home] + [Path(c['destination']) for c in store.categories()]
        visited = set()
        for source in store.get('sources', []):
            for root, dirs, files in os.walk(source, followlinks=False):
                dirs[:] = [d for d in dirs if not d.startswith('.') and not any(inside(Path(root) / d, x) for x in excluded)
                           and not (Path(root) / d).is_symlink() and not (hasattr(Path(root) / d, 'is_junction') and (Path(root) / d).is_junction())]
                for name in files:
                    p = Path(root) / name
                    if p not in visited and self.engine.eligible(p):
                        visited.add(p)
                        yield p

    def run(self):
        worker = self
        class Events(FileSystemEventHandler):
            def on_any_event(self, event):
                if worker.monitoring:
                    worker.wake.set()
        observer, watched = None, None
        candidates, failures = {}, {}
        last_scan, manual_until, last_index = 0, 0, 0
        while not self.isInterruptionRequested():
            sources = tuple(self.engine.store.get('sources', [])) if self.monitoring else ()
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
            with self.guard:
                action = self.actions.pop(0) if self.actions else None
            if action:
                self.busy = True
                try:
                    self.message.emit('正在执行文件操作…')
                    getattr(self.engine, action[0])(*action[1])
                except Exception as exc:
                    self.engine.store.event('错误', str(exc))
                    self.message.emit(str(exc))
                finally:
                    self.busy = False
                    self.changed.emit()
            if self.scan.is_set():
                self.scan.clear()
                manual_until = time.monotonic() + 10
                last_scan = 0
            now = time.monotonic()
            if self.monitoring and now - last_index > 30:
                last_index = now
                try:
                    self.engine.index_archives()
                    self.changed.emit()
                except Exception as exc:
                    self.engine.store.event('错误', '目录索引：' + str(exc))
            if (self.monitoring or now < manual_until) and (now - last_scan >= 2):
                last_scan = now
                monitoring_at_start = self.monitoring
                present = set()
                try:
                    for p in self.paths():
                        if self.isInterruptionRequested():
                            break
                        if monitoring_at_start and not self.monitoring:
                            break
                        present.add(p)
                        stat = p.stat()
                        sig = (stat.st_size, stat.st_mtime_ns)
                        old = candidates.get(p)
                        if not old or old[0] != sig:
                            candidates[p] = (sig, time.monotonic())
                            continue
                        if time.monotonic() - old[1] < 3 or time.monotonic() < failures.get(p, 0):
                            continue
                        signature = f'{stat.st_size}:{stat.st_mtime_ns}'
                        if self.engine.store.rows('SELECT id FROM files WHERE source=? AND signature=?', (str(p.resolve()), signature)):
                            continue
                        self.busy = True
                        try:
                            self.message.emit('正在分析：' + p.name)
                            self.engine.process(p)
                        except Exception as exc:
                            failures[p] = time.monotonic() + 60
                            self.engine.store.event('错误', p.name + '：' + str(exc))
                        finally:
                            self.busy = False
                            self.changed.emit()
                    candidates = {p: v for p, v in candidates.items() if p in present}
                except Exception as exc:
                    self.engine.store.event('错误', '扫描失败：' + str(exc))
                self.message.emit('监控中 · 文件稳定 3 秒后分析' if self.monitoring else '本次扫描完成')
            self.wake.wait(1)
            self.wake.clear()
        if observer:
            observer.stop()
            if observer.is_alive():
                observer.join()
