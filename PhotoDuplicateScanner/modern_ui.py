"""Page layout and appearance for the native desktop application."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPalette
from ui_icons import icon, dropdown_style, refresh_icons
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QHBoxLayout, QStackedWidget, QScrollArea)

COPY = {
    'nav_scan': ('Scan', '扫描'), 'nav_results': ('Duplicates', '重复文件'),
    'nav_history': ('History', '历史记录'), 'nav_settings': ('Settings', '设置'),
    'scan_heading': ('Scan your folders', '扫描文件夹'),
    'scan_subtitle': ('Compare photos and videos across all selected folders.', '一起比较所有选中文件夹中的照片和视频。'),
    'results_heading': ('Duplicates', '重复文件'),
    'results_subtitle': ('Review matches. Keep the memories you want.', '检查重复文件，保留珍贵回忆。'),
    'history_heading': ('Activity history', '操作历史'),
    'history_subtitle': ('Review the latest scan and recent cleanup records.', '查看最近一次扫描及近期清理记录。'),
    'settings_heading': ('Settings', '设置'),
    'settings_subtitle': ('Make the app comfortable to use.', '按您的习惯调整程序。'),
    'display': ('Display', '显示'), 'theme': ('Theme', '主题'),
    'light': ('Light', '浅色'), 'dark': ('Dark', '深色'),
    'language': ('Language', '语言'),
    'preferences': ('Scan preferences', '扫描偏好'),
    'local': ('Your data stays on this computer', '数据保存在本机'),
    'local_note': ('Scan records, settings and thumbnails are stored beside the application.', '扫描记录、设置和缩略图保存在程序所在文件夹。'),
    'readonly': ('Scanning does not change your original files.', '扫描不会修改原始文件。'),
    'cleanup_note': ('Choose a folder from scan results. Keep matching copies in other folders.', '从扫描结果选择文件夹，保留其他文件夹中的相同副本。'),
    'latest_scan': ('Latest scan', '最近一次扫描'),
    'history_limit': ('Recent records: up to 100 recycle actions, 100 errors and 20 folder cleanups.', '近期记录：最多 100 条回收操作、100 条错误及 20 次文件夹清理。'),
    'summary_modern': ('{groups} duplicate groups · {size} extra copies', '{groups} 组重复文件 · {size} 多余副本'),
}

EXTRA_STYLE = '''
QFrame#navigation {background:#edf3fc;border:0;border-radius:14px;}
QPushButton#nav {text-align:left;padding:14px 16px;border:0;background:transparent;font-size:15px;}
QPushButton#nav:checked {background:#dbeafe;color:#165bdf;font-weight:600;}
QFrame#panel {background:white;border:1px solid #e0e7f0;border-radius:12px;}
QFrame#cleanup {background:#eaf4ff;border:1px solid #d9eaff;border-radius:10px;}
QTabBar::tab {background:#f0f4fa;padding:10px 22px;margin:0 6px 4px 0;border-radius:7px;}
QTabBar::tab:selected {background:#2563eb;color:white;}
QTabWidget::pane {border:0;}
QScrollBar:vertical {width:10px;background:transparent;}
QScrollBar::handle:vertical {background:#c6d2e3;border-radius:5px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QComboBox QAbstractItemView {
    background:white; color:#243047; border:1px solid #ccd6e4;
    selection-background-color:#2563eb; selection-color:white;
    outline:0;
}
QComboBox QAbstractItemView::item {padding:7px 10px; min-height:22px;}
QComboBox QAbstractItemView::item:selected {background:#2563eb;color:white;}
QComboBox QAbstractItemView::item:disabled {color:#65748b;}
'''


def apply_theme(window):
    from desktop import STYLE
    style = STYLE + EXTRA_STYLE
    if window.theme == 'dark':
        replacements = {
            '#f5f7fb':'#151c28', '#243047':'#e3eaf6', '#162239':'#f0f4fc',
            'background: white':'background: #202b3c', 'background:white':'background:#202b3c',
            '#fbfcfe':'#243044', '#f9fbfe':'#1b2637', '#edf3fc':'#1a2537',
            '#f0f4fa':'#25334a', '#dbeafe':'#243e66', '#165bdf':'#9bc5ff',
            '#eaf4ff':'#20334e', '#d9eaff':'#334c6c', '#edf5ff':'#263e5e',
            '#65748b':'#b2c1d7', '#dfe5ee':'#39475b', '#e0e5ed':'#39475b',
            '#e0e7f0':'#39475b', '#ccd6e4':'#465873', '#edf4ff':'#2d4160',
            '#f1f3f6':'#283347', '#edf1f7':'#2b394e', '#edf3fa':'#2b394e',
            '#f4f7fb':'#243044', '#dce3ed':'#39475b', '#e0e5ee':'#39475b',
        }
        for old,new in replacements.items():
            style=style.replace(old,new)
    window.setStyleSheet(style + dropdown_style(window.theme))
    # The native popup frame paints its margins from the palette, outside
    # the styled item view. Theme that frame too, including scroll gutters.
    background = QColor('#202b3c' if window.theme=='dark' else '#ffffff')
    foreground = QColor('#e3eaf6' if window.theme=='dark' else '#243047')
    for combo in window.findChildren(QComboBox):
        palette = combo.palette()
        for role in (QPalette.ColorRole.Window,QPalette.ColorRole.Base,QPalette.ColorRole.Button):
            palette.setColor(role,background)
        for role in (QPalette.ColorRole.WindowText,QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText):
            palette.setColor(role,foreground)
        palette.setColor(QPalette.ColorRole.Highlight,QColor('#2563eb'))
        palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#ffffff'))
        combo.setPalette(palette)
        popup = combo.view().window()
        popup.setPalette(palette)
        popup.setAutoFillBackground(True)
    refresh_icons(window)


def layout_pages(w, main, outer, centre, inspector, footer):
    """Reuse existing controls and services; reorganize them into four pages."""
    old_widgets=[]
    def collect(layout):
        while layout.count():
            child=layout.takeAt(0)
            if child.widget():old_widgets.append(child.widget())
            elif child.layout():collect(child.layout())
    while outer.count():
        item=outer.takeAt(0)
        if item.widget():
            old_widgets.append(item.widget())
        elif item.layout():
            collect(item.layout())
    shell=QWidget()
    row=QHBoxLayout(shell)
    row.setContentsMargins(0,0,0,0)
    row.setSpacing(22)
    nav=QFrame(); nav.setObjectName('navigation'); nav.setFixedWidth(180)
    left=QVBoxLayout(nav); left.setContentsMargins(10,18,10,18)
    brand_row=QHBoxLayout(); brand_row.setSpacing(8)
    logo=QLabel(); logo.setPixmap(icon('logo').pixmap(32,32)); brand_row.addWidget(logo)
    brand=QLabel('Photo Duplicate\nScanner'); brand.setStyleSheet('font-weight:600;font-size:12px;')
    brand_row.addWidget(brand,1); left.addLayout(brand_row); left.addSpacing(22)
    w.nav_buttons=[]
    for index,key in enumerate(('nav_scan','nav_results','nav_history','nav_settings')):
        b=QPushButton(w.tr(key)); b.setObjectName('nav'); b.setCheckable(True)
        b.setIconSize(QSize(20,20))
        b.clicked.connect(lambda checked=False,i=index:w.navigate_page(i))
        left.addWidget(b); w.nav_buttons.append(b)
    left.addStretch()
    language_row=QHBoxLayout()
    language_icon=QLabel(); language_icon.setPixmap(icon('globe','#8290a6').pixmap(18,18))
    language_row.addWidget(language_icon); language_row.addWidget(QLabel('English / 中文'),1)
    left.addLayout(language_row)
    row.addWidget(nav)
    w.pages=QStackedWidget(); row.addWidget(w.pages,1)

    def page(title,subtitle):
        content=QWidget(); col=QVBoxLayout(content); col.setContentsMargins(0,6,0,0); col.setSpacing(14)
        heading=QLabel(w.tr(title)); heading.setObjectName('heading'); col.addWidget(heading)
        note=QLabel(w.tr(subtitle)); note.setObjectName('muted'); note.setWordWrap(True); col.addWidget(note)
        return content,col

    def panel(col):
        frame=QFrame(); frame.setObjectName('panel')
        inside=QVBoxLayout(frame); inside.setContentsMargins(22,20,22,20); inside.setSpacing(12)
        col.addWidget(frame)
        return inside

    scan,scan_col=page('scan_heading','scan_subtitle')
    locations=panel(scan_col)
    line=QHBoxLayout(); line.addWidget(QLabel(w.tr('locations')),1); line.addWidget(w.add_button); locations.addLayout(line)
    w.root_list.setMaximumHeight(180); locations.addWidget(w.root_list)
    locations.addWidget(w.remove_button,0,Qt.AlignmentFlag.AlignLeft)
    locations.addWidget(QLabel(w.tr('subfolders')))
    mode_row=QHBoxLayout(); mode_row.addWidget(QLabel(w.tr('scan_type'))); mode_row.addWidget(w.scan_type_box,1); locations.addLayout(mode_row)
    progress=panel(scan_col)
    for widget in (w.status_label,w.progress,w.count_label,w.progress_label,w.time_label,w.finish_label,w.rate_label,w.current_folder):progress.addWidget(widget)
    actions=QHBoxLayout(); actions.addWidget(w.start_button); actions.addWidget(w.stop_button); actions.addStretch(); progress.addLayout(actions)
    progress.addWidget(QLabel(w.tr('readonly')))
    scan_col.addStretch()
    scroller=QScrollArea(); scroller.setWidgetResizable(True); scroller.setWidget(scan); w.pages.addWidget(scroller)

    results,result_col=page('results_heading','results_subtitle')
    export_row=QHBoxLayout(); w.summary_label=QLabel(); w.summary_label.setObjectName('section')
    export_row.addWidget(w.summary_label,1); export_row.addWidget(w.export_button); result_col.addLayout(export_row)
    cleanup=QFrame(); cleanup.setObjectName('cleanup'); clean_row=QHBoxLayout(cleanup)
    note=QLabel(w.tr('cleanup_note')); note.setWordWrap(True); clean_row.addWidget(note,1); clean_row.addWidget(w.folder_button)
    result_col.addWidget(cleanup)
    # A drawer opens only when inspecting a file, leaving room for small cards.
    body=QHBoxLayout(); centre.setParent(results); body.addWidget(centre,1)
    inspector.setParent(results); w.inspector_frame=inspector
    close=QPushButton(w.tr('close')); close.clicked.connect(inspector.hide); inspector.layout().insertWidget(0,close)
    body.addWidget(inspector); inspector.hide(); result_col.addLayout(body,1)
    footer.setParent(results); result_col.addWidget(footer)
    w.recycle_button.setStyleSheet('QPushButton {background:#dc3545;color:white;font-weight:600;padding:12px 18px;border:0;border-radius:8px;} QPushButton:disabled {background:#bbc4d2;color:#f8fafc;}')
    w.pages.addWidget(results)

    history,history_col=page('history_heading','history_subtitle')
    hrow=QHBoxLayout(); hrow.addWidget(QLabel(w.tr('history_limit')),1)
    w.history_button.setParent(history); w.history_button.setText(w.tr('refresh')); hrow.addWidget(w.history_button)
    history_col.addLayout(hrow)
    w.history_content=QWidget(); w.history_layout=QVBoxLayout(w.history_content); w.history_layout.setContentsMargins(0,0,0,0)
    history_col.addWidget(w.history_content,1); w.pages.addWidget(history)

    settings,settings_col=page('settings_heading','settings_subtitle')
    lang=panel(settings_col); lang_row=QHBoxLayout(); lang_row.addWidget(QLabel(w.tr('language')),1); lang_row.addWidget(w.language_box); lang.addLayout(lang_row)
    display=panel(settings_col); title=QLabel(w.tr('display')); title.setObjectName('section'); display.addWidget(title)
    w.theme_box=QComboBox()
    for theme in ('light','dark'):w.theme_box.addItem(w.tr(theme),theme)
    w.theme_box.setCurrentIndex(1 if w.theme=='dark' else 0)
    w.theme_box.currentIndexChanged.connect(w.change_theme)
    # Separate settings controls mirror the result toolbar's saved choices.
    w.settings_size=QComboBox()
    for size in ('small','medium','large'):w.settings_size.addItem(w.tr(size),size)
    w.settings_size.setCurrentIndex(w.size_box.currentIndex())
    w.settings_size.currentIndexChanged.connect(lambda i:w.size_box.setCurrentIndex(i))
    w.settings_count=QComboBox()
    for i in range(w.page_size_box.count()):w.settings_count.addItem(w.page_size_box.itemText(i),w.page_size_box.itemData(i))
    w.settings_count.setCurrentIndex(w.page_size_box.currentIndex())
    w.settings_count.currentIndexChanged.connect(lambda i:w.page_size_box.setCurrentIndex(i))
    for title,control in (('theme',w.theme_box),('thumbnail_size',w.settings_size),('per_page',w.settings_count)):
        line=QHBoxLayout(); line.addWidget(QLabel(w.tr(title)),1); line.addWidget(control); display.addLayout(line)
    preferences=panel(settings_col)
    line=QHBoxLayout(); line.addWidget(QLabel(w.tr('preferences')),1)
    w.settings_mode=QComboBox()
    for i in range(w.scan_type_box.count()):w.settings_mode.addItem(w.scan_type_box.itemText(i),w.scan_type_box.itemData(i))
    w.settings_mode.setCurrentIndex(w.scan_type_box.currentIndex())
    w.settings_mode.currentIndexChanged.connect(lambda i:w.scan_type_box.setCurrentIndex(i))
    line.addWidget(w.settings_mode); preferences.addLayout(line)
    local=panel(settings_col); local.addWidget(QLabel(w.tr('local')))
    note=QLabel(w.tr('local_note')); note.setWordWrap(True); local.addWidget(note)
    settings_col.addStretch()
    scroller=QScrollArea(); scroller.setWidgetResizable(True); scroller.setWidget(settings); w.pages.addWidget(scroller)
    outer.addWidget(shell)
    for widget in old_widgets:
        if widget not in (footer,w.language_box):widget.hide(); widget.deleteLater()
    apply_theme(w)
    w.navigate_page(w.active_page)
