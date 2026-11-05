import json
from pathlib import Path
import tempfile
import unittest
from core import Store, Engine
from cae import allowed_category, project_plan


class Classifier:
    def __init__(self, cid):
        self.cid, self.calls = cid, 0
    def classify(self, path):
        self.calls += 1
        return dict(category_id=self.cid, tags=['报告'], confidence=.99, reason='工程报告')


class CAETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.store = Store(self.root / 'state')
        self.engine = Engine(self.store)
        self.workspace = self.root / 'CAE'
        self.engine.setup_cae_workspace(str(self.workspace))
        self.ids = self.engine.create_cae_project(str(self.workspace), 'P2026-001', '研发部', '齿轮箱', '齿轮、传动')
        self.cid = next(cid for path, cid in self.ids.items() if path.endswith('/报告草稿'))
        self.classifier = Classifier(self.cid)
        self.engine.classifier = self.classifier
        self.store.set('auto_apply', True)
        self.inbox = self.workspace / '00_待整理'

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def file(self, name):
        p = self.inbox / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('测试资料', encoding='utf-8')
        self.engine.process(p)
        return p, self.store.rows('SELECT * FROM files WHERE source=?', (str(p),))[0]

    def test_template_creates_source_project_and_case(self):
        self.assertIn(str(self.inbox), self.store.get('sources'))
        case = self.workspace / '01_项目库/P2026-001_研发部_齿轮箱/03_仿真任务/C001_基准工况/求解'
        self.assertTrue(case.is_dir())
        self.assertTrue(self.store.get('cae_mode'))
        self.assertFalse(self.store.get('mode', 'copy') == 'move')

    def test_explicit_project_can_auto_file(self):
        p, f = self.file('P2026-001_分析报告.txt')
        self.assertEqual(f['status'], 'done')
        self.assertTrue(p.exists())
        self.assertIn('P2026-001', json.loads(f['tags']))

    def test_unknown_project_requires_review_even_at_low_threshold(self):
        self.store.set('threshold', .5)
        _, f = self.file('分析报告.txt')
        self.assertEqual(f['status'], 'review')
        self.assertIn('必须人工审核', f['reason'])
        self.engine.apply(f['id'])  # explicit human selection is permitted

    def test_conflicting_project_requires_review(self):
        self.engine.create_cae_project(str(self.workspace), 'P2026-002', '研发部', '轴承')
        _, f = self.file('P2026-001_P2026-002_报告.txt')
        self.assertEqual(f['status'], 'review')

    def test_native_solver_file_never_calls_ai_or_moves(self):
        p, f = self.file('P2026-001_model.inp')
        self.assertEqual(f['status'], 'protected')
        self.assertEqual(self.classifier.calls, 0)
        self.assertTrue(p.exists())
        with self.assertRaises(ValueError):
            self.engine.apply(f['id'], self.cid)

    def test_case_companion_files_preserved(self):
        folder = self.inbox / '完整工况'
        folder.mkdir()
        (folder / 'model.inp').write_text('*HEADING', encoding='utf-8')
        p, f = self.file('完整工况/P2026-001_说明.txt')
        self.assertEqual(f['status'], 'protected')
        self.assertEqual(self.classifier.calls, 0)
        self.assertTrue(p.exists())

    def test_protected_destination_cannot_receive_loose_files(self):
        cid = next(cid for path, cid in self.ids.items() if path.endswith('/求解'))
        self.assertFalse(allowed_category(self.store, cid))
        _, f = self.file('说明.txt')
        with self.assertRaises(ValueError):
            self.engine.apply(f['id'], cid)

    def test_duplicates_and_invalid_names_do_not_add_categories(self):
        count = len(self.store.categories())
        with self.assertRaises(ValueError):
            self.engine.create_cae_project(str(self.workspace), 'P2026-001', '研发部', '重复')
        with self.assertRaises(ValueError):
            project_plan('P2026-003', '../逃逸', '非法路径')
        with self.assertRaises(ValueError):
            self.engine.setup_cae_workspace(str(self.workspace))
        self.assertEqual(len(self.store.categories()), count)

    def test_existing_files_and_settings_are_preserved(self):
        marker = self.workspace / '02_公共资源库/材料数据库/user.txt'
        marker.write_text('用户资料', encoding='utf-8')
        self.store.set('model', 'existing-model')
        self.engine.create_cae_project(str(self.workspace), 'P2026-003', '研发部', '新项目')
        self.assertEqual(marker.read_text(encoding='utf-8'), '用户资料')
        self.assertEqual(self.store.get('model'), 'existing-model')

    def test_new_project_uses_configured_library_destination(self):
        cid = self.store.get('cae_workspace_roots')[str(self.workspace)]
        c = self.store.rows('SELECT * FROM categories WHERE id=?', (cid,))[0]
        dest = self.root / '高速盘项目'
        self.store.save_category(c['name'], str(dest), c['description'], c['parent'], c['id'])
        self.engine.create_cae_project(str(self.workspace), 'P2026-005', '研发部', '新地址')
        self.assertTrue((dest / 'P2026-005_研发部_新地址').is_dir())


if __name__ == '__main__':
    unittest.main()
