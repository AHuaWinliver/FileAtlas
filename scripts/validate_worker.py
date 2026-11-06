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
cid = store.save_category('验证', str(root / 'archive'), '文件夹规则：整包测试')
store.set('auto_apply', True)
store.set('mode', 'move')
classifier = Classifier(cid)
worker = Worker(Engine(store, classifier))
(src / '新文件.txt').write_text('监控启动前已存在', encoding='utf-8')
bundle = src / '整包测试'
(bundle / '子目录').mkdir(parents=True)
(bundle / '子目录' / '配套文件.txt').write_text('内部文件不会单独分类', encoding='utf-8')
worker.start()

def start_monitoring():
    worker.start_sorting()

QTimer.singleShot(500, start_monitoring)
QTimer.singleShot(8500, lambda: (src / '新文件.txt').write_text('内容2 changed', encoding='utf-8'))
def finish():
    worker.stop_sorting()
    worker.requestInterruption()
    worker.wake.set()
    if not worker.wait(5000):
        print('Worker did not stop in time.', file=sys.stderr)
        os._exit(1)
    code = 0
    try:
        rows = store.rows("SELECT * FROM operations WHERE status='done'")
        assert len(rows) == 3, rows
        assert classifier.calls == 2, classifier.calls
        assert all(Path(r['destination']).exists() for r in rows)
        assert len(set(r['destination'] for r in rows)) == 3
        assert (root / 'archive' / '整包测试' / '子目录' / '配套文件.txt').is_file()
        assert not bundle.exists()
        print(json.dumps({'idle_to_monitoring': 'PASS', 'existing_and_updated_file': 'PASS', 'collision': 'PASS',
                          'top_down_folder_bundle': 'PASS', 'operations': len(rows)}, indent=2))
    except Exception as exc:
        print(repr(exc), file=sys.stderr)
        code = 1
    finally:
        store.db.close()
        tmp.cleanup()
        app.exit(code)
QTimer.singleShot(18000, finish)
sys.exit(app.exec())
