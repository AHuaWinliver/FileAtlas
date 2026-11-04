import json
from pathlib import Path
import tempfile
import unittest
from core import Store, Engine, validate_decision


class FakeClassifier:
    def __init__(self, cid, confidence=.97):
        self.cid, self.confidence = cid, confidence
        self.calls = 0

    def classify(self, path):
        self.calls += 1
        return dict(category_id=self.cid, tags=['工程', '设计'], confidence=self.confidence, reason='测试依据')


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / '收件箱'
        self.source.mkdir()
        self.store = Store(self.root / 'state')
        self.store.set_sources([str(self.source)])
        self.cid = self.store.save_category('工程', str(self.root / '归档'), '工程文档')
        self.fake = FakeClassifier(self.cid)
        self.engine = Engine(self.store, self.fake)
        self.file = self.source / '测试.txt'
        self.file.write_text('设计方案与工程记录', encoding='utf-8')

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def analyze(self):
        self.engine.process(self.file)
        return self.store.rows('SELECT * FROM files')[0]

    def test_review_dedup_and_tags(self):
        f = self.analyze()
        self.engine.process(self.file)
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(f['status'], 'review')
        self.assertEqual(json.loads(f['tags']), ['工程', '设计'])

    def test_collision_copy_and_undo(self):
        root = self.root / '归档'
        root.mkdir()
        existing = root / self.file.name
        existing.write_text('原有文件', encoding='utf-8')
        f = self.analyze()
        dst = self.engine.apply(f['id'])
        self.assertEqual(existing.read_text(encoding='utf-8'), '原有文件')
        self.assertNotEqual(existing, dst)
        self.assertTrue(self.file.exists())
        self.assertEqual(dst.read_bytes(), self.file.read_bytes())
        op = self.store.rows("SELECT * FROM operations WHERE status='done'")[0]
        self.engine.undo(op['id'])
        self.assertFalse(dst.exists())
        self.assertTrue(self.file.exists())
        self.engine.process(self.file)
        self.assertEqual(self.fake.calls, 1)  # undo does not start an endless loop

    def test_move_and_restore(self):
        self.store.set('mode', 'move')
        self.store.set('auto_apply', True)
        self.analyze()
        self.assertFalse(self.file.exists())
        op = self.store.rows('SELECT * FROM operations')[0]
        self.engine.undo(op['id'])
        self.assertTrue(self.file.exists())
        self.assertFalse(Path(op['destination']).exists())

    def test_low_confidence_never_auto_moves(self):
        self.fake.confidence = .4
        self.store.set('auto_apply', True)
        self.assertEqual(self.analyze()['status'], 'review')
        self.assertEqual(self.store.rows('SELECT * FROM operations'), [])

    def test_changed_source_blocked(self):
        f = self.analyze()
        self.file.write_text('changed contents', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.engine.apply(f['id'])
        self.assertTrue(self.file.exists())

    def test_modified_destination_undo_blocked(self):
        dst = self.engine.apply(self.analyze()['id'])
        dst.write_text('user edited', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.engine.undo(self.store.rows('SELECT * FROM operations')[0]['id'])
        self.assertTrue(dst.exists())

    def test_copy_source_missing_undo_blocked(self):
        dst = self.engine.apply(self.analyze()['id'])
        self.file.unlink()
        with self.assertRaises(ValueError):
            self.engine.undo(self.store.rows('SELECT * FROM operations')[0]['id'])
        self.assertTrue(dst.exists())

    def test_nested_classification_and_tree(self):
        child = self.store.save_category('设计', str(self.root / '设计目录'), parent=self.cid)
        self.assertEqual(self.store.category_name(child), '工程 / 设计')
        with self.assertRaises(ValueError):
            self.store.save_category('工程', str(self.root / '归档'), parent=child, cid=self.cid)
        self.engine.apply(self.analyze()['id'])
        self.assertIn('测试.txt', self.store.export_tree().read_text(encoding='utf-8'))

    def test_destination_in_source_excluded(self):
        cid = self.store.save_category('内嵌', str(self.source / '已整理'))
        folder = self.source / '已整理'
        folder.mkdir()
        p = folder / 'x.txt'
        p.write_text('x')
        self.assertFalse(self.engine.eligible(p))
        with self.assertRaises(ValueError):
            self.store.set_sources([str(folder)])

    def test_untrusted_decision_rejected(self):
        for raw in [dict(category_id='../escape', confidence=.9), dict(category_id=self.cid, confidence=float('nan')), dict(category_id=self.cid, confidence=True), dict(category_id=self.cid, confidence=.9, tags='bad')]:
            with self.assertRaises(ValueError):
                validate_decision(raw, self.store.categories())

    def test_partial_download_excluded(self):
        p = self.source / 'video.crdownload'
        p.write_text('x')
        self.assertFalse(self.engine.eligible(p))

    def test_import_and_reconcile_existing_tree(self):
        root = self.root / '现有分类'
        child = root / '子分类'
        child.mkdir(parents=True)
        p = child / 'existing.txt'
        p.write_text('existing', encoding='utf-8')
        self.engine.import_tree(root)
        f = self.store.rows("SELECT * FROM files WHERE status='indexed'")[0]
        self.assertEqual(Path(f['path']), p)
        self.assertIn('子分类', self.store.category_name(f['category']))
        self.assertEqual(self.fake.calls, 0)
        p.unlink()
        self.engine.index_archives()
        self.assertEqual(self.store.rows('SELECT status FROM files WHERE id=?', (f['id'],))[0]['status'], 'missing')
        p.write_text('restored', encoding='utf-8')
        self.engine.index_archives()
        self.assertEqual(self.store.rows('SELECT status FROM files WHERE id=?', (f['id'],))[0]['status'], 'indexed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
