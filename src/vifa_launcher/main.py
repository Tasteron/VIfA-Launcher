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
import sys, json, re, subprocess, unicodedata, shutil, shlex, html
from pathlib import Path
import numpy as np
from PyQt5.QtCore import (
    Qt, QSize, QEvent, QRunnable, QThreadPool, pyqtSignal, QObject,
    QDir, QDirIterator, QRect, QTimer, QProcess, QPropertyAnimation, QElapsedTimer,
    QEasingCurve, QCoreApplication, QFileSystemWatcher, QIODevice, QFile
)
from PyQt5.QtGui import (
    QIcon, QFont, QPixmap, QPainter, QColor, QImage, QKeySequence, QGuiApplication, QTextDocument, QPixmapCache
)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QStackedWidget, QGridLayout, QDialog, QSizePolicy,
    QGraphicsOpacityEffect, QShortcut
)
from .config.io import load_settings, _DEFAULT_DESKTOP_DIRS, get_runtime_paths
from .transitions.registry import registry

# ============================================================================
# EFFECT CONFIGURATION
# ============================================================================
ENABLE_INTRO_ZOOM = True
ZOOM_START_SCALE = 2.2
EFFECT_DURATION = 200  # Duration of the intro zoom effect in milliseconds

# --------------------------------------------------------------------
# Scroll/Gesture Fine-Tuning (adjustable)
# --------------------------------------------------------------------
GESTURE_GAP_MS = 320         # Lockout time after a touchpad gesture (prevents double-trigger)
TRACKPAD_MULTIPLIER = 1.0    # Touchpad delta multiplier (usually 1.0)
TOUCHPAD_STEP_PAGES = 1      # Always exactly 1 page per gesture

# --------------------------------------------------------------------
# Background modes
# --------------------------------------------------------------------
BACKGROUND_MODE_WP     = "wp_sync"     # Sync with wallpaper
BACKGROUND_MODE_IMAGE  = "custom_image" # Use a custom image
BACKGROUND_MODE_COLOR  = "color"       # Use a solid color

# CSS for app icons (hover/focus effects)
APP_ICON_QSS = """
QPushButton {
    border: none;
    background: transparent;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 30);
    border-radius: 12px;
}
QPushButton:focus {
    background-color: rgba(255, 255, 255, 80);
    border-radius: 12px;
    border: 2px solid white;
}
"""

BASE_DIR = Path(__file__).resolve().parent
ICON_SEARCH_PATHS = [
    "/usr/share/pixmaps",
    "/usr/share/icons/hicolor/48x48/apps",
    "/usr/share/icons/hicolor/64x64/apps",
    "/usr/share/icons/hicolor/128x128/apps",
    "/usr/share/icons/hicolor/256x256/apps",
    "/usr/share/icons/hicolor/scalable/apps",
    "/var/lib/flatpak/exports/share/icons",
    "/var/lib/snapd/desktop/icons",
]
CACHE_FILE = Path.home() / ".cache/VIfA-Launcher/apps_v2.json"
CACHE_SCHEMA_VERSION = 4
INDEX_ALL_LOCALES = True
ACCENT_FOLDING = True  # Normalize accented characters for search

def _substitute_field_codes(args, name="", icon=None, desktop_file=None):
    """
    Substitute % codes in desktop file Exec fields according to the Desktop Entry Specification.
    Supported: %i, %c, %k. Unsupported codes are removed.
    """
    out = []
    for a in args:
        a = a.replace("%%", "%")
        if a in {"%f","%F","%u","%U","%d","%D","%n","%N","%v","%m"}:
            continue
        if a == "%i":
            if icon and os.path.isabs(icon):
                out.extend(["--icon", icon])
            continue
        if a == "%c":
            if name:
                out.append(name)
            continue
        if a == "%k":
            if desktop_file:
                out.append(desktop_file)
            continue
        for code in ("%f","%F","%u","%U","%d","%D","%n","%N","%v","%m"):
            a = a.replace(code, "")
        if "%i" in a:
            a = a.replace("%i", icon if (icon and os.path.isabs(icon)) else "")
        a = a.replace("%c", name or "")
        if "%k" in a and desktop_file:
            a = a.replace("%k", desktop_file)
        if a:
            out.append(a)
    return out

# List of terminal emulators to try for wrapping commands
_TERMINAL_CANDIDATES = [
    ["x-terminal-emulator","-e"],
    ["gnome-terminal","--"],
    ["konsole","-e"],
    ["xfce4-terminal","-e"],
    ["mate-terminal","-e"],
    ["tilix","-e"],
    ["lxterminal","-e"],
    ["alacritty","-e"],
    ["kitty","-e"],
    ["xterm","-e"],
]

def _wrap_in_terminal(argv):
    """
    Wrap a command in a terminal emulator if it's not already a terminal.
    """
    if not argv: return argv
    prog = shutil.which(argv[0]) or argv[0]
    base = os.path.basename(prog).lower()
    if base in {"gnome-terminal","konsole","xfce4-terminal","mate-terminal","tilix","lxterminal","alacritty","kitty","xterm","x-terminal-emulator"}:
        return argv
    for cand in _TERMINAL_CANDIDATES:
        term = shutil.which(cand[0])
        if term:
            return [term] + cand[1:] + argv
    return argv

def _normalize_token(s: str) -> str:
    """
    Normalize a string for search: NFKC normalization, casefolding, and optional accent folding.
    """
    if not s: return ""
    s = unicodedata.normalize("NFKC", s).casefold()
    if ACCENT_FOLDING:
        s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return s

def _parse_qcolor(s: str, default="#202020") -> QColor:
    """
    Parse a color string into a QColor, falling back to default if invalid.
    """
    c = QColor(s)
    if not c.isValid(): c = QColor(default)
    return c

class AnimatedStackedWidget(QStackedWidget):
    """
    A QStackedWidget with animated transitions between pages.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        s = load_settings()
        self.animation_duration = int(getattr(s, "anim_duration_ms", 280))
        self._strategy = registry.get(getattr(s, "animation", "slide"))
        self._anim_group = None
        self.is_animating = False

    def set_strategy_by_name(self, name: str):
        """
        Set the animation strategy by name (e.g., 'slide', 'fade').
        """
        self._strategy = registry.get(name or "slide")

    def set_animation_duration(self, ms: int):
        """
        Set the duration of the animation in milliseconds.
        """
        self.animation_duration = int(ms)

    def setCurrentIndexAnimated(self, index: int):
        """
        Switch to the page at `index` with animation.
        """
        if index == self.currentIndex() or self.is_animating: return
        if index < 0 or index >= self.count(): return
        if self.width() <= 0 or self.height() <= 0 or self.currentWidget() is None:
            self.setCurrentIndex(index); return
        self.is_animating = True
        try:
            grp = self._strategy.start(self, index, self.animation_duration)
        except Exception:
            grp = None
        if not hasattr(grp, "finished"):
            self.setCurrentIndex(index); self.is_animating = False; self._anim_group = None; return
        self._anim_group = grp
        def on_finished():
            try:
                old = self.currentWidget()
                if old and old is not self.currentWidget():
                    old.hide()
            finally:
                self.is_animating = False
                self._anim_group = None
        try:
            grp.finished.connect(on_finished); grp.start()
        except Exception:
            self.setCurrentIndex(index)
            self.is_animating = False
            self._anim_group = None

class AppLoadSignals(QObject):
    """
    Signals for asynchronous app loading.
    """
    finished = pyqtSignal(list)  # [(name, icon_id, cmd, search_blob, workdir, terminal, desktop_file)]

def _locale_chain():
    """
    Build a list of locale preferences for desktop file field selection.
    """
    langs = []; language = os.environ.get("LANGUAGE", "")
    if language: langs.extend([p for p in language.split(":") if p])
    lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    if lang:
        lang = lang.split(".")[0]
        if lang and lang not in langs: langs.append(lang)
        base = lang.split("_")[0]
        if base and base not in langs: langs.append(base)
    if "en" not in langs: langs.append("en")
    seen=set(); result=[]
    for l in langs:
        if l not in seen: seen.add(l); result.append(l)
    return result

def _remove_suffix(s: str, suffix: str) -> str:
    """
    Remove `suffix` from `s` if present.
    """
    return s[: -len(suffix)] if s.endswith(suffix) else s

class AppLoader(QRunnable):
    """
    Load application data from .desktop files in background.
    """
    def __init__(self):
        super().__init__()
        self.s = AppLoadSignals()
        self.locale_pref = _locale_chain()
        self.locale_sig = "|".join(self.locale_pref)

    @staticmethod
    def _fingerprint(p: str):
        """
        Generate a fingerprint for a file based on mtime and size.
        """
        try:
            st = os.stat(p); return f"{int(st.st_mtime)}:{st.st_size}"
        except FileNotFoundError:
            return None

    @staticmethod
    def _find_icon_file(icon_name: str):
        """
        Find the absolute path to an icon file by name.
        """
        if not icon_name: return None
        if os.path.isabs(icon_name):
            if os.path.exists(icon_name): return icon_name
            for ext in ("",".png",".svg",".xpm"):
                p = icon_name + ext
                if os.path.exists(p): return p
            return None
        for base in ICON_SEARCH_PATHS:
            if not os.path.isdir(base): continue
            for ext in ("",".png",".svg",".xpm"):
                candidate = os.path.join(base, icon_name + ext)
                if os.path.exists(candidate): return candidate
        return None

    def _read_desktop_file(self, full_path: str):
        """
        Parse a .desktop file and extract relevant fields.
        """
        name_default = None; icon_name = None; cmd = None; try_exec = None
        workdir = None; terminal = False
        fields = {"Name": {}, "GenericName": {}, "Comment": {}, "Keywords": {}}
        in_entry = False
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith("["):
                        in_entry = (line.lower() == "[desktop entry]"); continue
                    if not in_entry: continue
                    if line.startswith("Name="): name_default = line.split("=",1)[1]
                    elif line.startswith("Icon="): icon_name = line.split("=",1)[1]
                    elif line.startswith("Exec="): cmd = line.split("=",1)[1]
                    elif line.startswith("TryExec="): try_exec = line.split("=",1)[1]
                    elif line.startswith("Path="): workdir = line.split("=",1)[1]
                    elif line.lower().startswith("terminal="):
                        val = line.split("=",1)[1].strip().lower(); terminal = val in ("1","true","yes","on")
                    for key in ("Name","GenericName","Comment"):
                        prefix = key + "["
                        if line.startswith(prefix) and "]=" in line:
                            loc, val = line[len(prefix):].split("]=",1); fields[key][loc]=val
                        elif line.startswith(key+"="):
                            val = line.split("=",1)[1]; fields[key][""]=val
                    xfull = "X-GNOME-FullName"; prefix = xfull+"["
                    if line.startswith(prefix) and "]=" in line:
                        loc, val = line[len(prefix):].split("]=",1); fields["Name"][loc]=val
                    elif line.startswith(xfull+"="):
                        val = line.split("=",1)[1]; fields["Name"][""]=val
                    for kname in ("Keywords","X-GNOME-Keywords","X-KDE-Keywords"):
                        prefix = kname+"["
                        if line.startswith(prefix) and "]=" in line:
                            loc, val = line[len(prefix):].split("]=",1)
                            merged = ";".join(list(filter(None,[fields["Keywords"].get(loc,""), val])))
                            fields["Keywords"][loc]=merged
                        elif line.startswith(kname+"="):
                            val = line.split("=",1)[1]
                            merged = ";".join(list(filter(None,[fields["Keywords"].get("", ""), val])))
                            fields["Keywords"][""]=merged
        except Exception:
            return None, None, None, "", None, False, full_path
        display_name = None
        for loc in self.locale_pref + [""]:
            if loc in fields["Name"]:
                display_name = fields["Name"][loc]; break
        if not display_name: display_name = name_default
        icon_id = None
        if icon_name:
            icon_path = self._find_icon_file(icon_name)
            icon_id = icon_path if icon_path else icon_name
        def values_for_all_locales(dct):
            return list(dct.values())
        terms = []
        for key in ("Name","GenericName","Comment"): terms.extend(values_for_all_locales(fields[key]))
        kws = []
        kv = values_for_all_locales(fields["Keywords"])
        for v in kv: kws.extend([x for x in v.split(";") if x])
        if cmd: terms.append(cmd)
        if try_exec: terms.append(try_exec)
        desktop_id = os.path.basename(full_path).lower()
        desktop_id = desktop_id[:-8] if desktop_id.endswith(".desktop") else desktop_id
        if desktop_id: terms.append(desktop_id)
        normalized, seen = [], set()
        for t in terms:
            tl = _normalize_token((t or "").strip())
            if tl and tl not in seen: seen.add(tl); normalized.append(tl)
        search_blob = " ".join(normalized)
        return display_name, icon_id, cmd, search_blob, workdir, terminal, full_path

    def _iter_effective_dirs(self):
        """
        Iterate over all directories that may contain .desktop files.
        """
        s = load_settings()
        defaults = _DEFAULT_DESKTOP_DIRS
        disabled = set(getattr(s, "desktop_dirs_disabled", []) or [])
        custom = list(getattr(s, "desktop_dirs_custom", []) or [])
        seen = set()
        for p in defaults + custom:
            if not p or p in disabled or p in seen: continue
            seen.add(p); yield p

    def run(self):
        """
        Load and cache application data.
        """
        cache = {}
        if CACHE_FILE.exists():
            try:
                cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                cache = {}
        apps = {}
        changed = False
        for path in self._iter_effective_dirs():
            if not os.path.isdir(path):
                continue
            it = QDirIterator(path, ["*.desktop"], QDir.Files, QDirIterator.NoIteratorFlags)
            while it.hasNext():
                full_path = it.next()
                fp = self._fingerprint(full_path)
                entry = cache.get(full_path)
                name = icon_id = cmd = search_blob = workdir = None
                terminal = False
                need_reparse = True
                if entry and entry.get("fp") == fp:
                    if (entry.get("search_blob")
                        and entry.get("loc") == self.locale_sig
                        and entry.get("ver") == CACHE_SCHEMA_VERSION
                        and bool(entry.get("idx_all")) is True
                        and bool(entry.get("acc_fold")) is True):
                        name = entry.get("name")
                        cmd = entry.get("cmd")
                        icon_id = entry.get("icon_id")
                        search_blob = entry.get("search_blob", "")
                        workdir = entry.get("workdir")
                        terminal = bool(entry.get("terminal", False))
                        need_reparse = False
                if need_reparse:
                    name, icon_id, cmd, search_blob, workdir, terminal, _df = self._read_desktop_file(full_path)
                    if name and cmd:
                        changed = True
                        cache[full_path] = {
                            "fp": fp, "name": name, "cmd": cmd, "icon_id": icon_id, "search_blob": search_blob,
                            "workdir": workdir, "terminal": terminal,
                            "loc": self.locale_sig, "ver": CACHE_SCHEMA_VERSION, "idx_all": True, "acc_fold": True,
                        }
                if name and cmd:
                    key = f"{name}:{cmd}"
                    if key not in apps:
                        apps[key] = (name, icon_id, cmd, search_blob, workdir, terminal, full_path)
        if changed:
            try:
                CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
            except Exception:
                pass
        app_list = sorted(apps.values(), key=lambda x: (x[0] or "").lower())
        self.s.finished.emit(app_list)

def _trim_alpha_borders(pix: QPixmap) -> QPixmap:
    """
    Trim transparent borders from a QPixmap.
    """
    if pix.isNull(): return pix
    img = pix.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    if w == 0 or h == 0: return pix
    ptr = img.bits(); ptr.setsize(img.byteCount())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, img.bytesPerLine())
    alpha = arr[:, 3:3 + 4 * w:4]
    rows = np.where(alpha.max(axis=1) > 0)[0]
    cols = np.where(alpha.max(axis=0) > 0)[0]
    if rows.size == 0 or cols.size == 0: return pix
    top, bottom = int(rows[0]), int(rows[-1])
    left, right = int(cols[0]), int(cols[-1])
    return pix.copy(left, top, right - left + 1, bottom - top + 1)

def _rasterize_icon_uniform(icon: QIcon, size: int) -> QIcon:
    """
    Rasterize an icon to a uniform size, preserving aspect ratio and trimming transparent borders.
    """
    if icon.isNull(): return icon
    base = icon.pixmap(size * 2, size * 2)
    if base.isNull(): return icon
    cropped = _trim_alpha_borders(base)
    target = QPixmap(size, size); target.fill(Qt.transparent)
    painter = QPainter(target); painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    try:
        margin = int(size * 0.05); avail = size - 2 * margin
        sw, sh = cropped.width(), cropped.height()
        if sw <= 0 or sh <= 0: return icon
        if sw >= sh:
            dw, dh = avail, max(1, int(avail * sh / max(1, sw)))
        else:
            dh, dw = avail, max(1, int(avail * sw / max(1, sh)))
        x = (size - dw) // 2; y = (size - dh) // 2
        painter.drawPixmap(QRect(x, y, dw, dh), cropped)
    finally:
        painter.end()
    return QIcon(target)

def _draw_placeholder_icon(size: int) -> QIcon:
    """
    Draw a placeholder icon (a square with an X).
    """
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
    try:
        r = min(size, size) - 2
        p.setBrush(QColor(255,255,255,40)); p.setPen(QColor(255,255,255,90))
        p.drawRoundedRect(1,1,r-2,r-2,12,12)
        p.drawLine(int(size*0.25), int(size*0.25), int(size*0.75), int(size*0.75))
        p.drawLine(int(size*0.75), int(size*0.25), int(size*0.25), int(size*0.75))
    finally:
        p.end()
    return QIcon(pm)

def _fallback_icon() -> QIcon:
    """
    Return a fallback icon if no other icon is available.
    """
    for path in [
        "/usr/share/icons/hicolor/48x48/apps/utilities-terminal.png",
        "/usr/share/pixmaps/unknown.png",
        "/usr/share/icons/gnome/48x48/status/image-missing.png",
    ]:
        if os.path.exists(path):
            return QIcon(path)
    ico = QIcon.fromTheme("application-x-executable")
    if not ico.isNull():
        return ico
    return _draw_placeholder_icon(64)

def _icon_is_resolvable(icon_id, use_theme_fallback=True):
    """
    Check if an icon ID can be resolved to an actual icon file or theme icon.
    """
    if not icon_id:
        return False
    if os.path.isabs(icon_id):
        if os.path.exists(icon_id): return True
        for ext in ("",".png",".svg",".xpm"):
            if os.path.exists(icon_id+ext): return True
        return False
    for base in ICON_SEARCH_PATHS:
        if not os.path.isdir(base): continue
        for ext in ("",".png",".svg",".xpm"):
            cand = os.path.join(base, icon_id+ext)
            if os.path.exists(cand): return True
    if use_theme_fallback and "/" not in (icon_id or ""):
        if QIcon.hasThemeIcon(icon_id): return True
        ic = QIcon.fromTheme(icon_id)
        if not ic.isNull(): return True
    return False

def _icon_from_id(icon_id, size, use_theme_fallback=True) -> QIcon:
    """
    Load an icon from an ID, falling back to a placeholder if necessary.
    """
    if not icon_id:
        return _rasterize_icon_uniform(_fallback_icon(), size)
    if os.path.isabs(icon_id) and os.path.exists(icon_id):
        return _rasterize_icon_uniform(QIcon(icon_id), size)
    icon = QIcon.fromTheme(icon_id) if use_theme_fallback else QIcon()
    if icon.isNull():
        if os.path.exists(icon_id):
            icon = QIcon(icon_id)
    if icon.isNull():
        for base in ICON_SEARCH_PATHS:
            for ext in ("",".png",".svg",".xpm"):
                p = os.path.join(base, icon_id+ext)
                if os.path.exists(p):
                    icon = QIcon(p); break
            if not icon.isNull(): break
    if icon.isNull():
        icon = _fallback_icon()
    return _rasterize_icon_uniform(icon, size)

class SearchLineEdit(QLineEdit):
    """
    Custom QLineEdit for the search bar with arrow key signals.
    """
    arrowDown = pyqtSignal(); arrowUp = pyqtSignal(); arrowLeft = pyqtSignal(); arrowRight = pyqtSignal(); enterPressed = pyqtSignal()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.route_lr_to_launcher = True

    def keyPressEvent(self, e):
        k = e.key()
        is_paste = e.matches(QKeySequence.Paste)
        if (e.text() and not e.text().isspace()) or is_paste or k in (Qt.Key_Backspace, Qt.Key_Delete):
            self.route_lr_to_launcher = False
        if k == Qt.Key_Left:
            if self.route_lr_to_launcher:
                self.arrowLeft.emit(); e.accept(); return
            return super().keyPressEvent(e)
        if k == Qt.Key_Right:
            if self.route_lr_to_launcher:
                self.arrowRight.emit(); e.accept(); return
            return super().keyPressEvent(e)
        if k == Qt.Key_Down:
            self.route_lr_to_launcher = True
            self.arrowDown.emit(); e.accept(); return
        if k == Qt.Key_Up:
            self.arrowUp.emit(); e.accept(); return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self.enterPressed.emit(); e.accept(); return
        super().keyPressEvent(e)

class AppIcon(QPushButton):
    """
    Button representing an application icon.
    """
    def __init__(self, icon: QIcon, command: str, launcher, icon_size: int):
        super().__init__()
        self.setIcon(icon)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(icon_size + 10, icon_size + 10)
        self.setFocusPolicy(Qt.NoFocus)
        self.command = command
        self.launcher = launcher
        self.clicked.connect(self.launch)
        self.setStyleSheet(APP_ICON_QSS)
        self._launch_meta = {}

    def launch(self):
        """
        Launch the application associated with this icon.
        """
        meta = getattr(self, "_launch_meta", {}) or {}
        self.launcher.launch_cmd(self.command,
                                 workdir=meta.get("workdir"),
                                 terminal=bool(meta.get("terminal", False)),
                                 name=str(meta.get("name") or ""),
                                 icon_id=meta.get("icon_id"),
                                 desktop_file_path=meta.get("desktop_file_path"))

# --- Helper for RichText label with robust line breaking ---
def _label_html(text: str) -> str:
    """
    Convert text to HTML with robust line breaking and centering.
    """
    safe = html.escape(text or "")
    return (
        "<div style='text-align:center;"
        "overflow-wrap:anywhere;word-wrap:break-word;word-break:break-word;"
        "white-space:normal;'>"
        f"{safe}</div>"
    )

class AppLauncher(QDialog):
    """
    Main application launcher dialog.
    """
    # --- Helpers: cache-busting pixmap load & swap to wp-o.jpg ---
    def _load_pixmap_nocache(self, path: str) -> QPixmap:
        """
        Load a pixmap, bypassing the cache.
        """
        try:
            f = QFile(path)
            if not f.open(QIODevice.ReadOnly):
                return QPixmap()
            data = f.readAll()
            f.close()
            pm = QPixmap()
            pm.loadFromData(data)
            return pm
        except Exception:
            return QPixmap()

    def _swap_to_wp_o_if_ready(self, readd=None):
        """
        Swap background to wp-o.jpg if it exists.
        """
        try:
            prefer = str(self.runtime_paths["wp_o"])
            if os.path.exists(prefer):
                self._bg_path = prefer
                self._bg_source = None
                self._bg_file_mtime = None
                self._update_background(force=True)
            if callable(readd):
                readd()
        except Exception:
            if callable(readd):
                readd()

    def __init__(self):
        super().__init__()
        self.setObjectName("Launcher")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowState(Qt.WindowFullScreen)
        s = load_settings()
        self.bg_mode = getattr(s, "background_mode", BACKGROUND_MODE_WP)
        self.bg_custom_path = getattr(s, "background_custom_path", "") or ""
        self.bg_color_str = getattr(s, "background_color", "#202020")
        self.only_resolvable = bool(getattr(s, "filter_only_apps_with_icon", False))
        self.use_theme_fallback = bool(getattr(s, "use_theme_fallback", True))
        self.page_size = int(getattr(s, "page_size", 35))
        the_icons_per_row = int(getattr(s, "icons_per_row", 7))
        self.icons_per_row = max(1, the_icons_per_row)
        self.icon_size = int(getattr(s, "icon_size", 115))
        self.grid_lr = int(getattr(s, "grid_margins_lr", 200))
        self.font_family = str(getattr(s, "font_family", ""))
        self.font_pt = int(getattr(s, "font_point_size", 12))
        self.font_color = str(getattr(s, "font_color", "#FFFFFF"))
        self.wheel_sensitivity = float(getattr(s, "wheel_sensitivity", 1.0))
        self.runtime_paths = get_runtime_paths()
        # --- Watch wp-o.jpg for instant swap ---
        try:
            self._fsw = QFileSystemWatcher(self)
            wp_o = str(self.runtime_paths["wp_o"])
            if os.path.exists(wp_o):
                self._fsw.addPath(wp_o)
            def _readd_watch():
                try:
                    files = self._fsw.files()
                    if files:
                        self._fsw.removePaths(files)
                except Exception:
                    pass
                try:
                    if os.path.exists(wp_o):
                        self._fsw.addPath(wp_o)
                except Exception:
                    pass
            def _on_wp_o_changed(path):
                QTimer.singleShot(120, lambda: self._swap_to_wp_o_if_ready(readd=_readd_watch))
            self._fsw.fileChanged.connect(_on_wp_o_changed)
        except Exception:
            pass
        # Background state
        self._bg_use_color = None
        self._bg_path = None
        self._bg_file_mtime = None
        self._choose_background_from_settings(s)
        self._bg_source = None
        self._bg_scaled_for = None
        # Background dimming from settings
        self._bg_dim_alpha = int(getattr(s, "background_dim_alpha", 80))
        # First update (safe - does nothing if background_label is missing)
        self._update_background(force=True)
        # Content/UI
        self.content = QWidget(self)
        self.content.setObjectName("content")
        self.content.setGeometry(self.rect())
        self.content.hide()
        self.background_label = QLabel(self.content)
        self.background_label.setGeometry(0, 0, self.width(), self.height())
        self.background_label.setScaledContents(True)
        self.background_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._update_background(force=True)
        self._bg_watch_timer = QTimer(self)
        self._bg_watch_timer.setInterval(800)
        self._bg_watch_timer.timeout.connect(self._bg_tick_watch)
        self._bg_watch_timer.start()
        self.apps = []
        self.filtered_apps = []
        self.current_page = 0
        self._total = 0
        self._total_pages = 0
        self._built_pages = set()
        self.selected_icon_index = -1
        self.selection_mode = False
        self._page_busy = False
        self._gesture_timer = QElapsedTimer()
        self._gesture_timer.invalidate()
        self._gesture_dir = 0
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.search_bar = SearchLineEdit()
        self.search_bar.setPlaceholderText("Search programs...")
        self.search_bar.textChanged.connect(self.filter_apps)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border-radius: 16px;
                font-size: 18px;
                background-color: rgba(255, 255, 255, 40);
                color: white;
                border: 1px solid rgba(255, 255, 255, 60);
            }
        """)
        layout.addWidget(self.search_bar, alignment=Qt.AlignCenter)
        self.search_bar.arrowDown.connect(self._on_search_arrow_down)
        self.search_bar.arrowUp.connect(self._on_search_arrow_up)
        self.search_bar.arrowLeft.connect(self._on_search_arrow_left)
        self.search_bar.arrowRight.connect(self._on_search_arrow_right)
        self.search_bar.enterPressed.connect(self._on_search_enter)
        self.stack = AnimatedStackedWidget()
        self.stack.installEventFilter(self)
        layout.addWidget(self.stack)
        self._make_transparent(self.stack)
        self.page_dots_holder = QWidget(self.content)
        self.page_dots_layout = QHBoxLayout(self.page_dots_holder)
        self.page_dots_layout.setSpacing(8)
        self.page_dots_layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.page_dots_holder)
        self.loading_label = QLabel("Loading apps...")
        self.loading_label.setStyleSheet("color: white; font-size: 16px;")
        loading_holder = QWidget()
        hl = QVBoxLayout(loading_holder)
        hl.setContentsMargins(0, 40, 0, 0)
        hl.addWidget(self.loading_label, alignment=Qt.AlignHCenter | Qt.AlignTop)
        self.stack.addWidget(loading_holder)
        QApplication.instance().installEventFilter(self)
        self._settings_shortcut = None
        self._install_settings_shortcut(getattr(s, "settings_shortcut", "Ctrl+,"))
        self.fx_curtain = QWidget(self)
        self.fx_curtain.setAutoFillBackground(True)
        pal = self.fx_curtain.palette()
        pal.setColor(self.fx_curtain.backgroundRole(), QColor(0,0,0))
        self.fx_curtain.setPalette(pal)
        self.fx_curtain.hide()
        self.fx_overlay = QLabel(self)
        self.fx_overlay.setScaledContents(True)
        self.fx_overlay.hide()
        self.threadpool = QThreadPool.globalInstance()
        loader = AppLoader()
        loader.s.finished.connect(self._on_apps_loaded)
        self.threadpool.start(loader)
        self._run_wallpaper_sync_once()
        self._on_search_text_changed(self.search_bar.text())

    def showEvent(self, e):
        super().showEvent(e)
        self.fx_curtain.setGeometry(self.rect())
        self.fx_curtain.show()
        self.fx_curtain.raise_()

    def _start_intro_fx(self):
        """
        Start the intro zoom effect.
        """
        if not ENABLE_INTRO_ZOOM:
            self.content.show()
            self.fx_curtain.hide()
            return
        self.content.setGeometry(self.rect())
        if self.content.layout():
            self.content.layout().activate()
        self.content.ensurePolished()
        self.content.repaint()
        QCoreApplication.processEvents()
        def _do_render():
            shot = QPixmap(self.size())
            shot.fill(Qt.transparent)
            self.content.render(shot)
            if shot.isNull() or shot.toImage().allGray() and shot.toImage().pixelColor(0,0).alpha() == 0:
                self.content.show()
                self.content.repaint()
                QCoreApplication.processEvents()
                self.content.hide()
                self.content.repaint()
                QCoreApplication.processEvents()
                shot2 = QPixmap(self.size())
                shot2.fill(Qt.transparent)
                self.content.render(shot2)
                shot = shot2
            self.fx_overlay.setPixmap(shot)
            self.fx_overlay.setGeometry(self.rect())
            self.fx_overlay.show()
            self.fx_overlay.raise_()
            self.fx_curtain.stackUnder(self.fx_overlay)
            screen_rect = self.rect()
            start_w = int(screen_rect.width() * ZOOM_START_SCALE)
            start_h = int(screen_rect.height() * ZOOM_START_SCALE)
            start_x = (screen_rect.width() - start_w) // 2
            start_y = (screen_rect.height() - start_h) // 2
            zoom = QPropertyAnimation(self.fx_overlay, b"geometry", self)
            zoom.setDuration(EFFECT_DURATION)
            zoom.setStartValue(QRect(start_x, start_y, start_w, start_h))
            zoom.setEndValue(screen_rect)
            zoom.setEasingCurve(QEasingCurve.OutCubic)
            def cleanup():
                self.fx_overlay.hide()
                self.fx_curtain.hide()
                self.content.show()
            zoom.finished.connect(cleanup)
            zoom.start(QPropertyAnimation.DeleteWhenStopped)
        QTimer.singleShot(0, _do_render)

    def _on_search_text_changed(self, text: str):
        """
        Update selection routing when search text changes.
        """
        self.search_bar.route_lr_to_launcher = (len(text.strip()) == 0)

    def _on_search_arrow_down(self):
        """
        Handle down arrow key in search bar.
        """
        self.search_bar.route_lr_to_launcher = True
        if not self.filtered_apps:
            return
        if not self.selection_mode:
            start_index = self.current_page * self.page_size
            if start_index < len(self.filtered_apps):
                self.select_icon(start_index)
            return
        self.navigate_selection("down")

    def _on_search_arrow_up(self):
        """
        Handle up arrow key in search bar.
        """
        if not self.selection_mode:
            return
        icon_index_in_page = self.selected_icon_index % self.page_size
        current_row_in_page = icon_index_in_page // self.icons_per_row
        if current_row_in_page == 0:
            self.clear_selection()
            self.search_bar.setFocus()
            return
        self.navigate_selection("up")

    def _on_search_arrow_left(self):
        """
        Handle left arrow key in search bar.
        """
        if not self.selection_mode:
            if self.current_page > 0:
                self.switch_page(self.current_page - 1, animate=True)
            return
        self.navigate_selection("left")

    def _on_search_arrow_right(self):
        """
        Handle right arrow key in search bar.
        """
        if not self.selection_mode:
            if self.current_page < self._total_pages - 1:
                self.switch_page(self.current_page + 1, animate=True)
            return
        self.navigate_selection("right")

    def _on_search_enter(self):
        """
        Handle enter key in search bar.
        """
        if self.selection_mode:
            self.launch_selected()

    def _choose_background_from_settings(self, s):
        """
        Update background mode and settings from user preferences.
        """
        mode = getattr(s, "background_mode", BACKGROUND_MODE_WP)
        self.bg_mode = mode
        self._bg_dim_alpha = int(getattr(s, "background_dim_alpha", 80))
        if mode == BACKGROUND_MODE_COLOR:
            self._bg_use_color = _parse_qcolor(getattr(s, "background_color", "#202020"), "#202020")
            self._bg_path = None; self._bg_file_mtime = None
        elif mode == BACKGROUND_MODE_IMAGE:
            self._bg_use_color = None
            prefer = str(self.runtime_paths["wp_o"])
            if os.path.exists(prefer):
                self._bg_path = prefer
            else:
                custom = getattr(s, "background_custom_path", "") or ""
                self._bg_path = custom if custom else None
            self._bg_file_mtime = None
        else:
            self._bg_use_color = None
            self._bg_path = str(self.runtime_paths["wp"])
            self._bg_file_mtime = None

    def _install_settings_shortcut(self, seq_str: str):
        """
        Install or update the settings shortcut.
        """
        if getattr(self, "_settings_shortcut", None) is not None:
            try: self._settings_shortcut.setParent(None)
            except Exception: pass
            self._settings_shortcut = None
        try:
            sc = QShortcut(QKeySequence(seq_str), self)
        except Exception:
            sc = QShortcut(QKeySequence("Ctrl+,"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self.open_settings)
        self._settings_shortcut = sc

    def _bg_tick_watch(self):
        """
        Periodically check if the background image has changed.
        """
        if self._bg_use_color is not None: return
        old = self._bg_file_mtime
        self._load_bg_source()
        if self._bg_file_mtime and old != self._bg_file_mtime:
            self._update_background(force=True)

    def _load_bg_source(self):
        """
        Load the background image or color.
        """
        if self._bg_use_color is not None:
            self._bg_source = None; return
        if not self._bg_path or not os.path.exists(self._bg_path):
            self._bg_source = None; self._bg_file_mtime = None; return
        try:
            mtime = os.path.getmtime(self._bg_path)
        except Exception:
            mtime = None
        need_reload = (self._bg_source is None) or (mtime is not None and mtime != self._bg_file_mtime)
        if need_reload:
            pm = self._load_pixmap_nocache(self._bg_path)
            if not pm.isNull():
                self._bg_source = pm; self._bg_file_mtime = mtime
            else:
                self._bg_source = None

    def _update_background(self, force: bool = False):
        """
        Update the background pixmap, applying dimming if configured.
        """
        try:
            QPixmapCache.clear()
        except Exception:
            pass
        if not hasattr(self, "background_label"):
            return
        if self._bg_use_color is not None:
            pm = QPixmap(self.size()); pm.fill(self._bg_use_color)
            self.background_label.setPixmap(pm)
            self.background_label.setGeometry(0,0,self.width(), self.height())
            self._bg_scaled_for = (self.width(), self.height())
            return
        self._load_bg_source()
        if self._bg_source is None:
            pm = QPixmap(self.size()); pm.fill(QColor(20,20,20))
            self.background_label.setPixmap(pm)
            self.background_label.setGeometry(0,0,self.width(), self.height())
            self._bg_scaled_for = (self.width(), self.height())
            return
        if self.width() <=0 or self.height() <=0: return
        size_key = (self.width(), self.height())
        if not force and getattr(self, "_bg_scaled_for", None) == size_key: return
        scaled = self._bg_source.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        painter = QPainter(scaled)
        if self._bg_dim_alpha > 0:
            painter.fillRect(scaled.rect(), QColor(0,0,0, self._bg_dim_alpha))
        painter.end()
        self.background_label.setPixmap(scaled)
        self.background_label.setGeometry(0,0,self.width(), self.height())
        self._bg_scaled_for = size_key

    def _make_transparent(self, w: QWidget):
        """
        Make a widget transparent.
        """
        w.setAttribute(Qt.WA_NoSystemBackground, True)
        w.setAutoFillBackground(False)
        w.setStyleSheet("background: transparent;")

    def resizeEvent(self, e):
        self._update_background()
        self.content.setGeometry(self.rect())
        if self.fx_curtain.isVisible():
            self.fx_curtain.setGeometry(self.rect())
        if self.fx_overlay.isVisible():
            self.fx_overlay.setGeometry(self.rect())
        super().resizeEvent(e)

    def _on_apps_loaded(self, apps):
        """
        Called when the list of apps is loaded.
        """
        if self.only_resolvable:
            self.apps = [a for a in apps if _icon_is_resolvable(a[1], use_theme_fallback=self.use_theme_fallback)]
        else:
            self.apps = apps
        self.filtered_apps = self.apps
        self._build_dots_and_placeholders()
        self.switch_page(0, animate=False)
        QTimer.singleShot(0, self._start_intro_fx)

    def _build_dots_and_placeholders(self):
        """
        Build page dots and placeholder widgets for all pages.
        """
        for i in reversed(range(self.page_dots_layout.count())):
            w = self.page_dots_layout.itemAt(i).widget()
            if w: w.deleteLater()
        while self.stack.count():
            w = self.stack.widget(0); self.stack.removeWidget(w); w.deleteLater()
        self._built_pages.clear()
        self._total = len(self.filtered_apps)
        self._total_pages = max(1, (self._total + self.page_size - 1)//self.page_size)
        for _ in range(self._total_pages):
            self.stack.addWidget(QWidget())
        for page in range(self._total_pages):
            dot = QLabel("●")
            dot.setStyleSheet(f"font-size: 16px; color: {'white' if page == 0 else 'gray'}")
            def mkhandler(p=page):
                def handler(event): self.switch_page(p)
                return handler
            dot.mousePressEvent = mkhandler(page)
            self.page_dots_layout.addWidget(dot)

    def _ensure_page_built(self, page: int):
        """
        Ensure the page at `page` is built.
        """
        if page in self._built_pages: return
        grid = QGridLayout(); grid.setSpacing(12)
        grid.setContentsMargins(self.grid_lr, 20, self.grid_lr, 20)
        start = page * self.page_size; end = min(start + self.page_size, self._total)
        self.setUpdatesEnabled(False)
        page_widget = QWidget(); self._make_transparent(page_widget)
        for i in range(start, end):
            name, icon_id, cmd, _blob, workdir, terminal, desktop_file_path = self.filtered_apps[i]
            row, col = divmod(i - start, self.icons_per_row)
            icon = _icon_from_id(icon_id, self.icon_size, use_theme_fallback=self.use_theme_fallback)
            app_btn = AppIcon(icon, cmd, self, self.icon_size)
            app_btn._launch_meta = {'workdir': workdir, 'terminal': terminal, 'name': name, 'icon_id': icon_id, 'desktop_file_path': desktop_file_path}
            label_width = self.icon_size + 40
            name_lbl = QLabel()
            qfont = QFont(self.font_family) if self.font_family else QFont()
            qfont.setPointSize(self.font_pt)
            name_lbl.setFont(qfont)
            name_lbl.setStyleSheet(f"background: transparent; color: {self.font_color}; padding-top: 2px;")
            name_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            name_lbl.setWordWrap(True)
            name_lbl.setFixedWidth(label_width)
            name_lbl.setContentsMargins(2, 0, 2, 0)
            name_lbl.setTextFormat(Qt.RichText)
            rich = _label_html(name)
            name_lbl.setText(rich)
            doc = QTextDocument()
            doc.setDefaultFont(qfont)
            doc.setHtml(rich)
            doc.setTextWidth(label_width)
            name_lbl.setMinimumHeight(int(doc.size().height()) + 4)
            name_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
            wrapper = QWidget(); self._make_transparent(wrapper)
            vl = QVBoxLayout(wrapper); vl.setAlignment(Qt.AlignCenter); vl.setSpacing(2); vl.setContentsMargins(0,0,0,0)
            vl.addWidget(app_btn, alignment=Qt.AlignCenter); vl.addWidget(name_lbl, alignment=Qt.AlignCenter)
            grid.addWidget(wrapper, row, col, alignment=Qt.AlignCenter)
        page_widget.setLayout(grid)
        self._page_busy = True
        self.stack.removeWidget(self.stack.widget(page))
        self.stack.insertWidget(page, page_widget)
        self.setUpdatesEnabled(True)
        self._built_pages.add(page)
        self._page_busy = False

    def _set_current_index_safe(self, index: int, animate: bool):
        """
        Safely set the current page index, with or without animation.
        """
        if animate:
            self.stack.setCurrentIndexAnimated(index)
        else:
            self.stack.setCurrentIndex(index)

    def switch_page(self, index: int, animate: bool = True):
        """
        Switch to the page at `index`.
        """
        if self._total_pages == 0: return
        index = max(0, min(index, self._total_pages - 1))
        if self._page_busy or self.stack.is_animating:
            return
        self._page_busy = True
        self._ensure_page_built(index)
        if hasattr(self, '_initial_load_done') and animate:
            self._set_current_index_safe(index, animate=True)
        else:
            self._set_current_index_safe(index, animate=False)
            if not hasattr(self, '_initial_load_done'):
                self._initial_load_done = True
        self.current_page = index
        for i in range(self.page_dots_layout.count()):
            dot = self.page_dots_layout.itemAt(i).widget()
            if dot: dot.setStyleSheet(f"font-size: 16px; color: {'white' if i == index else 'gray'}")
        self.clear_selection()
        if self.stack.is_animating:
            def _release_when_done():
                if not self.stack.is_animating:
                    self._page_busy = False
                else:
                    QTimer.singleShot(20, _release_when_done)
            _release_when_done()
        else:
            self._page_busy = False

    def filter_apps(self, text: str):
        """
        Filter the list of apps by search text.
        """
        q = _normalize_token(text or "").strip()
        if not self.apps: return
        if not q:
            base = self.apps
        else:
            tokens = q.split()
            def matches(a):
                name_norm = _normalize_token(a[0] or "")
                cmd_norm  = _normalize_token(a[2] or "")
                blob      = a[3] or ""
                doc = " ".join((blob, name_norm, cmd_norm))
                return all(tok in doc for tok in tokens)
            base = [a for a in self.apps if matches(a)]
        if self.only_resolvable:
            base = [a for a in base if _icon_is_resolvable(a[1], use_theme_fallback=self.use_theme_fallback)]
        self.filtered_apps = base
        self._build_dots_and_placeholders()
        self.switch_page(0, animate=False)

    def clear_selection(self):
        """
        Clear the current icon selection.
        """
        if self.selected_icon_index >= 0:
            page = self.selected_icon_index // self.page_size
            if page in self._built_pages and 0 <= page < self.stack.count():
                icon_index_in_page = self.selected_icon_index % self.page_size
                row, col = divmod(icon_index_in_page, self.icons_per_row)
                page_widget = self.stack.widget(page)
                grid = page_widget.layout() if page_widget else None
                if grid:
                    item = grid.itemAtPosition(row, col)
                    wrapper = item.widget() if item else None
                    if wrapper:
                        btn = wrapper.findChild(AppIcon)
                        if btn:
                            btn.setStyleSheet(APP_ICON_QSS)
        self.selected_icon_index = -1
        self.selection_mode = False

    def select_icon(self, index: int):
        """
        Select the icon at `index`.
        """
        if index < 0 or index >= len(self.filtered_apps): return
        self.clear_selection()
        self.selected_icon_index = index
        self.selection_mode = True
        page = index // self.page_size
        if page != self.current_page:
            self.switch_page(page, animate=True)
        icon_index_in_page = index % self.page_size
        row, col = divmod(icon_index_in_page, self.icons_per_row)
        page_widget = self.stack.widget(page)
        grid = page_widget.layout() if page_widget else None
        if not grid: return
        item = grid.itemAtPosition(row, col)
        wrapper = item.widget() if item else None
        if not wrapper: return
        btn = wrapper.findChild(AppIcon)
        if not btn: return
        btn.setStyleSheet(
            APP_ICON_QSS +
            "QPushButton{border: 2px solid white; border-radius: 12px; background-color: rgba(255,255,255,80);} "
        )

    def navigate_selection(self, direction: str):
        """
        Navigate the selection in the specified direction.
        """
        if not self.filtered_apps: return
        if not self.selection_mode:
            if direction == "up":
                self.search_bar.setFocus(); return
            start_index_of_current_page = self.current_page * self.page_size
            if start_index_of_current_page < len(self.filtered_apps):
                self.select_icon(start_index_of_current_page)
            return
        current_index = self.selected_icon_index
        if direction == "up":
            new_index = current_index - self.icons_per_row
        elif direction == "down":
            new_index = current_index + self.icons_per_row
        elif direction == "left":
            new_index = current_index - 1
        elif direction == "right":
            new_index = current_index + 1
        else:
            return
        new_index = max(0, min(new_index, len(self.filtered_apps) - 1))
        self.select_icon(new_index)

    def launch_cmd(self, cmd, workdir=None, terminal=False, name="", icon_id=None, desktop_file_path=None):
        """
        Launch a command, optionally in a terminal.
        """
        try:
            argv = shlex.split(cmd, posix=True)
            argv = _substitute_field_codes(argv, name=name, icon=icon_id, desktop_file=desktop_file_path)
            if not argv: raise RuntimeError("empty Exec after substitution")
            if terminal: argv = _wrap_in_terminal(argv)
            program, args = argv[0], argv[1:]
            ok, _pid = QProcess.startDetached(program, args, workdir or "")
            if not ok:
                with open(os.devnull, "wb") as devnull:
                    subprocess.Popen(argv, cwd=workdir or None, stdout=devnull, stderr=devnull, stdin=devnull, start_new_session=True)
        except Exception:
            try:
                with open(os.devnull, "wb") as devnull:
                    subprocess.Popen(cmd, shell=True, cwd=workdir or None, stdout=devnull, stderr=devnull, stdin=devnull, start_new_session=True)
            except Exception:
                pass
        finally:
            QTimer.singleShot(0, QApplication.instance().quit)

    def launch_selected(self):
        """
        Launch the currently selected application.
        """
        if 0 <= self.selected_icon_index < len(self.filtered_apps):
            name, icon_id, cmd, _blob, workdir, terminal, desktop_file_path = self.filtered_apps[self.selected_icon_index]
            self.launch_cmd(cmd, workdir=workdir, terminal=terminal, name=name, icon_id=icon_id, desktop_file_path=desktop_file_path)

    def open_settings(self):
        """
        Open the settings dialog.
        """
        try:
            from .settings_ui import SettingsDialog
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Preferences", f"Could not load preferences:\n{e}")
            return
        dlg = SettingsDialog(self)
        def _apply_live(s):
            try:
                self.stack.set_strategy_by_name(getattr(s, "animation", "slide"))
                self.stack.set_animation_duration(int(getattr(s, "anim_duration_ms", 280)))
            except Exception:
                pass
            self._install_settings_shortcut(getattr(s, "settings_shortcut", "Ctrl+,"))
            self._choose_background_from_settings(s)
            self._bg_source = None
            self._bg_file_mtime = None
            self._update_background(force=True)
            self.page_size = int(getattr(s, "page_size", self.page_size))
            self.icons_per_row = int(getattr(s, "icons_per_row", self.icons_per_row))
            self.icon_size = int(getattr(s, "icon_size", self.icon_size))
            self.grid_lr = int(getattr(s, "grid_margins_lr", self.grid_lr))
            self.font_family = str(getattr(s, "font_family", self.font_family))
            self.font_pt = int(getattr(s, "font_point_size", self.font_pt))
            self.font_color = str(getattr(s, "font_color", self.font_color))
            self.only_resolvable = bool(getattr(s, "filter_only_apps_with_icon", self.only_resolvable))
            self.use_theme_fallback = bool(getattr(s, "use_theme_fallback", self.use_theme_fallback))
            self.wheel_sensitivity = float(getattr(s, "wheel_sensitivity", 1.0))
            self._bg_dim_alpha = int(getattr(s, "background_dim_alpha", 80))
            self._build_dots_and_placeholders()
            self.switch_page(0, animate=False)
        dlg.on_apply = _apply_live
        dlg.exec_()
        s = load_settings()
        self.stack.set_strategy_by_name(getattr(s, "animation", "slide"))
        self.stack.set_animation_duration(int(getattr(s, "anim_duration_ms", 280)))
        self._install_settings_shortcut(getattr(s, "settings_shortcut", "Ctrl+,"))
        self._choose_background_from_settings(s)
        self._bg_source = None
        self._bg_file_mtime = None
        self._update_background(force=True)
        self.page_size = int(getattr(s, "page_size", self.page_size))
        self.icons_per_row = int(getattr(s, "icons_per_row", self.icons_per_row))
        self.icon_size = int(getattr(s, "icon_size", self.icon_size))
        self.grid_lr = int(getattr(s, "grid_margins_lr", self.grid_lr))
        self.font_family = str(getattr(s, "font_family", self.font_family))
        self.font_pt = int(getattr(s, "font_point_size", self.font_pt))
        self.font_color = str(getattr(s, "font_color", self.font_color))
        self.only_resolvable = bool(getattr(s, "filter_only_apps_with_icon", self.only_resolvable))
        self.use_theme_fallback = bool(getattr(s, "use_theme_fallback", self.use_theme_fallback))
        self.wheel_sensitivity = float(getattr(s, "wheel_sensitivity", 1.0))
        self._bg_dim_alpha = int(getattr(s, "background_dim_alpha", 80))
        self._build_dots_and_placeholders()
        self.switch_page(0, animate=False)

    def _is_trackpad_wheel(self, ev) -> bool:
        """
        Check if a wheel event is from a trackpad.
        """
        pd = ev.pixelDelta()
        if pd and (pd.x() != 0 or pd.y() != 0):
            return True
        ad = ev.angleDelta()
        if ad and ad.y() % 120 != 0:
            return True
        return False

    def _touchpad_gesture_allowed(self, direction: int) -> bool:
        """
        Check if a touchpad gesture is allowed (not too soon after the last one).
        """
        if not self._gesture_timer.isValid():
            return True
        if self._gesture_timer.hasExpired(GESTURE_GAP_MS):
            return True
        if direction != self._gesture_dir:
            return True
        return False

    def _start_touchpad_cooldown(self, direction: int):
        """
        Start the cooldown timer after a touchpad gesture.
        """
        self._gesture_dir = 0 if direction == 0 else (1 if direction > 0 else -1)
        self._gesture_timer.restart()

    def eventFilter(self, source, event):
        """
        Filter events for wheel and key navigation.
        """
        if event.type() == QEvent.Wheel and source == self.stack:
            if self._page_busy or self.stack.is_animating:
                return True
            ady = event.angleDelta().y()
            pdy = event.pixelDelta().y()
            is_touchpad = self._is_trackpad_wheel(event)
            if is_touchpad:
                direction = pdy if pdy != 0 else ady
                direction *= TRACKPAD_MULTIPLIER
                if direction == 0:
                    return True
                dir_norm = 1 if direction < 0 else -1
                if not self._touchpad_gesture_allowed(dir_norm):
                    return True
                if dir_norm > 0:
                    if self.current_page < self._total_pages - 1:
                        self.switch_page(self.current_page + TOUCHPAD_STEP_PAGES, animate=True)
                else:
                    if self.current_page > 0:
                        self.switch_page(self.current_page - TOUCHPAD_STEP_PAGES, animate=True)
                self._start_touchpad_cooldown(dir_norm)
                return True
            else:
                direction = ady
                threshold = 120 / max(0.1, self.wheel_sensitivity)
                if abs(direction) >= threshold:
                    if direction < 0 and self.current_page < self._total_pages - 1:
                        self.switch_page(self.current_page + 1, animate=True)
                    elif direction > 0 and self.current_page > 0:
                        self.switch_page(self.current_page - 1, animate=True)
                return True
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if (event.text() and not event.text().isspace() and
                not event.modifiers() in (Qt.ControlModifier, Qt.AltModifier) and
                key not in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape, Qt.Key_Tab,
                           Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Left, Qt.Key_Right,
                           Qt.Key_Up, Qt.Key_Down)):
                self.search_bar.setFocus()
                self.search_bar.route_lr_to_launcher = False
                self.search_bar.keyPressEvent(event)
                return True
            fw = QApplication.focusWidget(); in_search = (fw is self.search_bar)
            if not in_search:
                if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
                    if self._page_busy or self.stack.is_animating:
                        return True
                    if key == Qt.Key_Left:
                        if self.selection_mode:
                            self.navigate_selection("left")
                        else:
                            if self.current_page > 0: self.switch_page(self.current_page - 1, animate=True)
                    elif key == Qt.Key_Right:
                        if self.selection_mode:
                            self.navigate_selection("right")
                        else:
                            if self.current_page < self._total_pages - 1: self.switch_page(self.current_page + 1, animate=True)
                    elif key == Qt.Key_Up:
                        self.navigate_selection("up")
                    elif key == Qt.Key_Down:
                        self.navigate_selection("down")
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter) and self.selection_mode:
                    self.launch_selected(); return True
                if key == Qt.Key_Escape:
                    if self.selection_mode:
                        self.clear_selection()
                    else:
                        self.close()
                    return True
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        """
        Close the launcher if the user clicks outside the content.
        """
        clicked_widget = self.childAt(event.pos())
        ignore_widgets = [self.search_bar, self.fx_curtain, self.fx_overlay]
        for i in range(self.page_dots_layout.count()):
            w = self.page_dots_layout.itemAt(i).widget()
            if w:
                ignore_widgets.append(w)
        current_page_widget = self.stack.currentWidget()
        if current_page_widget:
            for w in current_page_widget.findChildren(QWidget):
                ignore_widgets.append(w)
        is_ignored = (
            clicked_widget is None
            or clicked_widget in ignore_widgets
            or any(clicked_widget is w for w in ignore_widgets)
        )
        if not is_ignored:
            self.close()
        super().mousePressEvent(event)

    def _run_wallpaper_sync_once(self):
        """
        Run the wallpaper sync script once.
        """
        try:
            py = sys.executable or "python3"
            QProcess.startDetached(py, ["-m", "vifa_launcher.wallpaper_sync"])
        except Exception:
            pass


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass
    app = QApplication(sys.argv)
    launcher = AppLauncher()
    launcher.show()
    launcher.raise_()
    launcher.activateWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
