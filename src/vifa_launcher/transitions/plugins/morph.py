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
#
# -*- coding: utf-8 -*-
# ---------- PyQt5/6 Shim ----------
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = False

Qt           = QtCore.Qt
QRect        = QtCore.QRect
QRectF       = QtCore.QRectF
QPoint       = QtCore.QPoint
QSize        = QtCore.QSize
QPainter     = QtGui.QPainter
QImage       = QtGui.QImage
QColor       = QtGui.QColor
QEasingCurve = QtCore.QEasingCurve
QVariantAnimation = QtCore.QVariantAnimation
QSequentialAnimationGroup = QtCore.QSequentialAnimationGroup
QWidget      = QtWidgets.QWidget
QStackedWidget = QtWidgets.QStackedWidget

if PYQT6:
    AspectIgnore  = Qt.AspectRatioMode.IgnoreAspectRatio
    SmoothXform   = Qt.TransformationMode.SmoothTransformation
    Format_ARGB32 = QImage.Format.Format_ARGB32_Premultiplied
else:
    AspectIgnore  = Qt.IgnoreAspectRatio
    SmoothXform   = Qt.SmoothTransformation
    Format_ARGB32 = QImage.Format_ARGB32_Premultiplied

# ---------- Base ----------
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

# ---------- Tunables ----------
STRIPS           = 96     # 64–128: higher = smoother
S_MIN            = 0.14   # Minimum sample width per strip (prevents compression artifacts)
BLEED_PX         = 1.2    # Source bleed (float) to prevent edge artifacts
EPS_OVERLAP      = 0      # Minimum uniform overlap in pixels
XF_CENTER        = 0.50   # Crossfade center
XF_WIDTH         = 0.22   # Crossfade span (wider = softer)
GAMMA_S          = 1.0    # Shape s(t) = |cos(pi t)|^gamma
# Morph feeling
TO_SOFT_FACTOR   = 0.35
FROM_SOFT_FACTOR = 0.55
TO_SHARP_RANGE   = (0.55, 0.95)
FROM_SHARP_RANGE = (0.05, 0.45)

# ---------- Helpers ----------
def _render_widget_argb(widget: QWidget, size: QSize) -> QImage:
    """Render page off-screen into transparent ARGB (content only)."""
    w, h = max(1, size.width()), max(1, size.height())
    img = QImage(w, h, Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent if PYQT6 else Qt.transparent)
    try:
        widget.ensurePolished()
        lay = widget.layout()
        if lay:
            lay.activate()
    except Exception:
        pass
    orig = widget.size()
    try:
        if orig.width() != w or orig.height() != h:
            widget.resize(w, h)
        p = QPainter(img)
        widget.render(p)
        p.end()
    finally:
        try:
            if widget.size() != orig:
                widget.resize(orig)
        except Exception:
            pass
    return img

def _soften(img: QImage, factor: float) -> QImage:
    """Simple soft blur via downscale→upscale."""
    if factor <= 0 or factor >= 1:
        return img
    w, h = img.width(), img.height()
    sw, sh = max(1, int(w * factor)), max(1, int(h * factor))
    small = img.scaled(sw, sh, AspectIgnore, SmoothXform)
    back  = small.scaled(w, h, AspectIgnore, SmoothXform)
    return back

def _smoothstep(e0: float, e1: float, x: float) -> float:
    """Smoothstep interpolation between e0 and e1."""
    if e1 == e0:
        return 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)

# ---------- Overlay (float-precise, no feather) ----------
class _Overlay(QWidget):
    def __init__(self, parent_stack: QStackedWidget, from_img: QImage, to_img: QImage, strips: int = STRIPS):
        super().__init__(parent_stack)
        # Transparent – background remains
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._from = from_img
        self._to   = to_img
        self._from_soft = _soften(self._from, FROM_SOFT_FACTOR)
        self._to_soft   = _soften(self._to,   TO_SOFT_FACTOR)
        self._t      = 0.0
        self._strips = max(16, int(strips))
        self.show()
        self.raise_()

    def set_progress(self, t: float):
        self._t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
        self.update()

    def paintEvent(self, _):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.Antialiasing, False)
        W = float(self.width())
        H = float(self.height())
        n = float(self._strips)
        t = self._t
        # Homogeneous flip compression
        s = abs(math.cos(math.pi * t)) ** GAMMA_S
        if s < S_MIN:
            s = S_MIN
        # Soft crossfade
        w_to   = _smoothstep(XF_CENTER - XF_WIDTH, XF_CENTER + XF_WIDTH, t)
        w_from = 1.0 - w_to
        # Sharpness weights
        to_sharp   = _smoothstep(TO_SHARP_RANGE[0],   TO_SHARP_RANGE[1],   t)
        from_sharp = 1.0 - _smoothstep(FROM_SHARP_RANGE[0], FROM_SHARP_RANGE[1], t)
        # Strips with subpixel-precise boundaries
        # Division points (float): x_i = i * W/n
        for i in range(int(n)):
            x0 = (i    ) * W / n
            x1 = (i + 1) * W / n
            if i > 0:
                x0 -= EPS_OVERLAP
            if i < int(n) - 1:
                x1 += EPS_OVERLAP
            if x1 <= x0:
                continue
            dst = QRectF(x0, 0.0, x1 - x0, H)
            # Source (centered) with bleed
            src_full_x0 = (i    ) * W / n
            src_full_x1 = (i + 1) * W / n
            src_full_w  = src_full_x1 - src_full_x0
            w_sub   = max(1.0, src_full_w * s)
            leftover = max(0.0, src_full_w - w_sub)
            dx      = leftover * 0.5
            bleed   = min(BLEED_PX, dx)  # Do not exceed edge
            sx      = max(0.0, src_full_x0 + dx - bleed)
            sw      = min(W - sx, w_sub + 2.0 * bleed)
            src = QRectF(sx, 0.0, sw, H)
            # Old page
            if w_from > 0.0:
                if from_sharp < 1.0:
                    p.setOpacity(w_from * (1.0 - from_sharp))
                    p.drawImage(dst, self._from_soft, src)
                if from_sharp > 0.0:
                    p.setOpacity(w_from * from_sharp)
                    p.drawImage(dst, self._from, src)
            # New page
            if w_to > 0.0:
                if to_sharp < 1.0:
                    p.setOpacity(w_to * (1.0 - to_sharp))
                    p.drawImage(dst, self._to_soft, src)
                if to_sharp > 0.0:
                    p.setOpacity(w_to * to_sharp)
                    p.drawImage(dst, self._to, src)
        p.setOpacity(1.0)
        p.end()

# ---------- Strategy ----------
class CardFlipTransition(TransitionStrategy):
    name = "morph"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int) -> QSequentialAnimationGroup:
        if to_index == stack.currentIndex():
            return QSequentialAnimationGroup(stack)
        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSequentialAnimationGroup(stack)
        size = QSize(w, h)
        from_page = stack.currentWidget()
        to_page   = stack.widget(to_index)
        if from_page is None or to_page is None:
            return QSequentialAnimationGroup(stack)
        # Hide real pages → no overlay
        from_page.setVisible(False)
        to_page.setVisible(False)
        # Render pages as ARGB
        from_img = _render_widget_argb(from_page, size)
        to_img   = _render_widget_argb(to_page,   size)
        overlay = _Overlay(stack, from_img, to_img, strips=STRIPS)
        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.valueChanged.connect(overlay.set_progress)
        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(anim)
        def _finish():
            try:
                stack.setCurrentIndex(to_index)
                to_page.setVisible(True)
            finally:
                overlay.deleteLater()
        grp.finished.connect(_finish)
        return grp

