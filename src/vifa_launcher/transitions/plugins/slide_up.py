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
# vifa_launcher/transitions/plugins/slide_up.py

from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QParallelAnimationGroup
from PyQt5.QtWidgets import QWidget, QStackedWidget
from PyQt5.QtGui import QPainter, QImage

# --- Import base class (relative + fallback) ---
try:
    from ..base import TransitionStrategy
except Exception:
    try:
        from base import TransitionStrategy
    except Exception as exc:
        raise ImportError(
            "Could not import TransitionStrategy. "
            "Adjust the import in slide_up.py to match your project structure."
        ) from exc

# ---------- Render pages as ARGB32 (transparent) ----------
def _render_widget_alpha(widget: QWidget, w: int, h: int) -> QImage:
    """Render the widget off-screen into a transparent ARGB32 image."""
    img = QImage(max(1, w), max(1, h), QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    # Ensure layout/polish
    try:
        widget.ensurePolished()
        lay = widget.layout()
        if lay:
            lay.activate()
    except Exception:
        pass
    orig_size = widget.size()
    try:
        if orig_size.width() != w or orig_size.height() != h:
            widget.resize(w, h)
        p = QPainter(img)
        widget.render(p)  # Directly onto the transparent surface
        p.end()
    finally:
        try:
            if widget.size() != orig_size:
                widget.resize(orig_size)
        except Exception:
            pass
    return img

# ---------- Overlay: slides two page images vertically, with direction ----------
class _SlideOverlayVertical(QWidget):
    def __init__(self, parent_stack: QStackedWidget, from_img: QImage, to_img: QImage,
                 direction: int, easing: QEasingCurve):
        super().__init__(parent_stack)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._from = from_img
        self._to = to_img
        self._dir = 1 if direction >= 0 else -1   # +1: bottom→top, -1: top→bottom
        self._ease = easing
        self._t = 0.0
        self.show()
        self.raise_()

    def set_progress(self, t: float):
        self._t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
        self.update()

    def paintEvent(self, _):
        H = self.height()
        tt = self._ease.valueForProgress(self._t)
        # General with direction:
        # t=0:  from_y = 0
        #       to_y   =  dir * H   (start at bottom for dir=+1, top for dir=-1)
        # t=1:  from_y = -dir * H
        #       to_y   =  0
        from_y = int(-self._dir * tt * H)
        to_y   = int(self._dir * (1.0 - tt) * H)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.drawImage(0, from_y, self._from)
        p.drawImage(0, to_y,   self._to)
        p.end()

class SlideUpTransition(TransitionStrategy):
    name = "slide_up"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        grp = QParallelAnimationGroup(stack)
        from_index = stack.currentIndex()
        if to_index == from_index:
            return grp

        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0 or duration_ms <= 0:
            stack.setCurrentIndex(to_index)
            return grp

        current_widget: QWidget = stack.currentWidget()
        next_widget: QWidget = stack.widget(to_index)
        if current_widget is None or next_widget is None:
            grp.finished.connect(lambda: stack.setCurrentIndex(to_index))
            return grp

        # Hide both pages during animation (only overlay visible)
        cur_was_visible = current_widget.isVisible()
        next_was_visible = next_widget.isVisible()
        current_widget.setVisible(False)
        next_widget.setVisible(False)

        # Create page images
        from_img = _render_widget_alpha(current_widget, w, h)
        to_img   = _render_widget_alpha(next_widget,   w, h)

        # Determine direction: forward (bottom→top) vs. backward (top→bottom)
        direction = 1 if to_index > from_index else -1
        easing = QEasingCurve(QEasingCurve.OutCubic)
        overlay = _SlideOverlayVertical(stack, from_img, to_img, direction, easing)

        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Linear)  # Linear timing, curve in overlay
        anim.valueChanged.connect(overlay.set_progress)
        grp.addAnimation(anim)

        def finish():
            try:
                stack.setCurrentIndex(to_index)
                next_widget.setVisible(True)
            finally:
                overlay.deleteLater()
                if cur_was_visible:
                    current_widget.setVisible(False)

        grp.finished.connect(finish)
        return grp

