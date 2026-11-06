from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from bundles import snapshot
from core import Engine, Store


class FolderBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.source = root / 'source'
        self.source.mkdir()
        self.archive = root / 'archive'
        self.store = Store(root / 'state')
        self.addCleanup(self.store.db.close)
        self.store.set_sources([str(self.source)])
        self.cid = self.store.save_category('工程交付', str(self.archive), '文件夹规则：齿轮箱交付')
        self.store.set('auto_apply', True)
        self.engine = Engine(self.store)
        self.package = self.source / '齿轮箱交付'
        (self.package / '01_模型' / '空目录').mkdir(parents=True)
        (self.package / '01_模型' / 'model.step').write_text('CAD')
        (self.package / '02_说明.md').write_text('report')

    def classify(self):
        context = self.engine.folder_context()
        decision = self.engine.folder_decision(self.package, context)
        self.assertIsNotNone(decision)
        self.engine.process_folder(self.package, snapshot(self.package, source=True), decision)
        return self.store.rows('SELECT * FROM files WHERE kind=?', ('folder',))[0]

    def test_copy_index_and_undo_as_one_item(self):
        item = self.classify()
        archived = Path(item['path'])
        self.assertTrue((archived / '01_模型' / '空目录').is_dir())
        self.assertEqual((archived / '01_模型' / 'model.step').read_text(), 'CAD')
        self.assertTrue(self.package.is_dir())
        self.engine.index_archives()
        self.assertEqual(len(self.store.rows('SELECT * FROM files')), 1)
        markdown = self.store.export_tree().read_text(encoding='utf-8')
        self.assertIn('齿轮箱交付（整包）', markdown)
        self.assertNotIn('model.step', markdown)
        self.engine.undo(self.store.rows('SELECT id FROM operations')[0]['id'])
        self.assertFalse(archived.exists())
        self.assertTrue(self.package.is_dir())

    def test_move_and_restore_all_children(self):
        self.store.set('mode', 'move')
        original = snapshot(self.package)
        digest = original.digest(self.package)
        item = self.classify()
        self.assertFalse(self.package.exists())
        operation = self.store.rows('SELECT * FROM operations')[0]
        self.assertEqual(operation['mode'], 'move')
        self.engine.undo(operation['id'])
        self.assertEqual(snapshot(self.package).digest(self.package), digest)
        self.assertFalse(Path(item['path']).exists())

    def test_undo_rejects_added_archive_content(self):
        item = self.classify()
        extra = Path(item['path']) / 'new.txt'
        extra.write_text('new')
        with self.assertRaises(ValueError):
            self.engine.undo(self.store.rows('SELECT id FROM operations')[0]['id'])
        self.assertTrue(extra.is_file())
        self.assertTrue(self.package.is_dir())

    def test_nested_explicit_boundaries_and_source_root(self):
        self.store.save_category('试验资料', str(self.archive.parent / 'tests'), '文件夹规则：独立试验')
        (self.package / '01_模型' / '独立试验').mkdir()
        context = self.engine.folder_context()
        self.assertFalse(self.engine.folder_allowed(self.source, context))
        decision = self.engine.folder_decision(self.package, context)
        self.assertTrue(self.engine.folder_conflict(snapshot(self.package), decision, context))

    def test_model_cache_and_move_requires_review(self):
        self.package = self.package.rename(self.source / '齿轮箱台架交付件')
        self.store.set('mode', 'move')
        cid = self.cid

        class Classifier:
            calls = 0

            def classify_folder(self, path, names, cats):
                self.calls += 1
                return dict(category_id=cid, confidence=.97, tags=['台架'], reason='同一试验交付件')

        classifier = Classifier()
        self.engine = Engine(self.store, classifier)
        item = self.classify()
        self.assertEqual(item['status'], 'review')
        self.assertTrue(self.package.is_dir())
        self.assertIn('移动前须确认', item['reason'])
        (self.package / '02_说明.md').write_text('changed contents only')
        self.assertTrue(self.engine.folder_decision(self.package, self.engine.folder_context()))
        self.assertEqual(classifier.calls, 1)

    def test_solver_case_is_preserved(self):
        self.store.set('cae_mode', True)
        (self.package / '01_模型' / '.fileatlas-case.json').write_text('{}')
        item = self.classify()
        self.assertEqual(item['status'], 'protected')
        self.assertTrue(self.package.is_dir())
        self.assertFalse(self.archive.exists())

    def test_existing_database_adds_default_kind(self):
        self.store.db.close()
        database = self.store.home / 'catalog.sqlite3'
        with closing(sqlite3.connect(database)) as db, db:
            db.execute('ALTER TABLE files DROP COLUMN kind')
            db.execute("INSERT INTO files VALUES('legacy','src','dst','sig',NULL,'[]',1,'','review','today')")
        migrated = Store(self.store.home)
        try:
            self.assertEqual(migrated.rows('SELECT kind FROM files WHERE id=?', ('legacy',)), [{'kind': 'file'}])
        finally:
            migrated.db.close()
