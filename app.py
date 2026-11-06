from __future__ import annotations
import argparse
import json
from itertools import islice
import os
from pathlib import Path
import shutil
import sys
import traceback


def log_unhandled(kind, value, tb):
    try:
        folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FileAtlas'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'startup-error.log').write_text(''.join(traceback.format_exception(kind, value, tb)), encoding='utf-8')
    finally:
        sys.__excepthook__(kind, value, tb)


sys.excepthook = log_unhandled
from PySide6.QtCore import Qt, QTimer, QUrl, QLockFile, QPropertyAnimation, QEasingCurve, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QCheckBox, QDoubleSpinBox, QListWidget, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QFormLayout,
    QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QFrame, QSystemTrayIcon, QMenu, QAbstractItemView, QGraphicsOpacityEffect, QSizeGrip, QScrollArea, QProgressBar, QSizePolicy)
from core import Store, Engine, extract, initialize_local_model
from worker import SortMode, Worker
from cae import allowed_category
from cae_ui import CAEDialog


STYLE = '''
QWidget {font-family:"Microsoft YaHei UI";font-size:13px;color:#28354b;}
QMainWindow {background:transparent;}
QDialog {background:#f4f6fb;}
QWidget#surface {background:rgba(245,248,253,100);border:1px solid rgba(255,255,255,200);border-radius:14px;}
QWidget#workspace {background:rgba(249,251,255,130);border-top-right-radius:14px;}
QFrame#sidebar {background:rgba(226,234,246,75);border-right:1px solid rgba(255,255,255,160);border-top-left-radius:14px;border-bottom-left-radius:14px;}
QLabel#brand {color:#243956;font-size:25px;font-weight:700;}
QLabel#sidehint {color:#7387a0;font-size:12px;}
QListWidget#nav {background:transparent;border:0;color:#51657e;font-size:14px;outline:0;}
QListWidget#nav::item {padding:15px 14px;margin:3px 0;border-radius:8px;}
QListWidget#nav::item:hover {background:rgba(255,255,255,100);}
QListWidget#nav::item:selected {background:rgba(255,255,255,215);color:#1672bf;}
QLabel#title {font-size:26px;font-weight:700;color:#172940;}
QLabel#muted {color:#738198;}
QFrame#card {background:rgba(255,255,255,185);border:1px solid rgba(255,255,255,235);border-radius:14px;}
QLabel#metric {font-size:30px;font-weight:700;color:#1c6eab;}
QPushButton {background:rgba(255,255,255,190);border:1px solid #d4deeb;border-radius:8px;padding:9px 15px;}
QPushButton:hover {background:#eaf1fa;border-color:#9bb5d5;}
QPushButton#primary {background:#246fae;border-color:#246fae;color:white;font-weight:600;}
QPushButton#primary:hover {background:#1b5b91;}
QPushButton:disabled,QPushButton#primary:disabled {background:#eef2f7;border-color:#dce4ee;color:#8895a7;}
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QDoubleSpinBox {background:white;border:1px solid #d8e1ed;border-radius:6px;padding:8px;selection-background-color:#b9d9f5;}
QTreeWidget,QTableWidget {background:rgba(255,255,255,200);border:1px solid rgba(220,230,243,190);border-radius:10px;alternate-background-color:rgba(241,246,253,160);outline:0;}
QHeaderView::section {background:#f1f5fa;color:#687b94;border:0;border-bottom:1px solid #e2e8f1;padding:10px;font-weight:600;}
QTableWidget::item {padding:7px;}
QTableWidget::item:selected,QTreeWidget::item:selected {background:#e0effc;color:#164e7c;}
QSplitter::handle {background:transparent;width:10px;}
QCheckBox {spacing:8px;padding:5px 0;}
QProgressBar {background:rgba(190,209,231,150);border:0;border-radius:3px;}
QProgressBar::chunk {background:#3689c6;border-radius:3px;}
QStatusBar {background:rgba(242,246,253,180);color:#60728a;}
QPushButton#caption {background:transparent;border:0;border-radius:6px;font-size:16px;padding:3px;min-width:38px;min-height:27px;}
QPushButton#caption:hover {background:rgba(190,204,226,110);}
'''


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setFixedHeight(42)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 0, 4, 0)
        title = label('FILEATLAS  /  你的智能文件空间', 'muted')
        title.setWordWrap(False)
        row.addWidget(title)
        row.addStretch()
        for text, fn in [('−', window.showMinimized), ('□', self.maximize), ('×', window.close)]:
            b = button(text, fn)
            b.setObjectName('caption')
            row.addWidget(b)

    def maximize(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event):
        self.maximize()


class PreviewSignals(QObject):
    finished = Signal(str, str)


class PreviewTask(QRunnable):
    def __init__(self, fid, path):
        super().__init__()
        self.fid, self.path = fid, path
        self.signals = PreviewSignals()

    def run(self):
        try:
            if self.path.is_dir():
                entries = list(islice(self.path.iterdir(), 41))
                lines = ['整包归档 · 保留原目录结构', '']
                lines.extend(('📁 ' if p.is_dir() else '· ') + p.name for p in entries[:40])
                if len(entries) > 40:
                    lines.append('更多内容可在资源管理器中查看。')
                text = '\n'.join(lines)
            else:
                text = extract(self.path)[:5000] if self.path.is_file() else '项目已被外部移动或删除。'
        except Exception as exc:
            text = '无法预览：' + str(exc)
        self.signals.finished.emit(self.fid, text)


class ClaudeCheckSignals(QObject):
    finished = Signal(bool, str)


class ClaudeCheckTask(QRunnable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = ClaudeCheckSignals()

    def run(self):
        import subprocess
        try:
            if not self.path.is_file() or self.path.suffix.lower() != '.exe':
                raise ValueError('请选择 claude.exe')
            result = subprocess.run([str(self.path), '--version'], capture_output=True, text=True,
                                    timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise ValueError(result.stderr.strip() or f'程序退出码 {result.returncode}')
            self.signals.finished.emit(True, result.stdout.strip())
        except Exception as exc:
            self.signals.finished.emit(False, str(exc))


def button(text, fn, primary=False):
    w = QPushButton(text)
    if primary:
        w.setObjectName('primary')
    w.clicked.connect(fn)
    return w


def label(text, name=None):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(True)
    return w


class ProgressLine(QWidget):
    def __init__(self, *, persistent=False):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        row = QHBoxLayout()
        self.caption = label('', 'muted')
        self.caption.setWordWrap(False)
        self.caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.caption, 1)
        self.count = label('', 'muted')
        self.count.setWordWrap(False)
        row.addWidget(self.count)
        box.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        box.addWidget(self.bar)
        self.reveal = QTimer(self, singleShot=True, interval=180)
        self.reveal.timeout.connect(self.show)
        self.dismiss = QTimer(self, singleShot=True, interval=650)
        self.dismiss.timeout.connect(self.hide)
        if not persistent:
            self.hide()

    def update_progress(self, message='', done=0, total=0, *, idle=False):
        self.dismiss.stop()
        if not message:
            self.reveal.stop()
            if not self.isHidden() and self.bar.maximum() > 0 and self.bar.value() == self.bar.maximum():
                self.dismiss.start()
            else:
                self.hide()
            return
        self.caption.setText(message)
        self.caption.setToolTip(message)
        self.count.setText(f'{done}/{total}' if total else '')
        self.bar.setAccessibleName(message)
        self.bar.setRange(0, total or int(idle))
        if total or idle:
            self.bar.setValue(done)
        if self.isHidden() and not self.reveal.isActive():
            self.reveal.start()

    def show_idle(self, message, *, keep_value=False):
        if keep_value and self.count.text():
            self.update_progress(message, self.bar.value(), self.bar.maximum(), idle=True)
        else:
            self.update_progress(message, idle=True)


def icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('#246fae'))
    p.drawRoundedRect(2, 2, 60, 60, 15, 15)
    p.setBrush(QColor('#80d5d1'))
    p.drawRoundedRect(14, 19, 20, 12, 3, 3)
    p.setBrush(QColor('#ffffff'))
    p.drawRoundedRect(14, 26, 37, 24, 4, 4)
    p.end()
    return QIcon(pix)


class CategoryDialog(QDialog):
    def __init__(self, store, category=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('编辑分类' if category else '新建分类')
        self.resize(560, 350)
        self.store, self.category = store, category
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit((category or {}).get('name', ''))
        self.parent_box = QComboBox()
        self.parent_box.addItem('顶级分类', None)
        for c in store.categories():
            if not category or c['id'] != category['id']:
                self.parent_box.addItem(store.category_name(c['id']), c['id'])
        if category:
            self.parent_box.setCurrentIndex(max(0, self.parent_box.findData(category['parent'])))
        self.destination = QLineEdit((category or {}).get('destination', ''))
        row = QHBoxLayout()
        row.addWidget(self.destination)
        row.addWidget(button('浏览', self.browse))
        self.description = QPlainTextEdit((category or {}).get('description', ''))
        self.description.setPlaceholderText('填写分类依据。可另起一行写「扩展名规则：.pdf .docx」或「文件夹规则：项目交付包 | 试验资料包」。')
        form.addRow('分类名称', self.name)
        form.addRow('父级分类', self.parent_box)
        form.addRow('保存地址', row)
        form.addRow('分类依据', self.description)
        layout.addLayout(form)
        layout.addWidget(label('子分类的保存地址可独立设置，不必位于父分类的物理文件夹内。', 'muted'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self):
        value = QFileDialog.getExistingDirectory(self, '选择分类保存位置')
        if value:
            self.destination.setText(value)

    def save(self):
        try:
            self.store.save_category(self.name.text(), self.destination.text(), self.description.toPlainText(), self.parent_box.currentData(), (self.category or {}).get('id'))
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, '无法保存', str(exc))


class Window(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.engine = Engine(store)
        self.worker = Worker(self.engine)
        self.preview_requests = {}
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(250)
        self.refresh_timer.timeout.connect(self.refresh)
        self.worker.changed.connect(lambda: self.refresh_timer.start() if not self.refresh_timer.isActive() else None)
        self.worker.message.connect(self.statusBar().showMessage)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('FileAtlas · 智能文件整理')
        self.setWindowIcon(icon())
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        root = QWidget()
        root.setObjectName('surface')
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 30, 20, 24)
        side.addWidget(label('▣  FileAtlas', 'brand'))
        side.addWidget(label('让每一份文件，各归其位', 'sidehint'))
        side.addSpacing(30)
        self.nav = QListWidget()
        self.nav.setObjectName('nav')
        self.nav.addItems(['◈   工作台', '▤   文件资料库', '◎   待审核', '⌘   分类与目录', '⚙   自动化设置', '≡   整理记录'])
        side.addWidget(self.nav)
        side.addWidget(label('LOCAL FIRST\n本地索引 · 可追溯整理', 'sidehint'))
        layout.addWidget(sidebar)
        workspace = QWidget()
        workspace.setObjectName('workspace')
        area = QVBoxLayout(workspace)
        area.setContentsMargins(26, 0, 20, 18)
        area.addWidget(TitleBar(self))
        heading = QHBoxLayout()
        self.heading = label('工作台', 'title')
        heading.addWidget(self.heading)
        heading.addStretch()
        self.watch_btn = button('启动自动监控', self.toggle_watch, True)
        self.scan_btn = button('扫描源文件夹', self.scan)
        heading.addWidget(self.scan_btn)
        heading.addWidget(self.watch_btn)
        area.addLayout(heading)
        self.global_progress_area = QWidget()
        progress_layout = QVBoxLayout(self.global_progress_area)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.task_progress = ProgressLine()
        progress_layout.addWidget(self.task_progress)
        area.addWidget(self.global_progress_area)
        self.worker.progress.connect(self.task_progress.update_progress)
        area.addSpacing(12)
        self.stack = QStackedWidget()
        area.addWidget(self.stack)
        layout.addWidget(workspace)
        self.make_dashboard()
        self.make_library(False)
        self.make_library(True)
        self.make_categories()
        self.make_settings()
        self.make_history()
        self.worker.sorting_state_changed.connect(self.update_sorting_controls)
        self.worker.sorting_progress.connect(self.show_sorting_progress)
        self.update_sorting_controls()
        self.nav.currentRowChanged.connect(self.navigate)
        self.nav.setCurrentRow(0)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu()
        menu.addAction('打开 FileAtlas', self.showNormal)
        menu.addAction('退出', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip('FileAtlas · 智能文件整理')
        self.tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        self.worker.start()
        self.refresh()
        self.statusBar().showMessage('就绪 · 添加分类和源文件夹即可开始')
        self.statusBar().setSizeGripEnabled(True)
        self.apply_backdrop()

    def apply_backdrop(self):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            backdrop = ctypes.c_int(3)  # Windows 11 Desktop Acrylic
            result = dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), 4)
            corner = ctypes.c_int(2)
            dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), 4)
            class Margins(ctypes.Structure):
                _fields_ = [('left', ctypes.c_int), ('right', ctypes.c_int), ('top', ctypes.c_int), ('bottom', ctypes.c_int)]
            dwm.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.POINTER(Margins)]
            dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(Margins(-1, -1, -1, -1)))
            if result:
                self.centralWidget().setStyleSheet('QWidget#surface {background:#eff3fa;}')
        except Exception:
            self.centralWidget().setStyleSheet('QWidget#surface {background:#eff3fa;}')

    def nativeEvent(self, event_type, message):
        if sys.platform == 'win32' and not self.isMaximized():
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x84:  # WM_NCHITTEST: retain native edge resizing
                x = ctypes.c_short(msg.lParam & 0xffff).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
                rect = self.frameGeometry()
                scale = self.devicePixelRatioF()
                left, top = round(rect.left() * scale), round(rect.top() * scale)
                right, bottom = left + round(rect.width() * scale), top + round(rect.height() * scale)
                edge = round(7 * scale)
                l, r, t, b = x < left + edge, x >= right - edge, y < top + edge, y >= bottom - edge
                hit = 13 if l and t else 14 if r and t else 16 if l and b else 17 if r and b else 10 if l else 11 if r else 12 if t else 15 if b else None
                if hit:
                    return True, hit
        return super().nativeEvent(event_type, message)

    def page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(16)
        self.stack.addWidget(page)
        return box

    def navigate(self, i):
        self.stack.setCurrentIndex(i)
        self.watch_btn.setVisible(i != 0)
        self.global_progress_area.setVisible(i != 0)
        self.heading.setText(['工作台', '文件资料库', '待审核', '分类与目录', '自动化设置', '整理记录'][i])
        self.refresh()
        effect = QGraphicsOpacityEffect(self.stack.currentWidget())
        self.stack.currentWidget().setGraphicsEffect(effect)
        self.transition = QPropertyAnimation(effect, b'opacity', self)
        self.transition.setDuration(145)
        self.transition.setStartValue(.55)
        self.transition.setEndValue(1)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.start()

    def make_dashboard(self):
        box = self.page()
        metrics = QHBoxLayout()
        self.metrics = []
        for text in ['已索引条目', '已完成整理', '等待审核', '分类节点']:
            card = QFrame()
            card.setObjectName('card')
            b = QVBoxLayout(card)
            b.setContentsMargins(20, 18, 20, 18)
            b.addWidget(label(text, 'muted'))
            number = label('0', 'metric')
            b.addWidget(number)
            self.metrics.append(number)
            metrics.addWidget(card)
        box.addLayout(metrics)
        card = QFrame()
        card.setObjectName('card')
        b = QVBoxLayout(card)
        b.setContentsMargins(24, 24, 24, 24)
        header = QHBoxLayout()
        header.addWidget(label('整理任务', 'title'))
        header.addStretch()
        self.sort_state = label('', 'muted')
        header.addWidget(self.sort_state)
        b.addLayout(header)
        self.dashboard_progress = ProgressLine(persistent=True)
        b.addWidget(self.dashboard_progress)
        controls = QHBoxLayout()
        self.sort_start_btn = button('启动整理', self.start_monitoring, True)
        self.sort_pause_btn = button('暂停整理', self.pause_sorting)
        self.sort_stop_btn = button('停止整理', self.stop_sorting)
        self.sort_pause_btn.setToolTip('当前文件处理完成后暂停，可继续整理。')
        self.sort_stop_btn.setToolTip('当前文件处理完成后结束本轮整理，下次启动时重新扫描。')
        for control in (self.sort_start_btn, self.sort_pause_btn, self.sort_stop_btn):
            controls.addWidget(control)
        controls.addStretch()
        b.addLayout(controls)
        self.summary = label('')
        b.addWidget(self.summary)
        row = QHBoxLayout()
        row.addWidget(button('① 设置分类', lambda: self.nav.setCurrentRow(3), True))
        row.addWidget(button('② 设置整理源', lambda: self.nav.setCurrentRow(4)))
        row.addWidget(button('③ 查看待审核', lambda: self.nav.setCurrentRow(2)))
        row.addStretch()
        b.addLayout(row)
        box.addWidget(card)
        activity_header = QHBoxLayout()
        activity_header.addWidget(label('最近动态', 'title'))
        activity_header.addStretch()
        activity_header.addWidget(button('清空动态', self.clear_events))
        box.addLayout(activity_header)
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        box.addWidget(self.activity)

    def make_library(self, review):
        box = self.page()
        row = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText('搜索文件名、标签、路径或分类…')
        search.textChanged.connect(self.refresh_files)
        row.addWidget(search)
        row.addWidget(button('刷新', self.refresh))
        box.addLayout(row)
        split = QSplitter(Qt.Orientation.Vertical)
        table = self.table(['文件名称', '分类', '标签', '置信度', '状态', '更新时间'])
        table.itemSelectionChanged.connect(lambda: self.preview(review))
        table.itemDoubleClicked.connect(lambda _: self.open_selected(review))
        split.addWidget(table)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText('选择文件查看分类依据、完整路径与内容摘录。双击可在资源管理器定位。')
        preview_panel = QWidget()
        preview_box = QVBoxLayout(preview_panel)
        preview_box.setContentsMargins(0, 0, 0, 0)
        preview_progress = ProgressLine()
        preview_box.addWidget(preview_progress)
        preview_box.addWidget(preview)
        split.addWidget(preview_panel)
        split.setSizes([450, 180])
        box.addWidget(split)
        actions = QHBoxLayout()
        actions.addWidget(button('在资源管理器中定位', lambda: self.open_selected(review)))
        actions.addWidget(button('清空预览', lambda: self.clear_preview(review)))
        if review:
            combo = QComboBox()
            combo.setMinimumWidth(240)
            actions.addWidget(combo)
            actions.addWidget(button('按所选分类整理', self.apply_selected, True))
            actions.addWidget(button('重新分析所选', self.reanalyze))
            self.review_combo = combo
        else:
            actions.addWidget(button('编辑标签', self.edit_tags))
        actions.addStretch()
        box.addLayout(actions)
        if review:
            self.review_table, self.review_search, self.review_preview = table, search, preview
            self.review_preview_progress = preview_progress
        else:
            self.file_table, self.file_search, self.file_preview = table, search, preview
            self.file_preview_progress = preview_progress

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(43)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        return table

    def make_categories(self):
        box = self.page()
        cae_row = QHBoxLayout()
        cae_row.addWidget(button('创建 CAE 工作空间', lambda: self.cae_template(False), True))
        cae_row.addWidget(button('新建工程项目', lambda: self.cae_template(True)))
        cae_row.addWidget(label('项目 → 工作阶段 → 工况 · 求解文件保护', 'muted'))
        cae_row.addStretch()
        box.addLayout(cae_row)
        box.addWidget(label('逻辑分类支持多级嵌套，每个节点均有独立保存地址。修改地址只影响以后的整理。', 'muted'))
        row = QHBoxLayout()
        row.addWidget(button('＋ 新建分类', self.add_category, True))
        row.addWidget(button('编辑分类', self.edit_category))
        row.addWidget(button('删除分类', self.delete_category))
        row.addWidget(button('从现有目录生成分类', self.import_tree))
        row.addStretch()
        row.addWidget(button('导出目录 Markdown', self.export_tree))
        box.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['分类 / 文件', '保存地址', '分类依据 / 标签'])
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 360)
        self.tree.itemDoubleClicked.connect(self.tree_open)
        box.addWidget(self.tree)

    def make_settings(self):
        outer = self.page()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea,QScrollArea > QWidget > QWidget {background:transparent;}')
        contents = QWidget()
        box = QVBoxLayout(contents)
        box.setContentsMargins(0, 0, 12, 0)
        box.setSpacing(14)
        scroll.setWidget(contents)
        outer.addWidget(scroll)
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.sources = QPlainTextEdit('\n'.join(self.store.get('sources', [])))
        self.sources.setMaximumHeight(110)
        self.sources.setPlaceholderText('每行一个绝对路径；可添加多个监控源文件夹。')
        srcbox = QVBoxLayout()
        srcbox.addWidget(self.sources)
        srcbox.addWidget(button('＋ 选择源文件夹', self.browse_source))
        form.addRow('默认整理源', srcbox)
        self.claude = QLineEdit(self.store.get('claude_path', '') or shutil.which('claude') or '')
        clirow = QHBoxLayout()
        clirow.addWidget(self.claude)
        clirow.addWidget(button('浏览', self.browse_claude))
        form.addRow('Claude Code 程序', clirow)
        self.model = QLineEdit(self.store.get('model', ''))
        self.model.setPlaceholderText('留空使用 Claude Code 当前默认模型')
        form.addRow('模型', self.model)
        self.endpoint = QLineEdit(self.store.get('endpoint', ''))
        self.endpoint.setPlaceholderText('留空继承 Claude Code；例如 http://127.0.0.1:11434')
        form.addRow('模型服务地址（可选）', self.endpoint)
        self.mode = QComboBox()
        self.mode.addItem('复制到分类目录（保留源文件）', 'copy')
        self.mode.addItem('移动到分类目录（校验后移除源文件）', 'move')
        self.mode.setCurrentIndex(max(0, self.mode.findData(self.store.get('mode', 'copy'))))
        form.addRow('归档方式', self.mode)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(.5, 1)
        self.threshold.setSingleStep(.05)
        self.threshold.setValue(self.store.get('threshold', .85))
        form.addRow('自动归档置信度阈值', self.threshold)
        self.auto = QCheckBox('高于阈值直接整理；其余进入待审核')
        self.auto.setChecked(self.store.get('auto_apply', False))
        form.addRow('自动执行', self.auto)
        self.content = QCheckBox('提取 TXT / Markdown / CSV / PDF / DOCX 等文件的内容摘录（最多 12,000 字符）')
        self.content.setChecked(self.store.get('send_content', True))
        form.addRow('内容识别', self.content)
        self.folder_first = QCheckBox('先判断整包，混合目录再逐层下钻')
        self.folder_first.setChecked(self.store.get('folder_first', True))
        form.addRow('文件夹优先', self.folder_first)
        self.background = QCheckBox('关闭窗口后继续在托盘监控（使用托盘菜单退出）')
        self.background.setChecked(self.store.get('background', True))
        form.addRow('后台运行', self.background)
        box.addLayout(form)
        box.addWidget(label('Claude Code 在本机启动，模型请求会使用它当前配置的服务与凭据。文件名、路径及启用后的内容摘录会发送给该服务。图片、扫描 PDF、旧版 Office、压缩包当前按名称和元数据识别。', 'muted'))
        box.addWidget(label('整包判断使用文件夹名称和浅层相对名称。按一个项目记录标签、进度和撤销，目录内部结构原样保留。', 'muted'))
        box.addWidget(label('文件先等待至少 3 秒稳定；同名文件保留双方；目标目录从源监控中排除；失败记录写入“整理记录”。', 'muted'))
        row = QHBoxLayout()
        row.addWidget(button('保存设置', self.save_settings, True))
        row.addWidget(button('保存并启动自动整理', self.save_and_start))
        self.claude_check_btn = button('检测 Claude Code', self.check_claude)
        row.addWidget(self.claude_check_btn)
        row.addWidget(button('打开应用数据目录', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.home)))))
        row.addStretch()
        box.addLayout(row)
        self.claude_check_progress = ProgressLine()
        box.addWidget(self.claude_check_progress)
        box.addStretch()

    def make_history(self):
        box = self.page()
        row = QHBoxLayout()
        row.addWidget(label('完整操作记录保存在本地 SQLite。撤销前会再次校验文件内容。', 'muted'))
        row.addStretch()
        row.addWidget(button('撤销所选操作', self.undo))
        box.addLayout(row)
        self.history = self.table(['原文件', '目标路径', '方式', '状态', '时间', '异常说明'])
        box.addWidget(self.history)
        log_header = QHBoxLayout()
        log_header.addWidget(label('活动日志', 'muted'))
        log_header.addStretch()
        log_header.addWidget(button('清空日志', self.clear_events))
        box.addLayout(log_header)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(200)
        box.addWidget(self.logs)

    def selected(self, table):
        row = table.currentRow()
        item = table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def clear_events(self):
        latest = self.store.rows('SELECT COALESCE(MAX(id), 0) AS id FROM events')[0]['id']
        self.store.set('events_visible_after', latest)
        self.refresh_events()

    def refresh_events(self):
        cutoff = self.store.get('events_visible_after', 0)
        events = self.store.rows('SELECT * FROM events WHERE id > ? ORDER BY id DESC LIMIT 60', (cutoff,))
        logs = '\n'.join(f"{x['created']}  [{x['level']}]  {x['message']}" for x in events)
        self.activity.setPlaceholderText('日志已清空，新的动态将在这里显示。' if cutoff else '还没有整理记录。设置分类与整理源后，点击“扫描源文件夹”开始。')
        self.logs.setPlaceholderText('日志已清空，新的记录将在这里显示。' if cutoff else '暂无活动日志。')
        for view in (self.activity, self.logs):
            if view.toPlainText() != logs:
                view.setPlainText(logs)

    def refresh(self):
        if getattr(self, 'template_pending', False) and not self.worker.busy:
            self.sources.setPlainText('\n'.join(self.store.get('sources', [])))
            self.template_pending = False
        cats = self.store.categories()
        counts = self.store.rows('SELECT status,COUNT(*) n FROM files GROUP BY status')
        c = {r['status']: r['n'] for r in counts}
        for w, v in zip(self.metrics, [sum(c.values()), c.get('done', 0), c.get('review', 0), len(cats)]):
            w.setText(str(v))
        self.summary.setText(f"整理源 {len(self.store.get('sources', []))} 个  ·  分类 {len(cats)} 个  ·  {'自动归档已开启' if self.store.get('auto_apply', False) else '分类后等待审核'}  ·  {'移动模式' if self.store.get('mode', 'copy') == 'move' else '复制模式'}")
        self.refresh_events()
        self.refresh_files()
        selected = self.review_combo.currentData()
        self.review_combo.clear()
        self.review_combo.addItem('使用 AI 推荐分类', None)
        for cat in cats:
            if allowed_category(self.store, cat['id']):
                self.review_combo.addItem(self.store.category_name(cat['id']), cat['id'])
        self.review_combo.setCurrentIndex(max(0, self.review_combo.findData(selected)))
        self.tree.clear()
        def walk(parent, widget):
            for cat in cats:
                if cat['parent'] == parent:
                    node = QTreeWidgetItem([cat['name'], cat['destination'], cat['description']])
                    node.setData(0, Qt.ItemDataRole.UserRole, cat['id'])
                    if widget:
                        widget.addChild(node)
                    else:
                        self.tree.addTopLevelItem(node)
                    walk(cat['id'], node)
                    entries = self.store.rows("SELECT * FROM files WHERE category=? AND status IN ('done','indexed') ORDER BY path LIMIT 201", (cat['id'],))
                    for f in entries[:200]:
                        name = Path(f['path']).name
                        if f['kind'] == 'folder':
                            name = '📦 ' + name + '（整包）'
                        child = QTreeWidgetItem([name, f['path'], ' · '.join(json.loads(f['tags']))])
                        node.addChild(child)
                    if len(entries) > 200:
                        node.addChild(QTreeWidgetItem(['更多文件请在资料库中搜索', '', '']))
        walk(None, None)
        self.tree.expandAll()
        ops = self.store.rows('SELECT * FROM operations ORDER BY created DESC LIMIT 1000')
        self.fill(self.history, [(o['id'], [Path(o['source']).name, o['destination'], {'copy':'复制','move':'移动'}.get(o['mode'], o['mode']), o['status'], o['created'], o['error']]) for o in ops])

    def fill(self, table, rows):
        selected = self.selected(table)
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for i, (key, cells) in enumerate(rows):
            for j, value in enumerate(cells):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, key)
                table.setItem(i, j, item)
            if key == selected:
                table.selectRow(i)
        table.blockSignals(False)

    def refresh_files(self):
        for table, search, review in [(self.file_table, self.file_search, False), (self.review_table, self.review_search, True)]:
            query = search.text().strip()
            matching_categories = [c['id'] for c in self.store.categories() if query.lower() in self.store.category_name(c['id']).lower()]
            clauses, args = [], []
            if review:
                clauses.append("status='review'")
            if query:
                escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                cond = "path LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\'"
                args.extend(['%' + escaped + '%', '%' + escaped + '%'])
                if matching_categories:
                    cond += ' OR category IN (' + ','.join('?' for _ in matching_categories) + ')'
                    args.extend(matching_categories)
                clauses.append('(' + cond + ')')
            files = self.store.rows('SELECT * FROM files ' + ('WHERE ' + ' AND '.join(clauses) + ' ' if clauses else '') + 'ORDER BY updated DESC LIMIT 1000', args)
            rows = []
            for f in files:
                cat = self.store.category_name(f['category']) or '未匹配分类'
                name = Path(f['path']).name + ('（整包）' if f['kind'] == 'folder' else '')
                rows.append((f['id'], [name, cat, ' · '.join(json.loads(f['tags'])), f"{f['confidence']:.0%}" if f['status'] != 'indexed' else '位置索引', {'review':'待审核','done':'已整理','undone':'已撤销','indexed':'原有文件','missing':'项目已移走','superseded':'已有新版本','protected':'工况受保护'}.get(f['status'], f['status']), f['updated']]))
            self.fill(table, rows)

    def file(self, review):
        fid = self.selected(self.review_table if review else self.file_table)
        found = self.store.rows('SELECT * FROM files WHERE id=?', (fid,))
        return found[0] if found else None

    def preview(self, review):
        f = self.file(review)
        target = self.review_preview if review else self.file_preview
        progress = self.review_preview_progress if review else self.file_preview_progress
        self.preview_requests.pop(review, None)
        if f:
            p = Path(f['path'])
            text = f"路径：{p}\n源路径：{f['source']}\n分类依据：{f['reason']}\n标签：{' / '.join(json.loads(f['tags']))}\n\n"
            target.setPlainText(text + '正在读取预览…')
            progress.update_progress('正在读取文件预览')
            request = object()
            self.preview_requests[review] = request
            task = PreviewTask(f['id'], p)

            def ready(fid, content):
                if self.preview_requests.get(review) is not request:
                    return
                self.preview_requests.pop(review)
                progress.update_progress()
                table = self.review_table if review else self.file_table
                if self.selected(table) == fid:
                    target.setPlainText(text + content)
                else:
                    target.clear()
            task.signals.finished.connect(ready)
            QThreadPool.globalInstance().start(task)
        else:
            target.clear()
            progress.update_progress()

    def clear_preview(self, review):
        table = self.review_table if review else self.file_table
        table.selectionModel().clear()
        self.preview(review)

    def open_selected(self, review):
        f = self.file(review)
        if f:
            if f['kind'] == 'folder':
                QDesktopServices.openUrl(QUrl.fromLocalFile(f['path']))
            else:
                import subprocess
                subprocess.Popen(['explorer.exe', '/select,', f['path']])

    def ready_to_scan(self):
        sources = self.store.get('sources', [])
        if not any(Path(source).is_dir() for source in sources):
            QMessageBox.information(self, '请检查整理源', '请保存至少一个可访问的整理源文件夹。')
            return False
        if not any(allowed_category(self.store, cat['id']) for cat in self.store.categories()):
            QMessageBox.information(self, '请检查分类', '请先添加至少一个可以接收文件的分类。')
            return False
        if not self.worker.isRunning():
            self.worker.start()
        return True

    def scan(self):
        if not self.ready_to_scan():
            return
        if not self.worker.sorting_status()[0].active:
            self.dashboard_progress.update_progress('正在准备扫描整理源')
        self.worker.request_scan()
        self.statusBar().showMessage('正在扫描，等待整理项写入稳定后开始分析…')

    def update_sorting_controls(self):
        mode, paused, working = self.worker.sorting_status()
        stopped = not mode.active
        running = not stopped and not paused
        self.sort_start_btn.setEnabled((paused or stopped) and not working)
        self.sort_start_btn.setText('继续整理' if paused else '启动整理')
        self.sort_pause_btn.setEnabled(running)
        self.sort_stop_btn.setEnabled(not stopped)
        self.scan_btn.setEnabled(not paused and not (stopped and working))
        self.watch_btn.setEnabled(not ((paused or stopped) and working))
        self.watch_btn.setText('继续自动整理' if paused else '暂停自动整理' if running else '启动自动监控')
        if stopped:
            if mode == SortMode.MANUAL_DONE:
                self.sort_state.setText('单次扫描结束')
                self.dashboard_progress.show_idle('点击「启动整理」扫描并监控整理源', keep_value=True)
            elif working:
                self.sort_state.setText('正在停止')
            else:
                self.sort_state.setText('已停止')
                self.dashboard_progress.show_idle('点击「启动整理」扫描并监控整理源')
        elif paused:
            self.sort_state.setText('正在暂停' if working else '已暂停')
            if not working:
                self.dashboard_progress.show_idle('点击「继续整理」处理剩余文件', keep_value=True)
        else:
            self.sort_state.setText('自动整理中' if mode == SortMode.MONITORING else '扫描整理中')

    def show_sorting_progress(self, message, done, total):
        mode, paused, working = self.worker.sorting_status()
        if mode == SortMode.MANUAL_DONE:
            if total:
                self.dashboard_progress.update_progress('单次扫描结束', done, total, idle=True)
        elif paused and not working:
            if total and done:
                self.dashboard_progress.update_progress('点击「继续整理」处理剩余文件', done, total, idle=True)
        elif mode.active or working:
            if message:
                self.dashboard_progress.update_progress(message, done, total)
            elif not paused:
                self.dashboard_progress.show_idle('正在监控整理源 · 等待新文件', keep_value=True)

    def start_monitoring(self, *, continuous=False):
        mode, paused, _ = self.worker.sorting_status()
        if (mode == SortMode.MONITORING and not paused) or not self.ready_to_scan():
            return
        self.dashboard_progress.update_progress('正在准备扫描整理源')
        self.worker.start_sorting(continuous=continuous)
        message = '继续整理，检查尚未处理的文件' if paused else '开始扫描现有文件，符合条件时自动归档' if self.store.get('auto_apply', False) else '开始扫描现有文件，分类结果进入待审核'
        self.store.event('监控', message)
        self.statusBar().showMessage(message)
        self.refresh_events()

    def toggle_watch(self):
        mode, paused, _ = self.worker.sorting_status()
        if not mode.active or paused:
            self.start_monitoring()
        else:
            self.pause_sorting()

    def pause_sorting(self):
        self.worker.pause_sorting()
        self.statusBar().showMessage('暂停整理 · 当前文件安全处理完成后暂停' if self.worker.sorting_status()[2] else '整理已暂停')

    def stop_sorting(self):
        self.worker.stop_sorting()
        self.statusBar().showMessage('停止整理 · 当前文件安全处理完成后停止' if self.worker.sorting_status()[2] else '整理已停止')

    def apply_selected(self):
        f = self.file(True)
        if f:
            self.worker.enqueue('apply', f['id'], self.review_combo.currentData())

    def reanalyze(self):
        if self.worker.sorting_status()[1]:
            QMessageBox.information(self, '整理已暂停', '请先继续整理，再重新分析。')
            return
        if self.worker.busy:
            QMessageBox.information(self, '正在处理', '请等待当前任务完成。')
            return
        f = self.file(True)
        if f:
            if f['kind'] == 'folder':
                self.store.run('DELETE FROM folder_decisions WHERE path=?', (f['source'],))
            self.store.run("DELETE FROM files WHERE id=? AND status='review'", (f['id'],))
            self.worker.request_scan()
            self.refresh()

    def edit_tags(self):
        f = self.file(False)
        if not f:
            return
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, '编辑标签', '以逗号分隔：', text=', '.join(json.loads(f['tags'])))
        if ok:
            self.store.run('UPDATE files SET tags=? WHERE id=?', (json.dumps(list(dict.fromkeys(t.strip()[:40] for t in text.replace('，', ',').split(',') if t.strip()))[:20], ensure_ascii=False), f['id']))
            self.worker.enqueue('export_tree')
            self.refresh()

    def category(self):
        node = self.tree.currentItem()
        cid = node.data(0, Qt.ItemDataRole.UserRole) if node else None
        return next((c for c in self.store.categories() if c['id'] == cid), None)

    def add_category(self):
        if CategoryDialog(self.store, parent=self).exec():
            self.worker.enqueue('export_tree')
            self.refresh()

    def cae_template(self, project):
        if self.worker.busy:
            QMessageBox.information(self, '正在处理', '请等待当前任务完成后创建模板。')
            return
        if project and not self.store.get('cae_workspaces', []):
            QMessageBox.information(self, '请先创建工作空间', '先选择“创建 CAE 工作空间”，再按项目编号建立工程项目。')
            return
        dialog = CAEDialog(self.store, project, self)
        if dialog.exec() and dialog.arguments:
            self.template_pending = True
            self.worker.stop_sorting()
            self.worker.enqueue('create_cae_project' if project else 'setup_cae_workspace', *dialog.arguments)
            self.statusBar().showMessage('正在创建 CAE 分类与目录，完成后可刷新并查看…')

    def import_tree(self):
        path = QFileDialog.getExistingDirectory(self, '选择现有分类目录（读取目录和文件，不移动文件）')
        if path:
            self.worker.enqueue('import_tree', path)

    def edit_category(self):
        c = self.category()
        if c and CategoryDialog(self.store, c, self).exec():
            self.worker.enqueue('export_tree')
            self.refresh()

    def delete_category(self):
        c = self.category()
        if c:
            try:
                self.store.delete_category(c['id'])
                self.worker.enqueue('export_tree')
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, '无法删除', str(exc))

    def tree_open(self, item, column):
        value = item.text(1)
        if Path(value).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(value if Path(value).is_dir() else str(Path(value).parent)))

    def export_tree(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出文件目录', '文件目录.md', 'Markdown (*.md)')
        if path:
            self.worker.enqueue('export_tree', path)
            self.statusBar().showMessage('目录导出已加入任务队列')

    def browse_source(self):
        path = QFileDialog.getExistingDirectory(self, '选择默认整理源文件夹')
        if path:
            self.sources.appendPlainText(path)

    def browse_claude(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 Claude Code 原生程序', '', 'Executable (*.exe)')
        if path:
            self.claude.setText(path)

    def save_settings(self):
        if self.worker.busy:
            QMessageBox.information(self, '正在处理', '请等待当前任务完成后保存设置。')
            return False
        try:
            endpoint = self.endpoint.text().strip()
            if endpoint:
                from urllib.parse import urlparse
                url = urlparse(endpoint)
                if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
                    raise ValueError('模型服务地址必须是有效的 HTTP/HTTPS 地址，不能包含凭据')
            self.store.set_sources([x.strip() for x in self.sources.toPlainText().splitlines() if x.strip()])
            for key, value in dict(claude_path=self.claude.text().strip(), model=self.model.text().strip(), endpoint=endpoint, mode=self.mode.currentData(), threshold=self.threshold.value(), auto_apply=self.auto.isChecked(), send_content=self.content.isChecked(), folder_first=self.folder_first.isChecked(), background=self.background.isChecked()).items():
                self.store.set(key, value)
            self.worker.wake.set()
            self.refresh()
            mode, paused, _ = self.worker.sorting_status()
            self.statusBar().showMessage('设置已保存，监控运行中' if mode == SortMode.MONITORING and not paused else '设置已保存，可在工作台控制整理')
            return True
        except Exception as exc:
            QMessageBox.warning(self, '配置无效', str(exc))
            return False

    def save_and_start(self):
        self.auto.setChecked(True)
        if self.save_settings():
            self.start_monitoring(continuous=True)

    def check_claude(self):
        self.claude_check_btn.setEnabled(False)
        self.claude_check_progress.update_progress('正在检测 Claude Code')
        task = ClaudeCheckTask(Path(self.claude.text()))
        task.signals.finished.connect(self.claude_checked)
        QThreadPool.globalInstance().start(task)

    def claude_checked(self, ok, message):
        self.claude_check_progress.update_progress()
        self.claude_check_btn.setEnabled(True)
        if ok:
            QMessageBox.information(self, 'Claude Code 已找到', message + '\n\n此检测确认程序可执行；模型连接与登录状态会在实际分类时验证。')
        else:
            QMessageBox.warning(self, '检测失败', message)

    def undo(self):
        oid = self.selected(self.history)
        if oid:
            self.worker.enqueue('undo', oid)

    def quit_app(self):
        self.worker.stop_sorting()
        if self.worker.has_pending_work():
            QMessageBox.information(self, '等待当前任务', '已停止后续监控。当前分类或文件操作完成后，可再次退出。')
            return
        self.worker.requestInterruption()
        self.worker.wake.set()
        if not self.worker.wait(5000):
            QMessageBox.information(self, '正在退出', '正在停止目录监控，请稍后重试。')
            return
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        event.ignore()
        if self.store.get('background', True) and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray.showMessage('FileAtlas', '程序继续在托盘运行。右键托盘图标可退出。')
        else:
            self.quit_app()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--start-monitoring', action='store_true', help='Start monitoring the saved source folders')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    home = Path(args.data_dir) if args.data_dir else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FileAtlas'
    home.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(home / 'app.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None, 'FileAtlas', '此数据目录已有 FileAtlas 实例运行，请从托盘打开。')
        return
    store = Store(home)
    initialize_local_model(store)
    win = Window(store)
    win.show()
    if args.start_monitoring:
        QTimer.singleShot(0, win.start_monitoring)
    if args.smoke:
        def screenshot():
            win.grab().save(str(home / 'preview.png'))
            win.quit_app()
        QTimer.singleShot(1500, screenshot)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
