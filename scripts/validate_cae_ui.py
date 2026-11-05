"""Validate template previews without creating anything at the preview address."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app import STYLE
from cae_ui import CAEDialog
from core import Store, Engine

app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
with tempfile.TemporaryDirectory(prefix='fileatlas-cae-ui-') as folder:
    root = Path(folder).resolve()
    store = Store(root / 'state')
    workspace = CAEDialog(store)
    workspace.root.setText('D:/CAE_Workspace')
    assert workspace.ok.isEnabled()
    assert '00_待整理' in workspace.output.toPlainText()
    assert store.categories() == []
    workspace.show()
    app.processEvents()
    output = Path(__file__).resolve().parents[1] / 'validation' / 'cae-workspace.png'
    output.parent.mkdir(exist_ok=True)
    workspace.grab().save(str(output))
    workspace.hide()
    Engine(store).setup_cae_workspace(str(root / 'CAE'))
    project = CAEDialog(store, project=True)
    assert not project.ok.isEnabled()
    project.code.setText('P2026-001')
    project.client.setText('研发部')
    project.name.setText('齿轮箱')
    assert project.ok.isEnabled()
    assert 'C001_基准工况' in project.output.toPlainText()
    project.name.setText('../escape')
    assert not project.ok.isEnabled()
    project.close()
    workspace.close()
    store.db.close()
print('CAE workspace and project preview dialogs: PASS')
