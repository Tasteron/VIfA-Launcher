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
#
# -*- coding: utf-8 -*-
# --- PyQt5/6 Compatibility Shim -----------------------------------------
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = False
Qt = QtCore.Qt
QE = QtCore.QEasingCurve
QVA = QtCore.QVariantAnimation
QSG = QtCore.QSequentialAnimationGroup
QWidget = QtWidgets.QWidget
QStackedWidget = QtWidgets.QStackedWidget
QPainter = QtGui.QPainter
QPixmap = QtGui.QPixmap
QRect = QtCore.QRect
QRectF = QtCore.QRectF
QSize = QtCore.QSize
QPainterPath = QtGui.QPainterPath
# Set easing and render flags for compatibility
if PYQT6:
    EASE = getattr(QE.Type, "InOutSine", QE.InOutSine)
    RF_BG = QtWidgets.QWidget.RenderFlag.DrawWindowBackground
    RF_CH = QtWidgets.QWidget.RenderFlag.DrawChildren
    # Enums for 5/6 compatibility
    WA_NoSystemBackground      = Qt.WidgetAttribute.WA_NoSystemBackground
    WA_TransparentForMouse     = Qt.WidgetAttribute.WA_TransparentForMouseEvents
    WA_StyledBackground        = Qt.WidgetAttribute.WA_StyledBackground
    CM_SourceOver              = QtGui.QPainter.CompositionMode.CompositionMode_SourceOver
else:
    EASE = QE.InOutSine
    RF_BG = QtWidgets.QWidget.DrawWindowBackground
    RF_CH = QtWidgets.QWidget.DrawChildren
    WA_NoSystemBackground      = Qt.WA_NoSystemBackground
    WA_TransparentForMouse     = Qt.WA_TransparentForMouseEvents
    WA_StyledBackground        = Qt.WA_StyledBackground
    CM_SourceOver              = QtGui.QPainter.CompositionMode_SourceOver
# --- Base -----------------------------------------------------------------
try:
    from ..base import TransitionStrategy  # type: ignore
except Exception:
    try:
        from .base import TransitionStrategy  # type: ignore
    except Exception:
        class TransitionStrategy(object):
            name = "Transition"
            def start(self, *args, **kwargs):
                return QSG()
# --- Helpers ----------------------------------------------------------------
def _process_events():
    try:
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 0)
    except Exception:
        pass

def _render_target_to_pixmap(target: QWidget, size: QSize, dpr: float) -> QPixmap:
    """Render the given widget offscreen into a DPI-aware QPixmap (without foreign background)."""
    w = max(1, int(size.width() * max(1.0, dpr)))
    h = max(1, int(size.height() * max(1.0, dpr)))
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(max(1.0, dpr))
    p = QPainter(pm)
    try:
        target.render(p, QtCore.QPoint(0, 0), QtGui.QRegion(), RF_BG | RF_CH)
    finally:
        p.end()
    return pm

def _ease_in_out_sine(x: float) -> float:
    import math
    x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
    return 0.5 * (1.0 - math.cos(math.pi * x))
# --- Overlay ----------------------------------------------------------------
class _Overlay(QWidget):
    GRID_W = 48
    GRID_H = 48
    SPREAD = 0.82   # Radial delay (center to edge)
    MIN_FRAC = 0.06 # Initial size of inner core (>0 avoids pop-in)
    OVERLAP = 1     # 1px overlap to prevent visible seams
    RADIUS = 2      # Slight rounding of tile edges
    EPS = 1e-6

    def __init__(self, parent_stack: QWidget, from_pm: QPixmap, to_pm: QPixmap):
        super().__init__(parent_stack)
        # Transparent overlay – only paint what is necessary
        self.setAttribute(WA_NoSystemBackground, True)
        self.setAttribute(WA_TransparentForMouse, True)
        self.setAttribute(WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._from = from_pm
        self._to = to_pm
        self._t = 0.0
        W, H = self.width(), self.height()
        cols = max(10, W // self.GRID_W)
        rows = max(8,  H // self.GRID_H)
        self._cols, self._rows = cols, rows
        self._tile_w = max(1, W // cols)
        self._tile_h = max(1, H // rows)
        # Radial sorting (center to edge)
        cx, cy = W * 0.5, H * 0.5
        import math
        maxd = math.hypot(cx, cy)
        tiles = []
        for j in range(rows):
            for i in range(cols):
                x = i * self._tile_w
                y = j * self._tile_h
                ww = self._tile_w if i < cols - 1 else W - x
                hh = self._tile_h if j < rows - 1 else H - y
                rect = QRect(x, y, ww, hh)
                mx = x + ww * 0.5
                my = y + hh * 0.5
                delay = math.hypot(mx - cx, my - cy) / max(1.0, maxd)
                tiles.append((rect, delay))
        tiles.sort(key=lambda t: t[1])
        self._tiles = tiles
        self.show()
        self.raise_()

    def set_progress(self, t: float) -> None:
        self._t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
        self.update()

    def _local_phase(self, t_global: float, delay: float) -> float:
        start = delay * self.SPREAD
        if t_global <= start:
            return 0.0
        span = max(self.EPS, 1.0 - start)
        return (t_global - start) / span

    def _inner_rect(self, rect: QRect, frac: float) -> QRect:
        # Growing inner area (centered)
        f = max(self.MIN_FRAC, min(1.0, frac))
        w = max(1, int(rect.width() * f))
        h = max(1, int(rect.height() * f))
        cx = rect.x() + rect.width() // 2
        cy = rect.y() + rect.height() // 2
        x = cx - w // 2
        y = cy - h // 2
        # Slight overlap to prevent visible seams
        x = max(0, x - self.OVERLAP)
        y = max(0, y - self.OVERLAP)
        w = min(rect.right() + 1 - x + self.OVERLAP, rect.width())
        h = min(rect.bottom() + 1 - y + self.OVERLAP, rect.height())
        return QRect(x, y, w, h)

    def paintEvent(self, _: object) -> None:
        if self._to.isNull() or self._from.isNull():
            return
        t = self._t
        if t <= 0.0:
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.setCompositionMode(CM_SourceOver)
            # IMPORTANT: Draw the entire old page first as a "base",
            # so no new pixel shines through prematurely (for transparent widgets).
            p.drawPixmap(self.rect(), self._from, self._from.rect())
            # Then, tile by tile, only add the inner part of the new image.
            for rect, delay in self._tiles:
                local = self._local_phase(t, delay)
                if local <= 0.0:
                    continue
                eased = _ease_in_out_sine(local)
                if eased >= 1.0 - self.EPS:
                    # Draw the entire tile as "new"
                    p.drawPixmap(rect, self._to, rect)
                else:
                    inner = self._inner_rect(rect, eased)
                    if not inner.isEmpty():
                        p.drawPixmap(inner, self._to, inner)
        finally:
            p.end()
# --- Strategy ----------------------------------------------------------------
class CheckerboardTransition(TransitionStrategy):
    name = "Mosaic"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int) -> QSG:
        if to_index == stack.currentIndex():
            return QSG(stack)
        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSG(stack)
        size = QSize(w, h)
        target  = stack.widget(to_index)
        current = stack.currentWidget()
        if target is None or current is None:
            return QSG(stack)
        # DO NOT SHOW TARGET DURING ANIMATION!
        # (otherwise it will shine through transparent areas)
        target.resize(size)
        target.setVisible(False)
        _process_events()
        # Adopt DPR
        try:
            dpr = float(getattr(stack, "devicePixelRatioF", lambda: 1.0)())
        except Exception:
            dpr = 1.0
        # Offscreen snapshots of both pages
        from_pm = _render_target_to_pixmap(current, size, dpr)
        to_pm   = _render_target_to_pixmap(target,  size, dpr)
        # Overlay: first draws the "old" page full-screen, then mosaic parts of the "new"
        overlay = _Overlay(stack, from_pm, to_pm)
        # Animation
        anim = QVA(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(EASE)
        anim.valueChanged.connect(overlay.set_progress)
        grp = QSG(stack)
        grp.addAnimation(anim)

        def _finish():
            # Now switch to the target page and make it visible
            stack.setCurrentIndex(to_index)
            target.setVisible(True)
            stack.repaint()
            QtCore.QTimer.singleShot(0, overlay.deleteLater)

        grp.finished.connect(_finish)
        return grp

