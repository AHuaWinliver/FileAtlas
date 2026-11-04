import json
import os
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QTimer
from core import Store, Engine
from worker import Worker

class Classifier:
    def __init__(self, cid):
        self.cid = cid
        self.calls = 0
    def classify(self, path):
        self.calls += 1
        return dict(category_id=self.cid, confidence=.99, tags=['监控验证'], reason='集成测试')

app = QCoreApplication([])
tmp = tempfile.TemporaryDirectory()
root = Path(tmp.name)
src = root / '监控源'
src.mkdir()
store = Store(root / 'state')
store.set_sources([str(src)])
cid = store.save_category('验证', str(root / 'archive'))
store.set('auto_apply', True)
store.set('mode', 'move')
classifier = Classifier(cid)
worker = Worker(Engine(store, classifier))
worker.monitoring = True
worker.start()
QTimer.singleShot(500, lambda: (src / '新文件.txt').write_text('内容1', encoding='utf-8'))
QTimer.singleShot(8500, lambda: (src / '新文件.txt').write_text('内容2 changed', encoding='utf-8'))
def finish():
    worker.monitoring = False
    worker.requestInterruption()
    worker.wake.set()
    if not worker.wait(5000):
        print('Worker did not stop in time.', file=sys.stderr)
        os._exit(1)
    code = 0
    try:
        rows = store.rows("SELECT * FROM operations WHERE status='done'")
        assert len(rows) == 2, rows
        assert classifier.calls == 2, classifier.calls
        assert all(Path(r['destination']).exists() for r in rows)
        assert len(set(r['destination'] for r in rows)) == 2
        print(json.dumps({'watcher': 'PASS', 'new_and_updated_file': 'PASS', 'collision': 'PASS', 'operations': len(rows)}, indent=2))
    except Exception as exc:
        print(repr(exc), file=sys.stderr)
        code = 1
    finally:
        store.db.close()
        tmp.cleanup()
        app.exit(code)
QTimer.singleShot(18000, finish)
sys.exit(app.exec())
