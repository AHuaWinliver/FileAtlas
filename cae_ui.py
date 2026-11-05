"""Preview-first dialogs for the built-in CAE workspace and project templates."""
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QHBoxLayout, QPushButton, QFileDialog, QLabel, QPlainTextEdit, QDialogButtonBox)
from cae import workspace_plan, project_plan


class CAEDialog(QDialog):
    def __init__(self, store, project=False, parent=None):
        super().__init__(parent)
        self.store, self.project = store, project
        self.setWindowTitle('新建 CAE 工程项目' if project else '创建 CAE 工作空间')
        self.resize(790, 660)
        self.arguments = None
        box = QVBoxLayout(self)
        form = QFormLayout()
        if project:
            self.workspace = QComboBox()
            self.workspace.addItems(store.get('cae_workspaces', []))
            form.addRow('所属工作空间', self.workspace)
            self.code = QLineEdit()
            self.code.setPlaceholderText('例如 P2026-001（唯一编号）')
            self.client = QLineEdit()
            self.client.setPlaceholderText('客户或部门简称')
            self.name = QLineEdit()
            self.name.setPlaceholderText('例如 齿轮箱动力学分析')
            self.keywords = QLineEdit()
            self.keywords.setPlaceholderText('零部件、产品别名等，帮助 Claude 判断')
            for text, widget in [('项目编号', self.code), ('客户 / 部门', self.client), ('项目名称', self.name), ('分类关键词', self.keywords)]:
                form.addRow(text, widget)
                widget.textChanged.connect(self.preview)
            self.workspace.currentTextChanged.connect(self.preview)
        else:
            self.root = QLineEdit()
            self.root.setPlaceholderText('选择一个工作空间根目录')
            row = QHBoxLayout()
            row.addWidget(self.root)
            browse = QPushButton('浏览…')
            browse.clicked.connect(self.browse)
            row.addWidget(browse)
            form.addRow('工作空间地址', row)
            self.root.textChanged.connect(self.preview)
        box.addLayout(form)
        hint = QLabel('预览将创建的分类与物理目录。现有文件保持原位；创建完成后可在“编辑分类”中修改各节点保存地址。')
        hint.setWordWrap(True)
        box.addWidget(hint)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        box.addWidget(self.output)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        box.addWidget(self.error)
        policy = QLabel('CAE 模式：只自动整理收件箱中的独立资料；项目编号不明时等待审核；求解文件和工况配套文件保留原位。不会自动启动监控。')
        policy.setWordWrap(True)
        box.addWidget(policy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setText('创建项目与基准工况' if project else '创建工作空间')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self.preview()

    def browse(self):
        directory = QFileDialog.getExistingDirectory(self, '选择 CAE 工作空间根目录')
        if directory:
            self.root.setText(directory)

    def preview(self):
        if not hasattr(self, 'output'):
            return
        try:
            if self.project:
                root = Path(self.workspace.currentText()) / '01_项目库'
                args = (self.workspace.currentText(), self.code.text().strip(), self.client.text().strip(), self.name.text().strip(), self.keywords.text().strip())
                entries = project_plan(*args[1:])
            else:
                root = Path(self.root.text().strip())
                if not self.root.text().strip() or not root.is_absolute():
                    raise ValueError('请选择工作空间的绝对路径。')
                args = (str(root),)
                entries = workspace_plan(root)
            lines = ['保存位置：' + str(root), '']
            if not self.project:
                lines += ['00_待整理/下载与接收  ← 自动添加为整理源', '00_待整理/临时资料', '']
            lines += [path + ('  [完整目录保护]' if protected else '  [可分类资料]' if allowed else '  [目录容器]')
                      for path, description, allowed, protected in entries]
            self.output.setPlainText('\n'.join(lines))
            self.arguments = args
            self.error.clear()
            self.ok.setEnabled(True)
        except ValueError as exc:
            self.error.setText(str(exc))
            self.arguments = None
            self.ok.setEnabled(False)
