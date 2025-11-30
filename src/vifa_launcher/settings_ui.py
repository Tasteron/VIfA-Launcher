# SPDX-License-Identifier: GPL-3.0-or-later
#
# VIfA-Launcher - Visual Interface for Applications
# Copyright (C) 2025 Tasteron
#
# This project is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import os
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

import sys
from PyQt5.QtCore import Qt, QProcess, QTimer
from PyQt5.QtGui import QColor, QFont, QGuiApplication, QFontMetrics
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QMessageBox, QRadioButton,
    QLineEdit, QFileDialog, QColorDialog, QSlider, QTabWidget, QWidget,
    QCheckBox, QListWidget, QListWidgetItem, QFontDialog,
    QScrollArea, QFrame, QGridLayout, QAbstractItemView
)

# Local imports (path setup same as original)
if __package__ is None or __package__ == "":
    THIS_DIR = os.path.dirname(os.path.abspath(__file__)); PARENT = os.path.dirname(THIS_DIR)
    if PARENT not in sys.path: sys.path.insert(0, PARENT)
    from vifa_launcher.config.io import load_settings, save_settings, CONFIG_FILE, _DEFAULT_DESKTOP_DIRS
    from vifa_launcher.transitions.registry import registry
    try:
        from vifa_launcher.ui.scroll import attach_adaptive_scroll
    except Exception:
        attach_adaptive_scroll = None
else:
    from .config.io import load_settings, save_settings, CONFIG_FILE, _DEFAULT_DESKTOP_DIRS
    from .transitions.registry import registry
    try:
        from .ui.scroll import attach_adaptive_scroll
    except Exception:
        attach_adaptive_scroll = None


class ModernCard(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.NoFrame)
        self.setObjectName("modernCard")
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 24); layout.setSpacing(16)
        if title:
            t = QLabel(title); t.setObjectName("cardTitle"); layout.addWidget(t)
        self.content_layout = QVBoxLayout(); self.content_layout.setSpacing(12); layout.addLayout(self.content_layout)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = load_settings()

        # Automatic DPI/scaling calculation
        self._ui_scale = self._calc_ui_scale()
        self._bump_global_font(min_px=self._min_readable_px())

        self.setWindowTitle("Preferences")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.setModal(True)
        self.setMinimumSize(self._dp(1000), self._dp(700))
        self.resize(self._dp(1200), self._dp(800))

        app = QApplication.instance()
        try:
            app.screenAdded.connect(self._on_screen_changed)
            app.screenRemoved.connect(self._on_screen_changed)
        except Exception:
            pass

        self._setup_ui()
        self._apply_modern_theme()
        self._load_from_settings()
        self._connect_signals()
        self.on_apply = None

        # Adaptive scroll behavior
        if attach_adaptive_scroll:
            try:
                self._scroll_general.verticalScrollBar().setSingleStep(12)
                self._scroll_appearance.verticalScrollBar().setSingleStep(12)
                self._scroll_advanced.verticalScrollBar().setSingleStep(12)
                self._scroll_dirs.verticalScrollBar().setSingleStep(12)
                self.list_dirs.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
                self.list_dirs.verticalScrollBar().setSingleStep(12)
            except Exception:
                pass

            self._scroll_filter = attach_adaptive_scroll(
                widgets=(self._scroll_general, self._scroll_appearance, self._scroll_advanced, self._scroll_dirs, self.list_dirs),
                sensitivity_getter=self._get_wheel_sensitivity,
                paged_for_trackpad=True,
                gesture_gap_ms=140
            )

    # ---------- Automatic scaling and readability ----------
    def _min_readable_px(self) -> int:
        """Calculate minimum readable font size based on screen DPI"""
        try:
            env_px = int(float(os.getenv("APP_MIN_READABLE_PX", "").strip()))
            if env_px > 0:
                return max(12, min(env_px, 28))
        except Exception:
            pass
        screen = QGuiApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        if dpi < 110:   return 14
        if dpi < 150:   return 16
        if dpi < 200:   return 18
        return 20

    def _calc_ui_scale(self) -> float:
        """Calculate UI scale factor based on DPI and screen resolution"""
        try:
            env_scale = float(os.getenv("APP_UI_SCALE", "").strip() or 0)
            if env_scale > 0:
                return max(0.9, min(env_scale, 2.5))
        except Exception:
            pass
        screen = QGuiApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        base = dpi / 96.0
        extra = 1.0
        if screen:
            g = screen.availableGeometry()
            px = g.width() * g.height()
            if px >= (3840*2160): extra = 1.15
            elif px >= (2560*1440): extra = 1.08
            elif px <= (1366*768): extra = 0.96
            if dpi >= 192: extra *= 0.98
        scale = base * extra
        if not (0.3 < scale < 4.0):
            scale = 1.10
        return float(max(0.9, min(scale, 2.5)))

    def _dp(self, px: int) -> int:
        """Convert pixels to density-independent pixels"""
        return int(round(px * self._ui_scale))

    def _bump_global_font(self, min_px: int = 16):
        """Ensure font size meets minimum readability requirements"""
        f = QApplication.font()
        fm = QFontMetrics(f)
        if fm.height() >= min_px:
            return
        base_pt = f.pointSizeF() if f.pointSizeF() > 0 else float(f.pointSize() or 11)
        ratio = float(min_px) / max(1.0, float(fm.height()))
        f.setPointSizeF(min(26.0, base_pt * ratio * 1.06))
        QApplication.setFont(f)

    def _recompute_scale_and_refresh(self):
        """Recalculate scale and refresh UI when screen configuration changes"""
        old = self._ui_scale
        self._ui_scale = self._calc_ui_scale()
        if abs(self._ui_scale - old) > 0.01:
            self._bump_global_font(min_px=self._min_readable_px())
            self._apply_modern_theme()
            self.setMinimumSize(self._dp(1000), self._dp(700))

    def _on_screen_changed(self, *args):
        """Handle screen configuration changes"""
        self._recompute_scale_and_refresh()

    def _get_wheel_sensitivity(self) -> float:
        """Get wheel sensitivity for scrolling"""
        return 1.0

    # ------------------- UI Setup -------------------
    def _setup_ui(self):
        """Initialize the main UI components"""
        main = QVBoxLayout(self); main.setContentsMargins(0,0,0,0); main.setSpacing(0)

        header = QWidget(); header.setObjectName("headerWidget"); header.setFixedHeight(self._dp(80))
        hl = QHBoxLayout(header); hl.setContentsMargins(self._dp(32), self._dp(20), self._dp(32), self._dp(20))
        tl = QVBoxLayout(); tl.setSpacing(self._dp(4))
        t = QLabel("Preferences"); t.setObjectName("headerTitle"); tl.addWidget(t)
        st = QLabel("Customize the App Launcher preferences according to your needs"); st.setObjectName("headerSubtitle"); tl.addWidget(st)
        hl.addLayout(tl); hl.addStretch(); main.addWidget(header)

        self.tabs = QTabWidget(); self.tabs.setObjectName("mainTabs"); self.tabs.setTabPosition(QTabWidget.North)
        # Remove focus outline from tabs
        try:
            bar = self.tabs.tabBar()
            bar.setFocusPolicy(Qt.NoFocus)
            self.tabs.setFocusPolicy(Qt.NoFocus)
        except Exception:
            pass
        main.addWidget(self.tabs, 1)

        self._create_general_tab()
        self._create_appearance_tab()
        self._create_advanced_tab()
        self._create_directories_tab()

        footer = QWidget(); footer.setObjectName("footerWidget"); footer.setFixedHeight(self._dp(80))
        fl = QHBoxLayout(footer); fl.setContentsMargins(self._dp(32), self._dp(20), self._dp(32), self._dp(20)); fl.setSpacing(self._dp(12))
        self.btn_defaults = QPushButton("Restore Defaults"); self.btn_defaults.setObjectName("secondaryButton"); fl.addWidget(self.btn_defaults)
        fl.addStretch()
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.setObjectName("secondaryButton"); fl.addWidget(self.btn_cancel)
        self.btn_apply = QPushButton("Apply Changes"); self.btn_apply.setObjectName("secondaryButton"); fl.addWidget(self.btn_apply)
        self.btn_save = QPushButton("Save Settings"); self.btn_save.setObjectName("primaryButton"); self.btn_save.setDefault(True); fl.addWidget(self.btn_save)
        main.addWidget(footer)

    def _label(self, text: str) -> QLabel:
        """Create a standardized setting label"""
        lb = QLabel(text); lb.setObjectName("settingLabel"); return lb

    def _create_general_tab(self):
        """Create the General settings tab"""
        self._scroll_general = QScrollArea(); self._scroll_general.setWidgetResizable(True); self._scroll_general.setFrameStyle(QFrame.NoFrame)
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(self._dp(24), self._dp(24), self._dp(24), self._dp(24)); l.setSpacing(self._dp(24))

        card = ModernCard("Animation & Behavior")
        r1 = QHBoxLayout(); r1.setSpacing(self._dp(16))
        r1.addWidget(self._label("Transition Animation:"))
        self.cb_animation = QComboBox(); self.cb_animation.setMinimumWidth(self._dp(200))
        try:
            names = registry.names()
        except Exception:
            names = ["none", "slide", "fade"]
        display = ["No Animation"] + [n.title() for n in names if n != "none"]
        self.cb_animation.addItems(display); r1.addWidget(self.cb_animation); r1.addStretch()
        card.content_layout.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(self._dp(16))
        r2.addWidget(self._label("Animation Duration:"))
        self.sb_duration = QSpinBox(); self.sb_duration.setRange(0,3000); self.sb_duration.setSingleStep(50); self.sb_duration.setSuffix(" ms"); self.sb_duration.setMinimumWidth(self._dp(120))
        r2.addWidget(self.sb_duration); r2.addStretch()
        card.content_layout.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(self._dp(16))
        r3.addWidget(self._label("Preferences Shortcut:"))
        self.cb_shortcut = QComboBox(); self.cb_shortcut.setMinimumWidth(self._dp(150))
        self.cb_shortcut.addItems(["Ctrl+,", "Ctrl+;", "Ctrl+.", "Ctrl+Alt+S", "F1", "F10"])
        r3.addWidget(self.cb_shortcut); r3.addStretch()
        card.content_layout.addLayout(r3)

        l.addWidget(card); l.addStretch()
        self._scroll_general.setWidget(w)
        self.tabs.addTab(self._scroll_general, "General")

    def _create_appearance_tab(self):
        """Create the Appearance settings tab"""
        self._scroll_appearance = QScrollArea(); self._scroll_appearance.setWidgetResizable(True); self._scroll_appearance.setFrameStyle(QFrame.NoFrame)
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(self._dp(24), self._dp(24), self._dp(24), self._dp(24)); l.setSpacing(self._dp(24))

        bg = ModernCard("Background Settings")
        mode = QWidget(); ml = QVBoxLayout(mode); ml.setContentsMargins(0,0,0,0); ml.setSpacing(self._dp(12))
        ml.addWidget(self._label("Background:"))
        self.rb_wp = QRadioButton("System Wallpaper")
        self.rb_image = QRadioButton("Use Custom Image")
        self.rb_color = QRadioButton("Solid Color")
        for rb in (self.rb_wp, self.rb_image, self.rb_color):
            ml.addWidget(rb)
        bg.content_layout.addWidget(mode)

        self.image_row = QWidget(); il = QHBoxLayout(self.image_row); il.setContentsMargins(self._dp(20), self._dp(8), 0, self._dp(8)); il.setSpacing(self._dp(12))
        il.addWidget(self._label("Image Path:"))
        self.le_image = QLineEdit(); self.le_image.setPlaceholderText("Select path to background image..."); il.addWidget(self.le_image, 1)
        btn_browse = QPushButton("Browse"); btn_browse.setObjectName("secondaryButton"); btn_browse.clicked.connect(self._on_browse_clicked); il.addWidget(btn_browse)
        bg.content_layout.addWidget(self.image_row)

        self.blur_row = QWidget(); bl = QHBoxLayout(self.blur_row); bl.setContentsMargins(self._dp(20), self._dp(8), 0, self._dp(8)); bl.setSpacing(self._dp(16))
        bl.addWidget(self._label("Blur:"))
        self.sl_blur = QSlider(Qt.Horizontal); self.sl_blur.setRange(0,100); self.sl_blur.setMinimumWidth(self._dp(200)); bl.addWidget(self.sl_blur)
        self.sb_blur = QSpinBox(); self.sb_blur.setRange(0,100); self.sb_blur.setSuffix(" %"); self.sb_blur.setMinimumWidth(self._dp(80)); bl.addWidget(self.sb_blur)
        bl.addStretch(); bg.content_layout.addWidget(self.blur_row)

        self.color_row = QWidget(); cl = QHBoxLayout(self.color_row); cl.setContentsMargins(self._dp(20), self._dp(8), 0, self._dp(8)); cl.setSpacing(self._dp(12))
        cl.addWidget(self._label("Background Color:"))
        self.le_color = QLineEdit(); self.le_color.setPlaceholderText("#RRGGBB"); self.le_color.setMaximumWidth(self._dp(120)); cl.addWidget(self.le_color)
        btn_pick = QPushButton("Select Color"); btn_pick.setObjectName("secondaryButton"); btn_pick.clicked.connect(self._on_pick_bg_color_clicked); cl.addWidget(btn_pick)
        cl.addStretch(); bg.content_layout.addWidget(self.color_row)

        # Background dimming
        self.darkness_row = QWidget()
        dl = QHBoxLayout(self.darkness_row); dl.setContentsMargins(self._dp(20), self._dp(8), 0, self._dp(8)); dl.setSpacing(self._dp(16))
        dl.addWidget(self._label("Background Dim:"))
        self.sl_darkness = QSlider(Qt.Horizontal); self.sl_darkness.setRange(0, 100); self.sl_darkness.setValue(32); self.sl_darkness.setMinimumWidth(self._dp(200)); dl.addWidget(self.sl_darkness)
        self.sb_darkness = QSpinBox(); self.sb_darkness.setRange(0, 100); self.sb_darkness.setSuffix(" %"); self.sb_darkness.setMinimumWidth(self._dp(80)); self.sb_darkness.setValue(32); dl.addWidget(self.sb_darkness)
        dl.addStretch(); bg.content_layout.addWidget(self.darkness_row)

        l.addWidget(bg)

        font_card = ModernCard("Font & Display")
        fr = QHBoxLayout(); fr.setSpacing(self._dp(12))
        fr.addWidget(self._label("Font Family:"))
        self.le_font_family = QLineEdit(); self.le_font_family.setPlaceholderText("Use system default"); fr.addWidget(self.le_font_family, 1)
        btn_font = QPushButton("Select Font"); btn_font.setObjectName("secondaryButton"); btn_font.clicked.connect(self._on_pick_font_clicked); fr.addWidget(btn_font)
        font_card.content_layout.addLayout(fr)

        fp = QHBoxLayout(); fp.setSpacing(self._dp(24))
        size_group = QHBoxLayout(); size_group.setSpacing(self._dp(8))
        size_group.addWidget(self._label("Size (pt):"))
        self.sb_font_pt = QSpinBox(); self.sb_font_pt.setRange(8, 40); self.sb_font_pt.setSuffix(" pt"); self.sb_font_pt.setMinimumWidth(self._dp(80))
        size_group.addWidget(self.sb_font_pt); fp.addLayout(size_group)
        color_group = QHBoxLayout(); color_group.setSpacing(self._dp(8))
        color_group.addWidget(self._label("Color:"))
        self.le_font_color = QLineEdit(); self.le_font_color.setPlaceholderText("#RRGGBB"); self.le_font_color.setMaximumWidth(self._dp(100)); color_group.addWidget(self.le_font_color)
        btn_font_color = QPushButton("Select"); btn_font_color.setObjectName("secondaryButton"); btn_font_color.clicked.connect(self._on_pick_font_color_clicked); color_group.addWidget(btn_font_color)
        fp.addLayout(color_group)
        font_card.content_layout.addLayout(fp)

        l.addWidget(font_card)
        l.addStretch()
        self._scroll_appearance.setWidget(w)
        self.tabs.addTab(self._scroll_appearance, "Appearance")

    def _create_advanced_tab(self):
        """Create the Advanced settings tab"""
        self._scroll_advanced = QScrollArea(); self._scroll_advanced.setWidgetResizable(True); self._scroll_advanced.setFrameStyle(QFrame.NoFrame)
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(self._dp(24), self._dp(24), self._dp(24), self._dp(24)); l.setSpacing(self._dp(24))

        layout_card = ModernCard("Layout")
        grid = QGridLayout(); grid.setSpacing(self._dp(16)); grid.setColumnStretch(1,1); grid.setColumnStretch(3,1)
        grid.addWidget(QLabel("Items per Page:"), 0, 0)
        self.sb_page_size = QSpinBox(); self.sb_page_size.setRange(5, 200); self.sb_page_size.setMinimumWidth(self._dp(100)); grid.addWidget(self.sb_page_size, 0, 1)
        grid.addWidget(QLabel("Icons per Row:"), 0, 2)
        self.sb_icons_per_row = QSpinBox(); self.sb_icons_per_row.setRange(3, 20); self.sb_icons_per_row.setMinimumWidth(self._dp(100)); grid.addWidget(self.sb_icons_per_row, 0, 3)
        grid.addWidget(QLabel("Icon Size:"), 1, 0)
        self.sb_icon_size = QSpinBox(); self.sb_icon_size.setRange(32, 256); self.sb_icon_size.setSuffix(" px"); self.sb_icon_size.setMinimumWidth(self._dp(100)); grid.addWidget(self.sb_icon_size, 1, 1)
        grid.addWidget(QLabel("Page Margins:"), 1, 2)
        self.sb_grid_lr = QSpinBox(); self.sb_grid_lr.setRange(0, 400); self.sb_grid_lr.setSuffix(" px"); self.sb_grid_lr.setMinimumWidth(self._dp(100)); grid.addWidget(self.sb_grid_lr, 1, 3)
        layout_card.content_layout.addLayout(grid)

        l.addWidget(layout_card)

        filter_card = ModernCard("Filter")
        self.cb_only_res = QCheckBox("Show Only Apps with Icon")
        self.cb_theme_fallback = QCheckBox("Use System Theme as Icon Fallback")
        filter_card.content_layout.addWidget(self.cb_only_res)
        filter_card.content_layout.addWidget(self.cb_theme_fallback)
        l.addWidget(filter_card)
        l.addStretch()
        self._scroll_advanced.setWidget(w)
        self.tabs.addTab(self._scroll_advanced, "Advanced")

    def _create_directories_tab(self):
        """Create the Directories settings tab"""
        self._scroll_dirs = QScrollArea(); self._scroll_dirs.setWidgetResizable(True); self._scroll_dirs.setFrameStyle(QFrame.NoFrame)
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(self._dp(24), self._dp(24), self._dp(24), self._dp(24)); l.setSpacing(self._dp(24))

        dirs_card = ModernCard("Directories")
        info = QLabel("Manage the directories where .desktop files are searched for.")
        info.setObjectName("infoText"); info.setWordWrap(True); dirs_card.content_layout.addWidget(info)
        self.list_dirs = QListWidget(); self.list_dirs.setMinimumHeight(self._dp(300)); self.list_dirs.setSelectionMode(QListWidget.SingleSelection)
        try:
            self.list_dirs.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            self.list_dirs.verticalScrollBar().setSingleStep(12)
        except Exception:
            pass
        dirs_card.content_layout.addWidget(self.list_dirs)
        btn_row = QHBoxLayout(); btn_row.setSpacing(self._dp(12))
        self.btn_add_ddir = QPushButton("Add Directory"); self.btn_add_ddir.setObjectName("primaryButton"); btn_row.addWidget(self.btn_add_ddir)
        self.btn_remove_ddir = QPushButton("Remove"); self.btn_remove_ddir.setObjectName("dangerButton"); btn_row.addWidget(self.btn_remove_ddir)
        btn_row.addStretch(); dirs_card.content_layout.addLayout(btn_row)
        l.addWidget(dirs_card); l.addStretch()
        self._scroll_dirs.setWidget(w)
        self.tabs.addTab(self._scroll_dirs, "Directories")

    # ---------- Theme Application ----------
    def _apply_modern_theme(self):
        """Apply modern theme with automatic dark/light mode detection"""
        app = QApplication.instance()
        palette = app.palette()
        window_color = palette.color(palette.Window)
        is_dark = (0.299 * window_color.red() + 0.587 * window_color.green() + 0.114 * window_color.blue()) < 128

        if is_dark:
            bg_primary = "#1a1a1a"; bg_secondary = "#2d2d30"; bg_tertiary = "#3c3c3c"
            text_primary = "#ffffff"; text_secondary = "#b3b3b3"; text_muted = "#808080"
            accent = "#007acc"; accent_hover = "#106ebe"; border = "#404040"
            danger = "#f14c4c"; success = "#4caf50"
        else:
            bg_primary = "#ffffff"; bg_secondary = "#f8f9fa"; bg_tertiary = "#e9ecef"
            text_primary = "#212529"; text_secondary = "#495057"; text_muted = "#6c757d"
            accent = "#007acc"; accent_hover = "#0056b3"; border = "#dee2e6"
            danger = "#dc3545"; success = "#28a745"

        s  = float(self._ui_scale)
        min_px = self._min_readable_px()
        fs_header_title   = max(min_px+6, int(round(24 * s)))
        fs_header_sub     = max(min_px-2, int(round(14 * s)))
        fs_card_title     = max(min_px-1, int(round(16 * s)))
        fs_body           = max(min_px,   int(round(15 * s)))
        fs_small          = max(min_px-2, int(round(13 * s)))
        pad_sm = max(6,  int(round(8 * s)))
        pad_md = max(8,  int(round(10 * s)))
        pad_lg = max(12, int(round(12 * s)))
        min_h_btn = max(min_px+8, int(round(36 * s)))
        min_h_inp = max(min_px+6, int(round(34 * s)))
        br_small  = max(6,  int(round(8 * s)))
        br_medium = max(8,  int(round(12 * s)))

        stylesheet = f"""
        /* Main Dialog */
        QDialog {{
            background-color: {bg_primary};
            color: {text_primary};
            font-size: {fs_body}px;
        }}
        /* Header */
        #headerWidget {{ background-color: {bg_secondary}; border-bottom: 1px solid {border}; }}
        #headerTitle {{ font-size: {fs_header_title}px; font-weight: 600; color: {text_primary}; margin: 0; }}
        #headerSubtitle {{ font-size: {fs_header_sub}px; color: {text_secondary}; margin: 0; }}
        /* Tabs */
        #mainTabs {{ border: none; background-color: {bg_primary}; font-size: {fs_body}px; }}
        #mainTabs::pane {{ border: none; background-color: {bg_primary}; }}
        #mainTabs QTabBar::tab {{
            background-color: transparent; border: none;
            padding: {pad_md}px {pad_lg}px; margin: 0 2px; border-radius: {br_medium}px;
            font-weight: 500; color: {text_secondary}; min-width: {int(round(110*s))}px;
        }}
        /* Remove focus outline from tabs */
        #mainTabs QTabBar::tab:focus {{ border: none; }}
        #mainTabs QTabBar::tab:selected:focus {{ border: none; }}
        #mainTabs QTabBar::tab:hover:focus {{ border: none; }}
        QTabBar:focus {{ outline: none; }}
        /* Tab appearance */
        #mainTabs QTabBar::tab:selected {{ background-color: {bg_tertiary}; color: {text_primary}; }}
        #mainTabs QTabBar::tab:hover:!selected {{ background-color: {bg_secondary}; color: {text_primary}; }}
        /* Cards */
        #modernCard {{ background-color: {bg_secondary}; border: 1px solid {border}; border-radius: {br_medium}px; margin: 4px; }}
        #cardTitle {{ font-size: {fs_card_title}px; font-weight: 600; color: {text_primary}; margin: 0 0 {max(6,int(round(8*s)))}px 0; }}
        /* Labels */
        #settingLabel {{ font-weight: 500; color: {text_primary}; min-width: {int(round(160*s))}px; }}
        #formDescription {{ color: {text_muted}; font-size: {fs_small}px; }}
        #infoText {{ color: {text_secondary}; font-size: {fs_body}px; padding: {pad_sm}px 0; }}
        /* Inputs */
        QLineEdit, QComboBox, QSpinBox {{
            background-color: {bg_primary}; border: 2px solid {border}; border-radius: {br_small}px;
            padding: {pad_sm}px {pad_md}px; font-size: {fs_body}px; color: {text_primary}; min-height: {min_h_inp}px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {accent}; background-color: {bg_primary}; }}
        QComboBox::drop-down {{ border: none; width: {int(round(34*s))}px; }}
        QComboBox::down-arrow {{ width: {int(round(14*s))}px; height: {int(round(14*s))}px; }}
        /* Buttons */
        #primaryButton {{
            background-color: {accent}; color: white; border: none; border-radius: {br_medium}px;
            padding: {pad_md}px {int(round(26*s))}px; font-weight: 600; font-size: {fs_body}px; min-height: {min_h_btn}px;
        }}
        #primaryButton:hover {{ background-color: {accent_hover}; }}
        #primaryButton:pressed {{ background-color: {accent}; }}
        #secondaryButton {{
            background-color: {bg_tertiary}; color: {text_primary}; border: 1px solid {border}; border-radius: {br_medium}px;
            padding: {pad_sm}px {int(round(22*s))}px; font-weight: 500; font-size: {fs_body}px; min-height: {min_h_btn}px;
        }}
        #secondaryButton:hover {{ background-color: {bg_secondary}; border-color: {accent}; }}
        #dangerButton {{
            background-color: {danger}; color: white; border: none; border-radius: {br_medium}px;
            padding: {pad_sm}px {int(round(22*s))}px; font-weight: 500; font-size: {fs_body}px; min-height: {min_h_btn}px;
        }}
        #dangerButton:hover {{ background-color: #c82333; }}
        /* Checks/Radio */
        QCheckBox, QRadioButton {{ color: {text_primary}; font-size: {fs_body}px; spacing: {int(round(8*s))}px; }}
        QCheckBox::indicator, QRadioButton::indicator {{ width: {int(round(22*s))}px; height: {int(round(22*s))}px; }}
        QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {{
            background-color: {bg_primary}; border: 2px solid {border}; border-radius: {int(round(5*s))}px;
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {accent}; border: 2px solid {accent}; border-radius: {int(round(5*s))}px;
        }}
        QRadioButton::indicator {{ border-radius: {int(round(11*s))}px; }}
        QRadioButton::indicator:checked {{ border-radius: {int(round(11*s))}px; }}
        /* Slider */
        QSlider::groove:horizontal {{ height: {max(4,int(round(7*s)))}px; background-color: {bg_tertiary}; border-radius: {int(round(3*s))}px; }}
        QSlider::handle:horizontal {{
            background-color: {accent}; border: none; width: {int(round(22*s))}px; height: {int(round(22*s))}px;
            margin: -{int(round(8*s))}px 0; border-radius: {int(round(11*s))}px;
        }}
        QSlider::handle:horizontal:hover {{ background-color: {accent_hover}; }}
        /* List */
        QListWidget {{
            background-color: {bg_primary}; border: 1px solid {border}; border-radius: {br_small}px;
            padding: {int(round(4*s))}px; outline: none; font-size: {fs_body}px;
        }}
        QListWidget::item {{
            background-color: transparent; border: none; padding: {pad_sm}px {pad_md}px;
            border-radius: {int(round(6*s))}px; margin: 2px; color: {text_primary};
        }}
        QListWidget::item:selected {{ background-color: {accent}; color: white; }}
        QListWidget::item:hover:!selected {{ background-color: {bg_secondary}; }}
        /* Scrollbars */
        QScrollArea {{ border: none; background-color: {bg_primary}; }}
        QScrollBar:vertical {{
            background-color: {bg_secondary}; width: {int(round(14*s))}px; border-radius: {int(round(7*s))}px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {text_muted}; border-radius: {int(round(7*s))}px; min-height: {int(round(34*s))}px; margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{ background-color: {accent}; }}
        /* Footer */
        #footerWidget {{ background-color: {bg_secondary}; border-top: 1px solid {border}; }}
        /* GroupBox */
        QGroupBox {{
            font-weight: 600; color: {text_primary}; border: 1px solid {border}; border-radius: {br_small}px;
            margin: {int(round(12*s))}px 0; padding-top: {int(round(12*s))}px; font-size: {fs_body}px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; left: {int(round(12*s))}px; padding: 0 {int(round(8*s))}px; background-color: {bg_primary};
        }}
        """
        self.setStyleSheet(stylesheet)

    # ---------- Signal Connections ----------
    def _connect_signals(self):
        """Connect all UI signals to their respective slots"""
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_defaults.clicked.connect(self._on_defaults_clicked)

        self.rb_wp.toggled.connect(self._update_enabled_states)
        self.rb_image.toggled.connect(self._update_enabled_states)
        self.rb_color.toggled.connect(self._update_enabled_states)

        self.sl_blur.valueChanged.connect(self.sb_blur.setValue)
        self.sb_blur.valueChanged.connect(self.sl_blur.setValue)

        self.sl_darkness.valueChanged.connect(self.sb_darkness.setValue)
        self.sb_darkness.valueChanged.connect(self.sl_darkness.setValue)

        self.btn_add_ddir.clicked.connect(self._on_add_ddir_clicked)
        self.btn_remove_ddir.clicked.connect(self._on_remove_ddir_clicked)
        self.list_dirs.itemChanged.connect(self._on_dir_item_changed)
        self.list_dirs.itemSelectionChanged.connect(self._update_remove_button_enabled)

    def _update_enabled_states(self):
        """Update enabled states of background-related controls"""
        use_image = self.rb_image.isChecked()
        use_wp = self.rb_wp.isChecked()
        use_color = self.rb_color.isChecked()
        self.image_row.setVisible(use_image)
        self.blur_row.setVisible(use_image or use_wp)
        self.color_row.setVisible(use_color)
        self.darkness_row.setVisible(True)

    # ---------- Color/Font Dialogs ----------
    def _on_pick_bg_color_clicked(self):
        """Open color picker for background color selection"""
        current = QColor(self.le_color.text() or "#510545")
        if not current.isValid(): current = QColor("#510545")
        color = QColorDialog.getColor(current, self, "Select Background Color")
        if color.isValid(): self.le_color.setText(color.name(QColor.HexRgb))

    def _on_pick_font_clicked(self):
        """Open font dialog for font family selection"""
        current_family = self.le_font_family.text() or QApplication.font().family()
        current_font = QFont(current_family, self.sb_font_pt.value())
        font, ok = QFontDialog.getFont(current_font, self, "Select Font Family")
        if ok:
            self.le_font_family.setText(font.family())
            self.sb_font_pt.setValue(font.pointSize())

    def _on_pick_font_color_clicked(self):
        """Open color picker for font color selection"""
        current = QColor(self.le_font_color.text() or "#FFFFFF")
        if not current.isValid(): current = QColor("#FFFFFF")
        color = QColorDialog.getColor(current, self, "Select Font Color")
        if color.isValid(): self.le_font_color.setText(color.name(QColor.HexRgb))

    # ---------- Data Loading/Saving ----------
    def _load_from_settings(self):
        """Load current settings into the UI form"""
        s = self._settings
        anim = getattr(s, "animation", "slide")
        display = "No Animation" if anim == "none" else anim.title()
        for i in range(self.cb_animation.count()):
            if self.cb_animation.itemText(i) == display:
                self.cb_animation.setCurrentIndex(i); break
        self.sb_duration.setValue(int(getattr(s, "anim_duration_ms", 280)))
        shortcut = getattr(s, "settings_shortcut", "Ctrl+,")
        items = [self.cb_shortcut.itemText(i) for i in range(self.cb_shortcut.count())]
        if shortcut in items: self.cb_shortcut.setCurrentText(shortcut)
        else: self.cb_shortcut.insertItem(0, shortcut); self.cb_shortcut.setCurrentIndex(0)

        mode = getattr(s, "background_mode", "wp_sync")
        if mode == "custom_image": self.rb_image.setChecked(True)
        elif mode == "color": self.rb_color.setChecked(True)
        else: self.rb_wp.setChecked(True)
        self.le_image.setText(getattr(s, "background_custom_path", ""))
        self.le_color.setText(getattr(s, "background_color", "#510545"))
        blur_val = int(getattr(s, "blur_percent", 70)); self.sl_blur.setValue(blur_val); self.sb_blur.setValue(blur_val)

        darkness_val = int(getattr(s, "background_dim_alpha", 80) / 2.55)
        self.sl_darkness.setValue(darkness_val); self.sb_darkness.setValue(darkness_val)

        self.le_font_family.setText(getattr(s, "font_family", ""))
        self.sb_font_pt.setValue(int(getattr(s, "font_point_size", 12)))
        self.le_font_color.setText(getattr(s, "font_color", "#FFFFFF"))

        self.sb_page_size.setValue(int(getattr(s, "page_size", 35)))
        self.sb_icons_per_row.setValue(int(getattr(s, "icons_per_row", 7)))
        self.sb_icon_size.setValue(int(getattr(s, "icon_size", 115)))
        self.sb_grid_lr.setValue(int(getattr(s, "grid_margins_lr", 200)))

        self.cb_only_res.setChecked(bool(getattr(s, "filter_only_apps_with_icon", False)))
        self.cb_theme_fallback.setChecked(bool(getattr(s, "use_theme_fallback", True)))

        self._fill_dirs_list()
        self._update_enabled_states()

    def _fill_dirs_list(self):
        """Populate the directories list with current settings"""
        self.list_dirs.blockSignals(True)
        self.list_dirs.clear()
        s = self._settings
        disabled = set(getattr(s, "desktop_dirs_disabled", []) or [])
        custom = list(getattr(s, "desktop_dirs_custom", []) or [])
        for path in _DEFAULT_DESKTOP_DIRS:
            item = QListWidgetItem(f"📁 {path} (System)")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Unchecked if path in disabled else Qt.Checked)
            item.setData(Qt.UserRole, {"is_system": True, "path": path})
            self.list_dirs.addItem(item)
        for path in custom:
            item = QListWidgetItem(f"📂 {path} (Custom)")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if path not in disabled else Qt.Unchecked)
            item.setData(Qt.UserRole, {"is_system": False, "path": path})
            self.list_dirs.addItem(item)
        self.list_dirs.blockSignals(False)
        self._update_remove_button_enabled()

    def _update_remove_button_enabled(self):
        """Update remove button state based on selection"""
        item = self.list_dirs.currentItem()
        if not item:
            self.btn_remove_ddir.setEnabled(False); return
        info = item.data(Qt.UserRole) or {}
        self.btn_remove_ddir.setEnabled(not info.get("is_system", True))

    def _on_browse_clicked(self):
        """Open file dialog for background image selection"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "",
            "Image files (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All files (*)"
        )
        if path:
            self.le_image.setText(path)

    def _on_add_ddir_clicked(self):
        """Add a new directory to search for .desktop files"""
        path = QFileDialog.getExistingDirectory(self, "Select Directory with .desktop Files")
        if not path: return
        if path in _DEFAULT_DESKTOP_DIRS:
            for i in range(self.list_dirs.count()):
                item = self.list_dirs.item(i); info = item.data(Qt.UserRole) or {}
                if info.get("path") == path: item.setCheckState(Qt.Checked); break
        else:
            if not hasattr(self._settings, 'desktop_dirs_custom'):
                self._settings.desktop_dirs_custom = []
            if path not in self._settings.desktop_dirs_custom:
                self._settings.desktop_dirs_custom.append(path)
            if hasattr(self._settings, 'desktop_dirs_disabled'):
                try: self._settings.desktop_dirs_disabled.remove(path)
                except ValueError: pass
        self._fill_dirs_list()

    def _on_remove_ddir_clicked(self):
        """Remove selected custom directory from search list"""
        item = self.list_dirs.currentItem()
        if not item: return
        info = item.data(Qt.UserRole) or {}
        if info.get("is_system", True): return
        path = info.get("path")
        if hasattr(self._settings, 'desktop_dirs_custom') and path in self._settings.desktop_dirs_custom:
            self._settings.desktop_dirs_custom.remove(path)
        if hasattr(self._settings, 'desktop_dirs_disabled'):
            try: self._settings.desktop_dirs_disabled.remove(path)
            except ValueError: pass
        self._fill_dirs_list()

    def _on_dir_item_changed(self, item):
        """Handle directory item checkbox state changes"""
        info = item.data(Qt.UserRole) or {}
        path = info.get("path")
        if not hasattr(self._settings, 'desktop_dirs_disabled'):
            self._settings.desktop_dirs_disabled = []
        if item.checkState() == Qt.Checked:
            try: self._settings.desktop_dirs_disabled.remove(path)
            except ValueError: pass
        else:
            if path not in self._settings.desktop_dirs_disabled:
                self._settings.desktop_dirs_disabled.append(path)

    def _on_defaults_clicked(self):
        """Reset all settings to default values"""
        reply = QMessageBox.question(
            self, "Reset Preferences",
            "Do you want to reset all preferences to default values?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes: return

        self.cb_animation.setCurrentText("Slide")
        self.sb_duration.setValue(280)
        self.cb_shortcut.setCurrentText("Ctrl+,")

        self.rb_wp.setChecked(True); self.rb_image.setChecked(False); self.rb_color.setChecked(False)
        self.le_image.setText(""); self.le_color.setText("#510545")
        self.sl_blur.setValue(70); self.sb_blur.setValue(70)

        self.sl_darkness.setValue(32); self.sb_darkness.setValue(32)

        self.le_font_family.setText(""); self.sb_font_pt.setValue(12); self.le_font_color.setText("#FFFFFF")

        self.sb_page_size.setValue(35); self.sb_icons_per_row.setValue(7); self.sb_icon_size.setValue(115); self.sb_grid_lr.setValue(200)

        self.cb_only_res.setChecked(False); self.cb_theme_fallback.setChecked(True)

        if hasattr(self._settings, 'desktop_dirs_custom'): self._settings.desktop_dirs_custom = []
        if hasattr(self._settings, 'desktop_dirs_disabled'): self._settings.desktop_dirs_disabled = []
        self._fill_dirs_list(); self._update_enabled_states()

        self._recompute_scale_and_refresh()

    def _read_form(self):
        """Read values from UI form into settings object"""
        s = self._settings
        anim_text = self.cb_animation.currentText()
        s.animation = "none" if anim_text == "No Animation" else anim_text.lower()
        s.anim_duration_ms = int(self.sb_duration.value())
        s.settings_shortcut = self.cb_shortcut.currentText().strip() or "Ctrl+,"

        if self.rb_image.isChecked(): s.background_mode = "custom_image"
        elif self.rb_color.isChecked(): s.background_mode = "color"
        else: s.background_mode = "wp_sync"
        s.background_custom_path = self.le_image.text().strip()
        s.background_color = self.le_color.text().strip() or "#510545"
        s.blur_percent = int(self.sb_blur.value())

        s.background_dim_alpha = int(self.sb_darkness.value() * 2.55)

        s.font_family = self.le_font_family.text().strip()
        s.font_point_size = int(self.sb_font_pt.value())
        s.font_color = self.le_font_color.text().strip() or "#FFFFFF"

        s.page_size = int(self.sb_page_size.value())
        s.icons_per_row = int(self.sb_icons_per_row.value())
        s.icon_size = int(self.sb_icon_size.value())
        s.grid_margins_lr = int(self.sb_grid_lr.value())

        s.filter_only_apps_with_icon = bool(self.cb_only_res.isChecked())
        s.use_theme_fallback = bool(self.cb_theme_fallback.isChecked())

        disabled = []; custom = []
        for i in range(self.list_dirs.count()):
            item = self.list_dirs.item(i)
            info = item.data(Qt.UserRole) or {}
            path = info.get("path")
            if not info.get("is_system", True): custom.append(path)
            if item.checkState() != Qt.Checked: disabled.append(path)
        s.desktop_dirs_custom = custom
        s.desktop_dirs_disabled = disabled

    def _on_apply_clicked(self):
        """Apply changes without closing the dialog"""
        self._read_form()
        self._recompute_scale_and_refresh()

        # Save settings and trigger wallpaper sync
        try:
            save_settings(self._settings)
        except Exception:
            pass

        try:
            py = sys.executable or "python3"
            QProcess.startDetached(py, ["-m", "app_launcher.wallpaper_sync"])
        except Exception:
            pass

        # Auto-refresh after short delay
        try:
            QTimer.singleShot(350, self._recompute_scale_and_refresh)
        except Exception:
            pass

        if callable(getattr(self, "on_apply", None)):
            try:
                self.on_apply(self._settings)
                QMessageBox.information(self, "Applied", "Preferences have been successfully applied.")
            except Exception as e:
                QMessageBox.warning(self, "Apply Error", f"Preferences could not be applied:\n{str(e)}")

    def _on_save_clicked(self):
        """Save settings and close the dialog"""
        self._read_form()
        try:
            save_settings(self._settings)
            QMessageBox.information(self, "Saved", f"Preferences have been successfully saved.\n\nLocation:\n{CONFIG_FILE}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Preferences could not be saved:\n{str(e)}")


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    dialog = SettingsDialog()
    dialog.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
