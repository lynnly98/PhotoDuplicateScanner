"""Native Windows photo review. Run with: python desktop.py"""
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, QLockFile, QUrl, QTranslator, QLibraryInfo
from PySide6.QtGui import QPixmap, QFont, QFontDatabase, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QCheckBox,
    QListWidget, QComboBox, QScrollArea, QSplitter, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFileDialog, QMessageBox, QProgressBar, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QTabBar, QAbstractItemView, QSizePolicy,
)
from database import BASE, DATA, init
import desktop_data as store
from languages import text, diagnostic
from modern_ui import layout_pages, apply_theme, COPY as MODERN_COPY
from ui_icons import icon
from scanner import CONTROL, ROOTS_FILE
from image_utils import thumbnail
from recycle import prepare, recycle_selected
from exporter import export_xlsx
import folder_cleanup
from media_types import SCAN_MODES
import video_utils


STYLE = '''
QWidget {font-family: "Segoe UI", "Microsoft YaHei UI"; font-size: 13px; color: #243047;}
QMainWindow, #main {background: #f5f7fb;}
QFrame#sidebar, QFrame#inspector, QFrame#footer {background: white; border: 1px solid #e0e5ed; border-radius: 10px;}
QFrame#group {background: white; border: 1px solid #dfe5ee; border-radius: 10px;}
QFrame#photo {background: #fbfcfe; border: 1px solid #dfe5ee; border-radius: 8px;}
QFrame#photo[chosen="true"] {background: #edf5ff; border: 2px solid #1775ed;}
QLabel#heading {font-size: 26px; font-weight: 700; color:#162239;}
QLabel#section {font-size: 16px; font-weight: 600;}
QLabel#muted {color: #65748b; font-size: 12px;}
QLabel#filename {font-weight: 600;}
QLabel#badge {color: #096acb; font-weight:600;}
QPushButton {background: white; border:1px solid #ccd6e4; border-radius:6px; padding:8px 13px;}
QPushButton:hover {background: #edf4ff; border-color:#78abf1;}
QPushButton:disabled {color:#a0a9b8; background:#f1f3f6; border-color:#e1e5ed;}
QPushButton#primary {background:#1272ed; color:white; border:0; font-weight:600; padding:11px 18px;}
QPushButton#primary:hover {background:#075fce;}
QPushButton#primary:disabled {background:#b8c9e1;}
QComboBox {background:white; border:1px solid #ccd6e4; border-radius:6px; padding:7px; min-width:120px;}
QListWidget {background:#f9fbfe; border:1px solid #e0e5ee; border-radius:6px; padding:4px;}
QListWidget::item {padding:10px 3px;}
QScrollArea {border:0; background:transparent;}
QScrollArea > QWidget > QWidget {background:transparent;}
QCheckBox {spacing:8px; padding:5px 0;}
QProgressBar {background:#edf1f7; border:0; border-radius:4px; min-height:9px; max-height:9px;}
QProgressBar::chunk {background:#1681ee; border-radius:4px;}
QTableWidget {background:white; alternate-background-color:#f4f7fb; border:1px solid #dce3ed;}
QHeaderView::section {background:#edf3fa; border:0; padding:8px; font-weight:600;}
'''


def size_text(value):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:,.1f} {unit}'
        value /= 1024


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


def apply_qt_language(language):
    application = QApplication.instance()
    previous = getattr(application, '_photo_translator', None)
    if previous:
        application.removeTranslator(previous)
    translator = QTranslator(application)
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if language == 'zh' and translator.load('qtbase_zh_CN', folder):
        application.installTranslator(translator)
    application._photo_translator = translator


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            logging.exception('Background task failed')
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


class ImageLabel(QLabel):
    clicked = Signal()

    def __init__(self, height=180):
        super().__init__()
        self.original = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, height)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMaximumHeight(height)
        self.setStyleSheet('background:#e9eef5; border-radius:6px; color:#7b8ba1;')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_image(self, path):
        self.original = QPixmap(path) if path else QPixmap()
        self.rescale()

    def rescale(self):
        if not self.original.isNull():
            self.setPixmap(self.original.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.rescale()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ElidedLabel(QLabel):
    """A compact single-line label; full content remains in the tooltip."""
    def __init__(self, value, kind=None):
        super().__init__()
        self.value = value
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setToolTip(value)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.setFixedHeight(20)
        if kind:
            self.setObjectName(kind)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.value,Qt.TextElideMode.ElideMiddle,max(1,self.width())))


class FolderLabel(ElidedLabel):
    activated = Signal()

    def mouseReleaseEvent(self, event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseReleaseEvent(event)


def label(value='', kind=None):
    result = QLabel(value)
    result.setWordWrap(True)
    result.setTextFormat(Qt.TextFormat.PlainText)
    if kind:
        result.setObjectName(kind)
    return result


def button(parent, key, callback, primary=False):
    result = QPushButton(parent.tr(key))
    result.clicked.connect(callback)
    if primary:
        result.setObjectName('primary')
    return result


def table(headers, rows):
    widget = QTableWidget(len(rows), len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setAlternatingRowColors(True)
    widget.setWordWrap(False)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            item = QTableWidgetItem(str(value or ''))
            item.setToolTip(str(value or ''))
            widget.setItem(i, j, item)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.setColumnWidth(0, 150)
    if len(headers) > 1:
        widget.setColumnWidth(1, 420)
    return widget


class ReviewDialog(QDialog):
    """No file operation is possible without this explicit second step."""
    def __init__(self, parent, manifest):
        super().__init__(parent)
        self.setWindowTitle(parent.tr('review'))
        self.resize(900, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(label(parent.tr('review_note')))
        if any(r.get('match_kind') in ('pixels','auto') for r in manifest):layout.addWidget(label(parent.tr('automatic_review')))
        layout.addWidget(table([parent.tr('path'), parent.tr('size'),parent.tr('match')],
                               [(r['path'], size_text(r['size']),parent.tr('match_'+r.get('match_kind','exact'))) for r in manifest]))
        if any(r.get('match_kind')=='similar' for r in manifest):
            layout.addWidget(label(parent.tr('similar_review')))
            layout.addWidget(table([parent.tr('path'),parent.tr('similar_keeper')],[(r['path'],r.get('keeper_path','')) for r in manifest if r.get('match_kind')=='similar']))
        layout.addWidget(label(parent.tr('restore_note'), 'muted'))
        self.check = QCheckBox(parent.tr('confirm_check'))
        self.check.setObjectName('confirm_check')
        layout.addWidget(self.check)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton(parent.tr('cancel'))
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self.confirm = QPushButton(parent.tr('confirm'))
        self.confirm.setObjectName('primary')
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.accept)
        self.check.toggled.connect(self.confirm.setEnabled)
        row.addWidget(self.confirm)
        layout.addLayout(row)


class ResultFolderDialog(QDialog):
    """Choose from compared scan-result folders, never a filesystem browser."""
    def __init__(self, parent, folders):
        super().__init__(parent)
        self.setWindowTitle(parent.tr('result_folder_title'))
        self.resize(800,450)
        layout = QVBoxLayout(self)
        layout.addWidget(label(parent.tr('result_folder_note')))
        self.folders = QListWidget()
        for row in folders:
            self.folders.addItem(row['root']+'  ·  '+parent.tr('result_folder_count',n=row['n']))
            item = self.folders.item(self.folders.count()-1)
            item.setData(Qt.ItemDataRole.UserRole,row['root'])
            item.setToolTip(row['root'])
        layout.addWidget(self.folders)
        buttons = QHBoxLayout()
        cancel = QPushButton(parent.tr('cancel'))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.confirm = QPushButton(parent.tr('review_folder'))
        self.confirm.setObjectName('primary')
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.accept)
        buttons.addWidget(self.confirm)
        layout.addLayout(buttons)
        self.folders.itemSelectionChanged.connect(lambda:self.confirm.setEnabled(bool(self.folders.currentItem())))
        self.folders.itemActivated.connect(lambda *_:self.accept())

    def chosen_folder(self):
        item = self.folders.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


class FolderReviewDialog(QDialog):
    """Paged review of every candidate and its fixed retained copy."""
    def __init__(self, parent, job, results=False):
        super().__init__(parent)
        self.host = parent
        self.job = job
        self.results = results
        self.page = 1
        self.pages = max(1,(job['total']+folder_cleanup.REVIEW_PAGE_SIZE-1)//folder_cleanup.REVIEW_PAGE_SIZE)
        self.setWindowTitle(parent.tr('folder_results' if results else 'folder_review'))
        self.resize(1100,640)
        layout = QVBoxLayout(self)
        layout.addWidget(label(parent.tr('remove_from',path=job['root']),'section'))
        layout.addWidget(label(parent.tr('folder_media',kind=parent.tr('all_media' if job.get('media_type')=='all' else 'videos_tab' if job.get('media_type')=='video' else 'photos_tab')),'section'))
        layout.addWidget(label(parent.tr('match_'+job.get('match_kind','exact')),'section'))
        if job.get('match_kind') in ('pixels','auto'):layout.addWidget(label(parent.tr('automatic_review')))
        layout.addWidget(label(parent.tr('folder_policy' if job.get('mode')=='cross_folder' else 'folder_policy_legacy')))
        if results:
            layout.addWidget(label(parent.tr('folder_summary',done=job['done'],total=job['total'],ok=job['recycled'],failed=job['failed'],remaining=job['total']-job['done']),'section'))
        else:
            layout.addWidget(label(parent.tr('folder_counts',n=job['total'],size=size_text(job['bytes'])),'section'))
        self.body = QVBoxLayout()
        layout.addLayout(self.body,1)
        navigation = QHBoxLayout()
        self.previous = QPushButton(parent.tr('previous'))
        self.next = QPushButton(parent.tr('next'))
        self.page_label = label()
        self.previous.clicked.connect(lambda:self.navigate(-1))
        self.next.clicked.connect(lambda:self.navigate(1))
        navigation.addWidget(self.previous)
        navigation.addWidget(self.page_label)
        navigation.addWidget(self.next)
        layout.addLayout(navigation)
        layout.addWidget(label(parent.tr('restore_note'),'muted'))
        row = QHBoxLayout()
        if not results:
            self.check = QCheckBox(parent.tr('folder_confirm'))
            layout.addWidget(self.check)
            cancel = QPushButton(parent.tr('cancel'))
            cancel.setDefault(True)
            cancel.clicked.connect(self.reject)
            row.addWidget(cancel)
            self.confirm = QPushButton(parent.tr('confirm'))
            self.confirm.setObjectName('primary')
            self.confirm.setAutoDefault(False)
            self.confirm.setEnabled(False)
            self.check.toggled.connect(self.confirm.setEnabled)
            self.confirm.clicked.connect(self.accept)
            row.addWidget(self.confirm)
        else:
            close = QPushButton(parent.tr('close'))
            close.clicked.connect(self.accept)
            row.addWidget(close)
        layout.addLayout(row)
        self.load_page()

    def navigate(self, step):
        self.page = max(1,min(self.pages,self.page+step))
        self.load_page()

    def load_page(self):
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = folder_cleanup.preview(self.job['id'],self.page)
        headers = [self.host.tr('recycle_path'),self.host.tr('keeper_outside' if self.job.get('mode')=='cross_folder' else 'keeper'),self.host.tr('size')]
        values = [(r['path'],r['keeper'],size_text(r['size'])) for r in rows]
        if self.results:
            headers.extend([self.host.tr('state'),self.host.tr('message')])
            values = [v+(self.host.tr(r['state']),diagnostic(self.host.language,r['message'])) for v,r in zip(values,rows)]
        review_table = table(headers,values)
        review_table.horizontalHeader().setStretchLastSection(False)
        review_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        review_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        review_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        if self.results:
            review_table.setColumnWidth(3,110)
            review_table.setColumnWidth(4,200)
        self.body.addWidget(review_table)
        self.page_label.setText(self.host.tr('page',n=self.page,total=self.pages))
        self.previous.setEnabled(self.page>1)
        self.next.setEnabled(self.page<self.pages)


class MainWindow(QMainWindow):
    folder_progress = Signal(int,int,int,int)

    def __init__(self):
        super().__init__()
        init()
        settings = store.read_settings()
        self.language = settings.get('language', 'en')
        if self.language not in ('en', 'zh'):
            self.language = 'en'
        apply_qt_language(self.language)
        self.active_page = 0
        self.match_kind='auto'
        self.theme = settings.get('theme','light')
        if self.theme not in ('light','dark'): self.theme = 'light'
        self.scan_mode=settings.get('scan_mode','photos')
        if self.scan_mode not in SCAN_MODES:
            self.scan_mode='photos'
        self.result_type=settings.get('result_type','photo')
        if self.result_type not in ('photo','video'):
            self.result_type='video' if self.scan_mode=='videos' else 'photo'
        self.thumbnail_size = settings.get('thumbnail_size','small')
        if self.thumbnail_size not in ('small','medium','large'):
            self.thumbnail_size = 'small'
        self.groups_per_page = settings.get('groups_per_page',store.GROUPS_PER_PAGE)
        if self.groups_per_page not in store.PAGE_SIZES:
            self.groups_per_page = store.GROUPS_PER_PAGE
        self.current_columns = None
        self.roots = store.read_roots()
        self.selected = {}
        self.page = 1
        self.sort = 'largest'
        self.member_pages = {}
        self.snapshot = None
        self.scan_status = {}
        self.last_phase = None
        self.scan_process = None
        self.local_worker_running = False
        self.busy = False
        self.folder_running = False
        self.folder_cancel = None
        self.folder_progress.connect(self.update_folder_progress)
        self.lock_busy = False
        self.loading_library = False
        self.library_revision = 0
        self.polling = False
        self.render_id = 0
        self.inspect_id = 0
        self.current_photo = None
        self.jobs = set()
        self.io_pool = QThreadPool(self)
        self.io_pool.setMaxThreadCount(2)
        self.image_pool = QThreadPool(self)
        self.image_pool.setMaxThreadCount(2)
        self.operation_pool = QThreadPool(self)
        self.operation_pool.setMaxThreadCount(1)
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.relayout_cards)
        self.setMinimumSize(1100, 740)
        self.resize(1480, 930)
        self.build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(4000)
        self.poll()
        self.refresh_library()

    def tr(self, key, **values):
        if key in MODERN_COPY:
            return MODERN_COPY[key][1 if self.language=='zh' else 0].format(**values)
        return text(self.language, key, **values)

    def submit(self, pool, function, success, failure=None):
        task = Task(function)
        self.jobs.add(task)
        task.signals.done.connect(success)
        task.signals.failed.connect(failure or self.show_error)
        task.signals.finished.connect(lambda: self.jobs.discard(task))
        pool.start(task)

    def build(self):
        self.render_id += 1
        self.inspect_id += 1
        self.setWindowTitle(self.tr('title') + ' · V2.1')
        self.setWindowIcon(icon('logo'))
        old = self.takeCentralWidget()
        if old:
            old.deleteLater()
        main = QWidget()
        main.setObjectName('main')
        self.setCentralWidget(main)
        outer = QVBoxLayout(main)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label(self.tr('heading'), 'heading'))
        titles.addWidget(label(self.tr('subtitle'), 'muted'))
        header.addLayout(titles, 1)
        header.addStretch()
        header.addWidget(label('Language / 语言'))
        self.language_box = QComboBox()
        self.language_box.setObjectName('language_box')
        self.language_box.addItem('English', 'en')
        self.language_box.addItem('中文', 'zh')
        self.language_box.setCurrentIndex(1 if self.language == 'zh' else 0)
        self.language_box.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_box)
        outer.addLayout(header)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.splitterMoved.connect(lambda *_:self.resize_timer.start(180))
        outer.addWidget(splitter, 1)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setMinimumWidth(230)
        sidebar.setMaximumWidth(320)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(16, 18, 16, 18)
        left.setSpacing(8)
        left.addWidget(label(self.tr('locations'), 'section'))
        self.add_button = button(self, 'add', self.add_folder)
        left.addWidget(self.add_button)
        self.root_list = QListWidget()
        self.root_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.root_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.root_list.setMaximumHeight(140)
        self.root_list.setMinimumHeight(96)
        self.root_list.addItems(self.roots)
        for i in range(self.root_list.count()):
            self.root_list.item(i).setToolTip(self.root_list.item(i).text())
        left.addWidget(self.root_list)
        self.remove_button = button(self, 'remove', self.remove_folder)
        left.addWidget(self.remove_button)
        left.addWidget(label(self.tr('subfolders'), 'muted'))
        left.addWidget(label(self.tr('scan_type'),'section'))
        self.scan_type_box=QComboBox()
        self.scan_type_box.setObjectName('scan_type')
        for mode in SCAN_MODES:
            self.scan_type_box.addItem(self.tr('scan_'+mode),mode)
        self.scan_type_box.setCurrentIndex(SCAN_MODES.index(self.scan_mode))
        self.scan_type_box.currentIndexChanged.connect(self.change_scan_mode)
        left.addWidget(self.scan_type_box)
        self.start_button = button(self, 'start', self.start_scan, True)
        self.start_button.setObjectName('start_scan')
        self.start_button.setStyleSheet('QPushButton {background:#1272ed;color:white;font-weight:600;padding:11px;border-radius:6px;} QPushButton:disabled {background:#b8c9e1;color:#eef2f7;}')
        self.stop_button = button(self, 'stop', self.stop_scan)
        left.addWidget(self.start_button)
        left.addWidget(self.stop_button)
        self.folder_button = button(self,'folder_cleanup',self.clean_folder)
        left.addWidget(self.folder_button)
        self.status_label = label('', 'section')
        self.count_label = label('', 'muted')
        self.progress_label = label('', 'muted')
        self.time_label = label('', 'muted')
        self.rate_label = label('', 'muted')
        self.finish_label = label('', 'muted')
        self.current_folder = label('', 'muted')
        self.current_folder.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.current_folder.setMaximumHeight(52)
        self.current_folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        for widget in (self.status_label,self.count_label,self.progress,self.progress_label,
                       self.time_label,self.finish_label,self.rate_label,self.current_folder):
            left.addWidget(widget)
        left.addWidget(label(self.tr('eta_note'), 'muted'))
        left.addStretch()
        self.export_button = button(self, 'export', self.export_report)
        self.history_button = button(self, 'history', self.show_history)
        left.addWidget(self.export_button)
        left.addWidget(self.history_button)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setMinimumWidth(230)
        sidebar_scroll.setMaximumWidth(320)
        sidebar_scroll.setWidget(sidebar)
        splitter.addWidget(sidebar_scroll)

        centre = QWidget()
        middle = QVBoxLayout(centre)
        middle.setContentsMargins(8, 0, 8, 0)
        self.result_tabs=QTabBar()
        self.result_tabs.setObjectName('media_result_tabs')
        self.result_tabs.addTab(self.tr('photos_tab'))
        self.result_tabs.addTab(self.tr('videos_tab'))
        self.result_tabs.setExpanding(False)
        self.result_tabs.setCurrentIndex(0 if self.result_type=='photo' else 1)
        self.result_tabs.currentChanged.connect(self.change_result_tab)
        middle.addWidget(self.result_tabs)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label(self.tr('automatic_matching'), 'section'))
        toolbar.addStretch()
        self.sort_box = QComboBox()
        self.sort_box.addItem(self.tr('largest'), 'largest')
        self.sort_box.addItem(self.tr('name'), 'name')
        self.sort_box.setCurrentIndex(0 if self.sort == 'largest' else 1)
        self.sort_box.currentIndexChanged.connect(self.sort_changed)
        toolbar.addWidget(self.sort_box)
        self.refresh_button = button(self, 'refresh', self.refresh_library)
        toolbar.addWidget(self.refresh_button)
        middle.addLayout(toolbar)
        display_options = QHBoxLayout()
        display_options.addWidget(label(self.tr('thumbnail_size')))
        self.size_box = QComboBox()
        self.size_box.setObjectName('thumbnail_size')
        self.size_box.setStyleSheet('min-width:70px;')
        for value in ('small','medium','large'):
            self.size_box.addItem(self.tr(value),value)
        self.size_box.setCurrentIndex(('small','medium','large').index(self.thumbnail_size))
        self.size_box.currentIndexChanged.connect(self.change_thumbnail_size)
        display_options.addWidget(self.size_box)
        display_options.addSpacing(16)
        display_options.addWidget(label(self.tr('per_page')))
        self.page_size_box = QComboBox()
        self.page_size_box.setObjectName('groups_per_page')
        self.page_size_box.setStyleSheet('min-width:55px;')
        for number in store.PAGE_SIZES:
            self.page_size_box.addItem(str(number),number)
        self.page_size_box.setCurrentIndex(store.PAGE_SIZES.index(self.groups_per_page))
        self.page_size_box.currentIndexChanged.connect(self.change_page_size)
        display_options.addWidget(self.page_size_box)
        display_options.addStretch()
        middle.addLayout(display_options)
        middle.addWidget(label(self.tr('automatic_note'), 'muted'))
        middle.addWidget(label(self.tr('scope'), 'muted'))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        middle.addWidget(self.scroll, 1)
        navigation = QHBoxLayout()
        self.previous_button = button(self, 'previous', lambda: self.navigate(-1))
        self.next_button = button(self, 'next', lambda: self.navigate(1))
        self.page_label = label()
        navigation.addWidget(self.previous_button)
        navigation.addStretch()
        navigation.addWidget(self.page_label)
        navigation.addStretch()
        navigation.addWidget(self.next_button)
        middle.addLayout(navigation)
        splitter.addWidget(centre)

        inspector = QFrame()
        inspector.setObjectName('inspector')
        inspector.setMinimumWidth(250)
        inspector.setMaximumWidth(390)
        right = QVBoxLayout(inspector)
        right.setContentsMargins(16,18,16,16)
        right.addWidget(label(self.tr('details'), 'section'))
        self.detail_image = ImageLabel(240)
        self.detail_image.setText(self.tr('choose'))
        right.addWidget(self.detail_image)
        self.detail_name = label('', 'section')
        self.detail_name.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        right.addWidget(self.detail_name)
        right.addWidget(label(self.tr('path'), 'muted'))
        self.detail_path = label()
        self.detail_path.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.detail_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right.addWidget(self.detail_path)
        self.detail_size = label()
        self.detail_dimensions = label()
        self.detail_date = label()
        self.detail_duration = label()
        for widget in (self.detail_size,self.detail_dimensions,self.detail_date,self.detail_duration):
            right.addWidget(widget)
        right.addWidget(label(self.tr('match'), 'muted'))
        self.detail_match=label(self.tr('sha'))
        right.addWidget(self.detail_match)
        self.open_button = button(self, 'open_folder', self.open_folder)
        self.open_button.setEnabled(bool(self.current_photo))
        right.addWidget(self.open_button)
        self.play_button=button(self,'play_video',self.play_video)
        self.play_button.setVisible(bool(self.current_photo and self.current_photo.get('media_type')=='video'))
        right.addWidget(self.play_button)
        right.addStretch()
        right.addWidget(label(self.tr('keep_rule'), 'muted'))
        splitter.addWidget(inspector)
        splitter.setSizes([250, 830, 320])
        splitter.setStretchFactor(1, 1)

        footer = QFrame()
        footer.setObjectName('footer')
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(16,12,16,12)
        self.selection_label = label('', 'section')
        bottom.addWidget(self.selection_label)
        self.clear_button = button(self, 'clear', self.clear_selection)
        bottom.addWidget(self.clear_button)
        bottom.addStretch()
        self.activity_label = label(self.tr('recycle_hint'), 'muted')
        bottom.addWidget(self.activity_label)
        self.cancel_folder_button = button(self,'cancel_cleanup',self.cancel_folder_cleanup)
        self.cancel_folder_button.setVisible(self.folder_running)
        bottom.addWidget(self.cancel_folder_button)
        self.recycle_button = button(self, 'recycle', self.review_selection, True)
        self.recycle_button.setObjectName('recycle_button')
        self.recycle_button.setStyleSheet('QPushButton {background:#1272ed;color:white;font-weight:600;padding:11px 18px;border-radius:6px;} QPushButton:disabled {background:#b8c9e1;color:#eef2f7;}')
        bottom.addWidget(self.recycle_button)
        outer.addWidget(footer)
        layout_pages(self, main, outer, centre, inspector, footer)
        self.update_status()
        self.update_selection()
        self.render_library()
        if self.current_photo:
            self.inspect(self.current_photo)

    def navigate_page(self, index):
        self.active_page = index
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        if index == 2:
            self.show_history()
        if index == 1:
            self.resize_timer.start(50)

    def change_theme(self):
        theme = self.theme_box.currentData()
        try:
            store.save_settings(theme=theme)
        except OSError as exc:
            self.show_error(str(exc))
            return
        self.theme = theme
        apply_theme(self)

    def active_match(self):
        return 'auto'

    def change_language(self, index):
        language = self.language_box.itemData(index)
        if language != self.language:
            try:
                store.save_settings(language)
            except OSError as exc:
                self.show_error(str(exc))
                self.language_box.blockSignals(True)
                self.language_box.setCurrentIndex(1 if self.language == 'zh' else 0)
                self.language_box.blockSignals(False)
                return
            self.language = language
            apply_qt_language(language)
            self.build()

    def sort_changed(self):
        self.sort = self.sort_box.currentData()
        self.page = 1
        self.refresh_library()

    def change_scan_mode(self):
        mode=self.scan_type_box.currentData()
        kind={'photos':'photo','videos':'video'}.get(mode,self.result_type)
        try:
            store.save_settings(scan_mode=mode,result_type=kind)
        except OSError as exc:
            self.show_error(str(exc))
            self.build()
            return
        self.scan_mode=mode
        self.set_result_type(kind)

    def change_result_tab(self,index):
        kind='photo' if index==0 else 'video'
        try:
            store.save_settings(result_type=kind)
        except OSError as exc:
            self.show_error(str(exc))
            self.build()
            return
        self.set_result_type(kind)

    def set_result_type(self,kind):
        self.result_type=kind
        self.page=1
        self.member_pages={}
        self.snapshot=None
        self.current_photo=None
        self.build()
        self.refresh_library()

    def change_thumbnail_size(self):
        size = self.size_box.currentData()
        try:
            store.save_settings(thumbnail_size=size)
        except OSError as exc:
            self.show_error(str(exc))
            self.size_box.blockSignals(True)
            self.size_box.setCurrentIndex(('small','medium','large').index(self.thumbnail_size))
            self.size_box.blockSignals(False)
            return
        self.thumbnail_size = size
        self.settings_size.blockSignals(True)
        self.settings_size.setCurrentIndex(self.size_box.currentIndex())
        self.settings_size.blockSignals(False)
        self.render_library()

    def change_page_size(self):
        number = self.page_size_box.currentData()
        try:
            store.save_settings(groups_per_page=number)
        except OSError as exc:
            self.show_error(str(exc))
            self.page_size_box.blockSignals(True)
            self.page_size_box.setCurrentIndex(store.PAGE_SIZES.index(self.groups_per_page))
            self.page_size_box.blockSignals(False)
            return
        self.groups_per_page = number
        self.settings_count.blockSignals(True)
        self.settings_count.setCurrentIndex(self.page_size_box.currentIndex())
        self.settings_count.blockSignals(False)
        self.page = 1
        self.refresh_library()

    def card_columns(self):
        target = {'small':180,'medium':250,'large':350}[self.thumbnail_size]
        available = max(180,self.scroll.viewport().width()-32)
        return max(1,min(6,available//target))

    def relayout_cards(self):
        if hasattr(self,'scroll') and self.snapshot and self.card_columns()!=self.current_columns:
            position = self.scroll.verticalScrollBar().value()
            self.render_library()
            self.scroll.verticalScrollBar().setValue(position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'resize_timer'):
            self.resize_timer.start(180)

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.tr('add'))
        if path:
            self.roots = store.normalized_roots(self.roots + [path])
            self.save_roots()

    def remove_folder(self):
        index = self.root_list.currentRow()
        if index >= 0:
            self.roots.pop(index)
            self.save_roots()

    def save_roots(self):
        try:
            store.atomic_json(ROOTS_FILE, self.roots)
            self.root_list.clear()
            self.root_list.addItems(self.roots)
            for i in range(self.root_list.count()):
                self.root_list.item(i).setToolTip(self.root_list.item(i).text())
            self.update_controls()
        except OSError as exc:
            self.show_error(str(exc))

    def scanning(self):
        return self.lock_busy or bool(self.scan_process and self.scan_process.poll() is None)

    def start_scan(self):
        if self.busy or self.scanning() or store.operation_busy():
            self.show_error(self.tr('busy'))
            return
        if not self.roots:
            self.show_error(self.tr('no_folders'))
            return
        missing = [p for p in self.roots if not Path(p).is_dir()]
        if missing:
            self.show_error(self.tr('missing_folders', paths='\n'.join(missing)))
            return
        try:
            store.atomic_json(ROOTS_FILE, store.normalized_roots(self.roots))
            CONTROL.unlink(missing_ok=True)
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            with (DATA/'scanner.log').open('ab') as log:
                command = [sys.executable,'--scan-worker','--mode',self.scan_mode] if getattr(sys,'frozen',False) else [sys.executable,str(BASE/'scanner.py'),'--mode',self.scan_mode]
                self.scan_process = subprocess.Popen(command,
                    cwd=str(BASE), creationflags=flags, stdout=log, stderr=log)
            (DATA/'worker.pid').write_text(str(self.scan_process.pid), encoding='utf-8')
            self.selected.clear()
            self.local_worker_running = True
            self.last_phase = None
            self.current_photo = None
            self.snapshot = None
            self.build()
            self.poll()
        except Exception as exc:
            self.show_error(str(exc))

    def stop_scan(self):
        try:
            CONTROL.touch()
            self.stop_button.setEnabled(False)
        except OSError as exc:
            self.show_error(str(exc))

    def poll(self):
        if self.polling:
            return
        self.polling = True
        def success(value):
            self.polling = False
            state, locked = value
            phase = state.get('phase')
            local_running = bool(self.scan_process and self.scan_process.poll() is None)
            refresh = (phase != self.last_phase or (self.lock_busy and not locked)
                       or (self.local_worker_running and not local_running) or self.snapshot is None)
            self.local_worker_running = local_running
            self.last_phase = phase
            self.scan_status = state
            self.lock_busy = locked
            self.update_status()
            if refresh and not self.busy and phase not in ('indexing','hashing','image_hashing','video_hashing','similarity_hashing','similarity_grouping'):
                self.refresh_library()
        def failed(error):
            self.polling = False
            self.status_label.setText(self.tr('error'))
            self.status_label.setToolTip(error)
        self.submit(self.io_pool, lambda: (store.status(), store.operation_busy()), success, failed)

    def update_status(self):
        state = self.scan_status
        phase = state.get('phase', 'idle')
        key = 'status_' + phase
        from languages import COPY
        value = self.tr(key) if key in COPY else phase
        scanned_mode=state.get('scan_mode','photos')
        if state.get('started') and scanned_mode in SCAN_MODES:
            value += ' · '+self.tr('scan_'+scanned_mode)
        if phase in ('indexing','hashing','image_hashing','video_hashing','similarity_hashing','similarity_grouping') and not self.scanning():
            value = self.tr('interrupted')
        self.status_label.setText(value)
        self.status_label.setToolTip(diagnostic(self.language, state.get('message') or ''))
        self.progress_label.setText(self.tr('progress', n=state.get('scanned') or 0,
            done=state.get('hash_done') or 0,total=state.get('hash_total') or 0,errors=state.get('errors') or 0))
        if phase in ('complete','complete_with_errors') and state.get('content_skipped',0):
            self.progress_label.setText(self.progress_label.text()+' · '+self.tr('limited_content',n=state['content_skipped']))
        active = phase in ('indexing','hashing','image_hashing','video_hashing','similarity_hashing','similarity_grouping') and self.scanning()
        if active and phase == 'indexing':
            self.progress.setRange(0,0)
        else:
            self.progress.setRange(0,100)
            self.progress.setValue(int(100*(state.get('hash_done') or 0)/max(1,state.get('hash_total') or 0)) if phase in ('hashing','image_hashing','video_hashing','similarity_hashing','similarity_grouping') else (100 if phase.startswith('complete') else 0))
        self.time_label.setText('')
        self.rate_label.setText('')
        self.finish_label.setText('')
        folder = state.get('current_folder') or ''
        self.current_folder.setText(folder if active else '')
        self.current_folder.setToolTip(folder)
        if state.get('started'):
            try:
                current = datetime.now()
                end = datetime.fromisoformat(state['finished']) if state.get('finished') else current
                elapsed = (end - datetime.fromisoformat(state['started'])).total_seconds()
                stage = max(1,(end-datetime.fromisoformat(state.get('phase_started') or state['started'])).total_seconds())
                done = state.get('hash_done') or 0
                eta = ((state.get('hash_total') or 0)-done)*stage/done if active and phase in ('hashing','image_hashing','video_hashing','similarity_hashing','similarity_grouping') and done>=5 else None
                self.time_label.setText(self.tr('timing',elapsed=duration(elapsed),eta=duration(eta) if eta is not None else self.tr('unknown')))
                if eta is not None:
                    self.finish_label.setText(self.tr('finish',value=(current+timedelta(seconds=eta)).strftime('%Y-%m-%d %H:%M')))
                if active:
                    photos = (state.get('scanned') or 0) if phase=='indexing' else done
                    byte_count = (state.get('index_bytes') or 0) if phase=='indexing' else (state.get('hash_bytes') or 0)
                    self.rate_label.setText(self.tr('rates',photos=photos/stage,mb=byte_count/1048576/stage))
            except (ValueError, TypeError):
                pass
        for widget in (self.time_label,self.rate_label,self.finish_label,self.current_folder):
            widget.setVisible(bool(widget.text()))
        if self.snapshot:
            self.count_label.setText(self.tr('indexed',n=self.snapshot['total'])+'\n'+self.tr('groups',n=self.snapshot['count']))
        self.update_controls()

    def update_controls(self):
        scanning = self.scanning()
        enabled = not self.busy
        self.add_button.setEnabled(enabled and not scanning)
        self.remove_button.setEnabled(enabled and not scanning)
        self.start_button.setEnabled(enabled and not scanning and bool(self.roots))
        self.stop_button.setEnabled(enabled and scanning)
        self.export_button.setEnabled(enabled and not scanning)
        self.folder_button.setEnabled(enabled and not scanning and self.scan_status.get('phase') in ('complete','complete_with_errors'))
        self.history_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled and not self.loading_library)
        self.language_box.setEnabled(enabled)
        self.scan_type_box.setEnabled(enabled and not scanning)
        self.result_tabs.setEnabled(enabled)
        self.clear_button.setEnabled(enabled and bool(self.selected))
        self.recycle_button.setEnabled(enabled and not scanning and bool(self.selected) and self.scan_status.get('phase') in ('complete','complete_with_errors'))
        self.sort_box.setEnabled(enabled and not self.loading_library)
        self.size_box.setEnabled(enabled)
        self.page_size_box.setEnabled(enabled and not self.loading_library)
        self.settings_mode.setEnabled(enabled and not scanning)
        self.settings_size.setEnabled(enabled)
        self.settings_count.setEnabled(enabled and not self.loading_library)
        for frame,check in getattr(self,'cards',{}).values():
            check.setEnabled(enabled and not scanning)
        for folder in getattr(self,'folder_links',[]):
            folder.setEnabled(enabled and not scanning)
        if self.snapshot:
            self.previous_button.setEnabled(enabled and not self.loading_library and self.page>1)
            self.next_button.setEnabled(enabled and not self.loading_library and self.page<self.snapshot['pages'])
        else:
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)

    def reset_after_cleanup(self):
        self.page = 1
        self.member_pages = {}
        self.snapshot = None
        # Reads already in progress must not restore pre-deletion results.
        self.library_revision += 1

    def refresh_library(self):
        if self.loading_library:
            return
        self.loading_library = True
        match=self.active_match()
        revision = self.library_revision
        page, sort, members, page_size, kind = self.page, self.sort, dict(self.member_pages), self.groups_per_page,self.result_type
        self.update_controls()
        def success(value):
            self.loading_library = False
            # Ignore a response if sort/page was changed while it was reading.
            if revision != self.library_revision or match!=self.active_match() or (page,sort,members,page_size,kind) != (self.page,self.sort,self.member_pages,self.groups_per_page,self.result_type):
                self.refresh_library()
                return
            self.snapshot = value
            self.page = value['page']
            self.render_library()
            self.update_status()
        def failed(error):
            self.loading_library = False
            if revision != self.library_revision:
                self.refresh_library()
                return
            self.update_controls()
            self.show_error(error)
        self.submit(self.io_pool, lambda: store.library(page,sort,members,page_size,kind,match), success, failed)

    def render_library(self):
        self.render_id += 1
        token = self.render_id
        columns = self.card_columns()
        self.current_columns = columns
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(10 if self.thumbnail_size=='small' else 16)
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(container)
        self.cards = {}
        self.folder_links = []
        if not self.snapshot:
            layout.addWidget(label(self.tr('loading'), 'muted'))
            self.page_label.setText('')
        elif not self.snapshot['groups']:
            layout.addWidget(label(self.tr('unified_empty'), 'muted'))
        else:
            groups_grid = QGridLayout()
            groups_grid.setSpacing(10)
            group_columns = 2 if self.thumbnail_size=='small' and columns>=4 else 1
            group_row = group_column = 0
            for column in range(group_columns):
                groups_grid.setColumnStretch(column,1)
            for offset, group in enumerate(self.snapshot['groups']):
                wide = group_columns>1 and len(group['photos'])>4
                span = group_columns if wide else 1
                if wide and group_column:
                    group_row += 1
                    group_column = 0
                card_columns = columns if wide else max(1,columns//group_columns)
                frame = QFrame()
                frame.setObjectName('group')
                inner = QVBoxLayout(frame)
                margin = 10 if self.thumbnail_size=='small' else 14
                inner.setContentsMargins(margin,margin,margin,margin)
                inner.addWidget(label(self.tr('group',n=(self.page-1)*self.snapshot['groups_per_page']+offset+1,
                    copies=group['n'],size=size_text(group.get('extra_bytes',(group['n']-1)*group['size'])))+' · '+self.tr('videos_tab' if group.get('media_type')=='video' else 'photos_tab'), 'section'))
                if group.get('is_similar'):
                    inner.addWidget(label(self.tr('similar_group',score=group['similarity_score']),'section'))
                else:
                    inner.addWidget(label(self.tr('confirmed_group'),'muted'))
                grid = QGridLayout()
                grid.setSpacing(8 if self.thumbnail_size=='small' else 12)
                for i, photo in enumerate(group['photos']):
                    card = self.make_card(photo,token)
                    grid.addWidget(card,i//card_columns,i%card_columns)
                for column in range(card_columns):
                    grid.setColumnStretch(column,1)
                inner.addLayout(grid)
                if group['n']>store.COPIES_PER_PAGE:
                    row = QHBoxLayout()
                    mp = group['member_page']
                    prev = button(self,'previous',lambda checked=False,g=group: self.members(g,-1))
                    nxt = button(self,'next',lambda checked=False,g=group: self.members(g,1))
                    prev.setEnabled(mp>1)
                    nxt.setEnabled(mp*store.COPIES_PER_PAGE<group['n'])
                    row.addWidget(prev)
                    row.addWidget(label(self.tr('members',a=(mp-1)*store.COPIES_PER_PAGE+1,
                        b=min(group['n'],mp*store.COPIES_PER_PAGE),n=group['n'])))
                    row.addWidget(nxt)
                    inner.addLayout(row)
                groups_grid.addWidget(frame,group_row,group_column,1,span,Qt.AlignmentFlag.AlignTop)
                group_column += span
                if group_column>=group_columns:
                    group_row += 1
                    group_column = 0
            layout.addLayout(groups_grid)
        layout.addStretch()
        if self.snapshot:
            self.summary_label.setText(self.tr('summary_modern',groups=self.snapshot['count'],size=size_text(self.snapshot['bytes'])))
            self.page_label.setText(self.tr('page',n=self.page,total=self.snapshot['pages']))
        self.update_controls()

    def make_card(self, photo, token):
        path = photo['path']
        frame = QFrame()
        frame.setObjectName('photo')
        frame.setProperty('chosen',path in self.selected)
        inner = QVBoxLayout(frame)
        compact = self.thumbnail_size=='small'
        inner.setContentsMargins(6,6,6,6) if compact else inner.setContentsMargins(10,10,10,10)
        inner.setSpacing(3 if compact else 6)
        height = {'small':90,'medium':135,'large':180}[self.thumbnail_size]
        cache_size = {'small':240,'medium':360,'large':480}[self.thumbnail_size]
        preview = ImageLabel(height)
        preview.setObjectName('thumbnail_'+path)
        preview.setText(self.tr('loading'))
        preview.clicked.connect(lambda: self.inspect(photo))
        inner.addWidget(preview)
        name = ElidedLabel(Path(path).name,'filename')
        name.setToolTip(path)
        inner.addWidget(name)
        folder_path = str(Path(path).parent)
        folder = FolderLabel(folder_path,'muted')
        folder.setObjectName('folder_link_'+path)
        folder.setCursor(Qt.CursorShape.PointingHandCursor)
        folder.setStyleSheet('color:#096acb;text-decoration:underline;')
        folder.setToolTip(folder_path+'\n'+self.tr('folder_link_tip'))
        folder.activated.connect(lambda:self.clean_folder(folder_path))
        self.folder_links.append(folder)
        inner.addWidget(folder)
        row = QHBoxLayout()
        row.addWidget(label(size_text(photo['size']),'muted'))
        if photo.get('match_kind')=='similar':row.addWidget(label(self.tr('similar_score',score=photo.get('similarity_score',0)),'muted'))
        row.addStretch()
        view = button(self,'details_button',lambda: self.inspect(photo))
        if compact:
            view.setStyleSheet('padding:3px 7px;')
        row.addWidget(view)
        inner.addLayout(row)
        check = QCheckBox(self.tr('select'))
        check.setObjectName('select_'+path)
        check.setChecked(path in self.selected)
        check.setEnabled(not self.busy and not self.scanning())
        check.toggled.connect(lambda checked: self.choose(photo,checked))
        inner.addWidget(check)
        self.cards[path] = (frame,check)
        def loaded(cached):
            if token != self.render_id:
                return
            preview.setText(self.tr('unavailable') if not cached else '')
            preview.set_image(cached)
        thumbnail_function=video_utils.thumbnail if photo.get('media_type')=='video' else thumbnail
        self.submit(self.image_pool,lambda:thumbnail_function(path,cache_size) if token == self.render_id else None,loaded,lambda _:loaded(None))
        return frame

    def choose(self, photo, checked):
        path = photo['path']
        if checked and len(self.selected)>=100:
            self.cards[path][1].blockSignals(True)
            self.cards[path][1].setChecked(False)
            self.cards[path][1].blockSignals(False)
            self.show_error(self.tr('limit'))
            return
        if checked:
            self.selected[path] = photo
        else:
            self.selected.pop(path,None)
        frame = self.cards[path][0]
        frame.setProperty('chosen',checked)
        frame.style().unpolish(frame)
        frame.style().polish(frame)
        self.update_selection()

    def update_selection(self):
        self.selection_label.setText(self.tr('selected',n=len(self.selected),size=size_text(sum(r['size'] for r in self.selected.values()))))
        self.update_controls()

    def clear_selection(self):
        self.selected.clear()
        for frame,check in self.cards.values():
            check.blockSignals(True)
            check.setChecked(False)
            check.blockSignals(False)
            frame.setProperty('chosen',False)
            frame.style().unpolish(frame)
            frame.style().polish(frame)
        self.update_selection()

    def members(self, group, direction):
        self.member_pages[group['sha256']] = group['member_page']+direction
        self.refresh_library()

    def navigate(self, direction):
        self.page += direction
        self.refresh_library()

    def inspect(self, photo):
        self.inspector_frame.show()
        self.current_photo = photo
        self.detail_match.setText(self.tr('match_similar')+' · '+self.tr('similar_score',score=photo.get('similarity_score',0)) if photo.get('match_kind')=='similar' else self.tr('automatic_matching'))
        self.inspect_id += 1
        token = self.inspect_id
        path = photo['path']
        self.detail_name.setText(Path(path).name)
        self.detail_path.setText(path)
        self.detail_size.setText(self.tr('size')+': '+size_text(photo['size']))
        self.detail_dimensions.setText(self.tr('dimensions')+': '+self.tr('loading'))
        self.detail_date.setText(self.tr('taken')+': '+self.tr('unknown'))
        is_video=photo.get('media_type')=='video'
        self.detail_date.setVisible(not is_video)
        self.detail_duration.setVisible(is_video)
        self.detail_duration.setText(self.tr('duration')+': '+self.tr('loading'))
        self.play_button.setVisible(is_video)
        self.detail_image.set_image(None)
        self.detail_image.setText(self.tr('loading'))
        self.open_button.setEnabled(True)
        def read():
            if is_video:
                return video_utils.details(path,800)
            from PIL import Image
            result = {'cache':thumbnail(path,800),'dimensions':None,'date':None}
            try:
                with Image.open(path) as image:
                    result['dimensions'] = image.size
                    result['date'] = image.getexif().get(36867)
            except (OSError,ValueError):
                pass
            return result
        def loaded(value):
            if token != self.inspect_id:
                return
            self.detail_image.setText('' if value['cache'] else self.tr('unavailable'))
            self.detail_image.set_image(value['cache'])
            dimensions = ' × '.join(str(n) for n in value['dimensions']) if value['dimensions'] else self.tr('unknown')
            self.detail_dimensions.setText(self.tr('dimensions')+': '+dimensions)
            self.detail_date.setText(self.tr('taken')+': '+str(value['date'] or self.tr('unknown')))
            if is_video:
                seconds=value.get('duration')
                self.detail_duration.setText(self.tr('duration')+': '+(duration(seconds) if seconds is not None else self.tr('unknown')))
        self.submit(self.image_pool,read,loaded,lambda _:loaded({'cache':None,'dimensions':None,'date':None}))

    def play_video(self):
        if not self.current_photo or self.current_photo.get('media_type')!='video':
            return
        path=self.current_photo['path']
        if not Path(path).is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            self.show_error(self.tr('no_player'))

    def open_folder(self):
        if not self.current_photo:
            return
        path = self.current_photo['path']
        if not Path(path).exists():
            self.show_error(self.tr('unavailable'))
            return
        if os.name == 'nt':
            subprocess.Popen(['explorer.exe','/select,',os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def set_busy(self, value, key='working'):
        self.busy = value
        self.activity_label.setText(self.tr(key if value else 'recycle_hint'))
        for frame,check in self.cards.values():
            check.setEnabled(not value and not self.scanning())
        self.update_controls()

    def review_selection(self):
        if not self.selected or self.busy or self.scanning():
            return
        paths = list(self.selected)
        modes={p:r.get('match_kind','auto') for p,r in self.selected.items()}
        self.set_busy(True)
        def success(manifest):
            self.set_busy(False)
            dialog = ReviewDialog(self,manifest)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # The service revalidates DB, lock, hashes and retained copies.
                self.set_busy(True)
                self.submit(self.operation_pool,lambda:recycle_selected(manifest),self.recycled,self.operation_failed)
        self.submit(self.operation_pool,lambda:prepare(paths,modes),success,self.operation_failed)

    def clean_folder(self, folder=None):
        if self.busy or self.scanning():
            return
        if not isinstance(folder,str):
            self.set_busy(True,'planning_folder')
            def loaded(folders):
                self.set_busy(False)
                if not folders:
                    self.message(self.tr('folder_cleanup'),self.tr('folder_empty'))
                    return
                dialog = ResultFolderDialog(self,folders)
                if dialog.exec()==QDialog.DialogCode.Accepted and dialog.chosen_folder():
                    self.clean_folder(dialog.chosen_folder())
            kind=self.result_type
            match=self.active_match()
            self.submit(self.io_pool,lambda:store.result_folders(kind,match),loaded,self.operation_failed)
            return
        path = folder
        kind=self.result_type
        match=self.active_match()
        self.set_busy(True,'planning_folder')
        def planned(job):
            self.set_busy(False)
            if not job['total']:
                self.message(self.tr('folder_cleanup'),self.tr('folder_empty'))
                return
            dialog = FolderReviewDialog(self,job)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self.folder_cancel = threading.Event()
                self.folder_running = True
                self.set_busy(True)
                self.cancel_folder_button.setVisible(True)
                self.cancel_folder_button.setEnabled(True)
                self.cancel_folder_button.setText(self.tr('cancel_cleanup'))
                self.submit(self.operation_pool,
                    lambda:folder_cleanup.execute(job['id'],progress=self.folder_progress.emit,cancel=self.folder_cancel),
                    self.folder_completed,self.folder_failed)
        self.submit(self.operation_pool,lambda:folder_cleanup.plan_folder(path,kind,match),planned,self.operation_failed)

    def update_folder_progress(self, done, total, ok, failed):
        if self.folder_running:
            self.activity_label.setText(self.tr('folder_progress',done=done,total=total,ok=ok,failed=failed))

    def cancel_folder_cleanup(self):
        if self.folder_cancel:
            self.folder_cancel.set()
            self.cancel_folder_button.setEnabled(False)
            self.cancel_folder_button.setText(self.tr('stopping'))

    def folder_failed(self, error):
        self.folder_running = False
        self.folder_cancel = None
        self.cancel_folder_button.setVisible(False)
        self.lock_busy = store.operation_busy()
        self.operation_failed(error)
        self.refresh_library()

    def folder_completed(self, job):
        self.folder_running = False
        self.folder_cancel = None
        self.lock_busy = store.operation_busy()
        self.set_busy(False)
        paths = set(self.selected)
        if self.current_photo:
            paths.add(self.current_photo['path'])
        active = store.active_paths(paths)
        self.selected = {p:r for p,r in self.selected.items() if p in active}
        if self.current_photo and self.current_photo['path'] not in active:
            self.current_photo = None
        if job['recycled']:
            self.reset_after_cleanup()
        self.build()
        self.refresh_library()
        FolderReviewDialog(self,job,results=True).exec()

    def operation_failed(self, error):
        self.set_busy(False)
        self.show_error(error)
        self.poll()

    def recycled(self, results):
        self.lock_busy = store.operation_busy()
        self.set_busy(False)
        # Keep unsuccessful selections for review; never retry automatically.
        for result in results:
            if result['result']=='Recycled':
                self.selected.pop(result['path'],None)
        if self.current_photo and any(r['path']==self.current_photo['path'] and r['result']=='Recycled' for r in results):
            self.current_photo = None
        ok = sum(r['result']=='Recycled' for r in results)
        if ok:
            self.reset_after_cleanup()
        self.build()
        self.refresh_library()
        self.show_table(self.tr('results'),self.tr('result_summary',ok=ok,failed=len(results)-ok)+'\n'+self.tr('restore_note'),
            [self.tr('result'),self.tr('path'),self.tr('message')],
            [(self.tr('recycled' if r['result']=='Recycled' else 'not_confirmed'),r['path'],diagnostic(self.language,r['message'])) for r in results])

    def export_report(self):
        if self.busy or self.scanning():
            return
        kind=self.result_type
        match=self.active_match()
        filename='Photo_Duplicates_Report.xlsx' if kind=='photo' else 'Video_Duplicates_Report.xlsx'
        if match=='pixels':filename='Same_Photos_Report.xlsx'
        path,_ = QFileDialog.getSaveFileName(self,self.tr('export'),str(BASE/'reports'/filename),'Excel (*.xlsx)')
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != '.xlsx':
            target = target.with_suffix('.xlsx')
        # QFileDialog has already asked before overwriting an existing target.
        self.set_busy(True,'exporting')
        language = self.language
        def write():
            target.parent.mkdir(parents=True,exist_ok=True)
            temp = target.with_suffix('.xlsx.tmp')
            try:
                temp.write_bytes(export_xlsx(language=language,media_type=kind,match_kind=match))
                os.replace(temp,target)
            finally:
                temp.unlink(missing_ok=True)
            return str(target)
        def done(value):
            self.set_busy(False)
            self.message(self.tr('export'),self.tr('export_done',path=value))
        self.submit(self.operation_pool,write,done,self.operation_failed)

    def show_history(self):
        self.history_button.setEnabled(False)
        def done(value):
            self.history_button.setEnabled(True)
            while self.history_layout.count():
                item = self.history_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            layout = self.history_layout
            state = value['latest_scan']
            from languages import COPY
            key = 'status_' + state.get('phase','idle')
            status = self.tr(key) if key in COPY else state.get('phase','—')
            layout.addWidget(label(self.tr('latest_scan')+': '+str(state.get('started') or '—')+' · '+status))
            layout.addWidget(label(self.tr('history_note')))
            tabs = QTabWidget()
            recycle_rows = [(r['created'],r['path'],self.tr('match_'+r.get('match_kind','exact')),self.tr(r['state']) if r['state'] in ('verifying','requested','recycled','needs_review') else r['state'],diagnostic(self.language,r['message'])) for r in value['recycle']]
            tabs.addTab(table([self.tr('created'),self.tr('path'),self.tr('match'),self.tr('state'),self.tr('message')],recycle_rows),self.tr('recycle_tab'))
            tabs.addTab(table([self.tr('run_id'),self.tr('path'),self.tr('message')],[(r['run_id'],r['path'],diagnostic(self.language,r['error'])) for r in value['errors']]),self.tr('errors_tab'))
            folders = value.get('folders',[])
            jobs_table = table([self.tr('created'),self.tr('path'),self.tr('match'),self.tr('state'),self.tr('result')],
                [(j['created'],j['root'],self.tr('match_'+j.get('match_kind','exact')),self.tr('job_interrupted' if j['state']=='interrupted' else j['state']),self.tr('folder_summary',done=j['done'],total=j['total'],ok=j['recycled'],failed=j['failed'],remaining=j['total']-j['done'])) for j in folders])
            jobs_table.cellDoubleClicked.connect(lambda row,column:FolderReviewDialog(self,folder_cleanup.info(folders[row]['id']),results=True).exec())
            tabs.addTab(jobs_table,self.tr('folder_history'))
            layout.addWidget(tabs)
        self.submit(self.io_pool,store.history,done,lambda error:(self.history_button.setEnabled(True),self.show_error(error)))

    def show_table(self, title, note, headers, rows):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(1000,540)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label(note))
        layout.addWidget(table(headers,rows))
        close = QPushButton(self.tr('close'))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def message(self, title, value, question=False):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(value)
        if question:
            yes = box.addButton(self.tr('yes'),QMessageBox.ButtonRole.YesRole)
            no = box.addButton(self.tr('no'),QMessageBox.ButtonRole.NoRole)
            box.setDefaultButton(no)
            box.exec()
            return box.clickedButton() is yes
        ok = box.addButton(self.tr('ok'),QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(ok)
        box.exec()

    def show_error(self, value):
        self.message(self.tr('error'),diagnostic(self.language,value))

    def closeEvent(self, event):
        self.lock_busy = store.operation_busy()
        if self.busy:
            self.message(self.tr('title'),self.tr('busy'))
            event.ignore()
        elif self.scanning() and not self.message(self.tr('title'),self.tr('closing'),True):
            event.ignore()
        else:
            self.timer.stop()
            # Finish in-flight reads safely before QObject receivers disappear.
            self.image_pool.clear()
            self.io_pool.clear()
            self.image_pool.waitForDone()
            self.io_pool.waitForDone()
            self.operation_pool.waitForDone()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(icon('logo'))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setFont(QFont('Segoe UI',10))
    init()
    logging.basicConfig(filename=DATA/'desktop.log',level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s',encoding='utf-8')
    instance = QLockFile(str(DATA/'desktop.lock'))
    if not instance.tryLock(100):
        language = store.read_settings().get('language','en')
        QMessageBox.information(None,text(language,'title'),
            'Photo Duplicate Scanner is already open.' if language=='en' else '照片重复清理程序已打开。')
        return 1
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
