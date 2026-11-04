from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app import Window, STYLE
from core import Store, Engine

root = Path(__file__).resolve().parents[1] / 'validation' / 'showcase'
src = root / '示例收件箱'
src.mkdir(parents=True, exist_ok=True)
store = Store(root / 'state')
store.set_sources([str(src.resolve())])
if not store.categories():
    project = store.save_category('项目资料', str((root / '项目资料').resolve()), '项目、工程与研发文档')
    design = store.save_category('机械设计', str((root / '项目资料' / '机械设计').resolve()), '机械结构、传动设计、技术方案与仿真', project)
    finance = store.save_category('财务与合同', str((root / '财务与合同').resolve()), '合同、发票与费用报销')
    store.save_category('阅读与学习', str((root / '阅读与学习').resolve()), '论文、读书笔记、技术手册')
    for filename, cid, confidence, tags, reason, apply in [
        ('齿轮传动系统_设计方案.md', design, .98, ['机械设计','齿轮传动','方案'], '内容涉及传动结构、减速比与设计参数，匹配机械设计分类。', True),
        ('采购合同_项目设备.txt', finance, .96, ['采购','合同','设备'], '采购合同及付款约定，归入财务与合同。', True),
        ('会议纪要_需求讨论.md', project, .71, ['会议纪要','需求','项目'], '涉及多个项目主题，需要确认具体归档位置。', False)]:
        p = src / filename
        p.write_text('# ' + filename + '\n\n这是一份用于界面验证的示例文件。\n', encoding='utf-8')
        class Classifier:
            def classify(self, path):
                return dict(category_id=cid, confidence=confidence, tags=tags, reason=reason)
        engine = Engine(store, Classifier())
        engine.process(p)
        if apply:
            engine.apply(store.rows('SELECT id FROM files WHERE source=?', (str(p.resolve()),))[0]['id'])
app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
win = Window(store)
win.show()
index = 0
def capture():
    global index
    win.nav.setCurrentRow(index)
    if index == 0:
        win.activity.setPlainText('示例数据 · 用于展示界面\n\n[已整理] 齿轮传动系统_设计方案.md → 项目资料 / 机械设计\n[已整理] 采购合同_项目设备.txt → 财务与合同\n[待审核] 会议纪要_需求讨论.md → 等待确认分类')
    if index == 1:
        win.file_search.setText('机械')
        assert win.file_table.rowCount() == 1
        win.file_table.selectRow(0)
    QTimer.singleShot(220, save)
def save():
    global index
    win.grab().save(str(root / f'page-{index}.png'))
    if index == 5:
        win.quit_app()
        return
    index += 1
    QTimer.singleShot(100, capture)
QTimer.singleShot(300, capture)
app.exec()
print('All six pages rendered successfully.')
