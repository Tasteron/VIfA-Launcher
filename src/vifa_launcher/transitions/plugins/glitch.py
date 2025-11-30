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
# transitions/glitch.py
import random
from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QSequentialAnimationGroup, QRect, QSize, QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPixmap, QImage
from ..base import TransitionStrategy

def _scaled(pm: QPixmap, size: QSize) -> QPixmap:
    if pm.isNull():
        out = QPixmap(size)
        out.fill(Qt.transparent)
        return out
    if pm.size() == size:
        return pm
    return pm.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

def _render_widget_transparent(widget: QWidget, target_size: QSize) -> QPixmap:
    """Render widget off-screen onto a transparent surface."""
    if target_size.isEmpty():
        target_size = widget.size() if not widget.size().isEmpty() else QSize(1, 1)
    img = QImage(max(1, target_size.width()), max(1, target_size.height()), QImage.Format_ARGB32_Premultiplied)
    img.fill(0x00000000)
    try:
        widget.ensurePolished()
        if widget.layout():
            widget.layout().activate()
    except Exception:
        pass
    orig = widget.size()
    try:
        if orig != target_size:
            widget.resize(target_size)
        p = QPainter(img)
        widget.render(p)
        p.end()
    finally:
        try:
            if orig != target_size:
                widget.resize(orig)
        except Exception:
            pass
    return QPixmap.fromImage(img)

class _DirectGlitchOverlay(QWidget):
    """
    More intense glitch effect with higher contrast and sharper stripes.
    """
    def __init__(self, parent, to_pm: QPixmap):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setGeometry(parent.rect())
        self._progress = 0.0
        self._to_pm = _scaled(to_pm, self.size())
        # More intense parameters for sharper effect
        self._bands = 12          # More bands for finer stripes
        self._max_offset = 24    # Larger offset
        self._jitter_layers = 3 # Multiple overlapping layers
        # Higher framerate for smoother animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(12)  # ~83fps
        self.show()
        self.raise_()

    def set_progress(self, p: float):
        self._progress = max(0.0, min(1.0, float(p)))

    def resizeEvent(self, _):
        self._to_pm = _scaled(self._to_pm, self.size())

    def paintEvent(self, _):
        if self._to_pm.isNull():
            return
        p = QPainter(self)
        t = self._progress
        w, h = self.width(), self.height()
        # More intense progress curve for faster effect
        intensity = min(1.0, t * 4.0)  # Faster buildup
        peak = 6.0 * t * (1.0 - t)     # Higher peak
        # Multiple overlapping layers for more intense effect
        for layer in range(self._jitter_layers):
            self._draw_glitch_layer(p, w, h, intensity, peak, layer)
        p.end()

    def _draw_glitch_layer(self, painter: QPainter, w: int, h: int, intensity: float, peak: float, layer: int):
        """Draw a layer of the glitch effect."""
        band_h = max(3, h // self._bands)
        base_opacity = 0.18 * intensity  # Higher opacity
        # Different blend modes for different layers
        if layer == 0:
            painter.setCompositionMode(QPainter.CompositionMode_Darken)
        elif layer == 1:
            painter.setCompositionMode(QPainter.CompositionMode_ColorBurn)
        else:
            painter.setCompositionMode(QPainter.CompositionMode_Multiply)
        # Random band activation for more organic look
        active_bands = random.sample(range(0, h, band_h),
                                   k=int(self._bands * 0.8 * intensity))
        for y in active_bands:
            bh = min(band_h, h - y)
            src = QRect(0, y, w, bh)

            # Larger and more unpredictable offset
            max_layer_offset = self._max_offset * (1.0 + layer * 0.3)
            dx = random.randint(-int(max_layer_offset * peak), int(max_layer_offset * peak))

            # Additional Y-offset for more complex effect
            dy = random.randint(-2, 2) if peak > 0.3 else 0

            dst = QRect(dx, y + dy, w, bh)

            # Variable opacity for more dynamic look
            band_opacity = base_opacity * (0.7 + 0.3 * random.random())
            painter.setOpacity(band_opacity)

            painter.drawPixmap(dst, self._to_pm, src)
        # Reset to default blend mode
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def cleanup(self):
        if hasattr(self, "_timer"):
            self._timer.stop()
        self.deleteLater()

class GlitchTransition(TransitionStrategy):
    """
    Intensified glitch transition with sharper effect.
    """
    name = "glitch"

    def start(self, stack, to_index: int, duration_ms: int):
        if to_index == stack.currentIndex():
            return QSequentialAnimationGroup(stack)
        size = stack.size()
        if size.isEmpty() and stack.parent():
            size = stack.parent().size()
        if size.isEmpty():
            size = QSize(800, 600)
        # Render target page
        to_widget = stack.widget(to_index)
        to_pm = _render_widget_transparent(to_widget, size)
        # Create overlay
        overlay = _DirectGlitchOverlay(stack, to_pm)
        # Shorter, more intense animation
        anim = QVariantAnimation(stack)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(max(180, int(duration_ms)))  # Slightly longer for more intense effect

        # Slightly accelerated easing curve
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.valueChanged.connect(overlay.set_progress)
        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            stack.setCurrentIndex(to_index)
            overlay.cleanup()

        grp.finished.connect(finish)
        return grp

