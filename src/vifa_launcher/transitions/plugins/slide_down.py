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
# vifa_launcher/transitions/plugins/slide_down.py

from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QParallelAnimationGroup
from PyQt5.QtWidgets import QWidget, QStackedWidget
from PyQt5.QtGui import QPainter, QImage
from ..base import TransitionStrategy

# ---------- Local, robust helpers: Render pages as TRANSPARENT images ----------
def _render_widget_alpha(widget: QWidget, w: int, h: int) -> QImage:
    """
    Render the widget off-screen into an ARGB32 image with a TRANSPARENT background.
    -> Only the page content is included; the (static) background remains outside.
    """
    img = QImage(max(1, w), max(1, h), QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    # Prepare widget (layout & polishing), temporarily adjust size
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
        # No special composition needed: we paint directly onto the transparent surface
        widget.render(p)
        p.end()
    finally:
        try:
            if widget.size() != orig_size:
                widget.resize(orig_size)
        except Exception:
            pass
    return img

# ---------- Overlay that ONLY slides the two page images from bottom to top ----------
class _SlideUpOverlay(QWidget):
    def __init__(self, parent_stack: QStackedWidget, from_img: QImage, to_img: QImage,
                 direction: int, easing: QEasingCurve):
        super().__init__(parent_stack)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._from = from_img  # ARGB (transparent)
        self._to = to_img      # ARGB (transparent)
        self._dir = 1 if direction >= 0 else -1   # +1: forward (up), -1: backward (down)
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
        # t=0:  from_y=0,         to_y= dir*H (starting from bottom)
        # t=1:  from_y=-dir*H,    to_y= 0 (reached top)
        from_y = int(-self._dir * tt * H)
        to_y   = int(self._dir * (1.0 - tt) * H)
        p = QPainter(self)
        # No smoothing needed: we move whole pixels (fast, jitter-free)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setRenderHint(QPainter.Antialiasing, False)
        # Only paint the page contents – the background remains visible and static
        p.drawImage(0, from_y, self._from)  # X position remains 0, Y moves
        p.drawImage(0, to_y,   self._to)    # X position remains 0, Y moves
        p.end()

class SlideUpTransition(TransitionStrategy):
    name = "slide_up"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        from_index = stack.currentIndex()
        if to_index == from_index:
            return QParallelAnimationGroup(stack)

        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QParallelAnimationGroup(stack)

        current_widget: QWidget = stack.currentWidget()
        next_widget: QWidget = stack.widget(to_index)
        if current_widget is None or next_widget is None:
            grp = QParallelAnimationGroup(stack)
            grp.finished.connect(lambda: stack.setCurrentIndex(to_index))
            return grp

        # Hide pages during animation → no overlay / no "ghosting"
        cur_was_visible = current_widget.isVisible()
        next_was_visible = next_widget.isVisible()
        current_widget.setVisible(False)
        next_widget.setVisible(False)

        # Create ARGB snapshots of ONLY the pages (no background)
        from_img = _render_widget_alpha(current_widget, w, h)
        to_img   = _render_widget_alpha(next_widget,   w, h)

        # Direction: 1 = up, -1 = down
        # Normally we want to slide up for "forward"
        direction = 1 if to_index > from_index else -1
        easing = QEasingCurve(QEasingCurve.OutCubic)
        overlay = _SlideUpOverlay(stack, from_img, to_img, direction, easing)

        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        # Linear time, curve in overlay (feels crisper)
        anim.setEasingCurve(QEasingCurve.Linear)
        anim.valueChanged.connect(overlay.set_progress)

        grp = QParallelAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            try:
                stack.setCurrentIndex(to_index)
                # Show target page; old remains hidden until next use
                next_widget.setVisible(True)
            finally:
                overlay.deleteLater()
                # Restore visibilities to "clean" state
                if cur_was_visible:
                    current_widget.setVisible(False)
                # next_widget remains visible

        grp.finished.connect(finish)
        return grp

# Alternative: Slide-Down Transition (top to bottom)
class SlideDownTransition(TransitionStrategy):
    name = "slide_down"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        from_index = stack.currentIndex()
        if to_index == from_index:
            return QParallelAnimationGroup(stack)

        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QParallelAnimationGroup(stack)

        current_widget: QWidget = stack.currentWidget()
        next_widget: QWidget = stack.widget(to_index)
        if current_widget is None or next_widget is None:
            grp = QParallelAnimationGroup(stack)
            grp.finished.connect(lambda: stack.setCurrentIndex(to_index))
            return grp

        # Hide pages during animation
        cur_was_visible = current_widget.isVisible()
        next_was_visible = next_widget.isVisible()
        current_widget.setVisible(False)
        next_widget.setVisible(False)

        # Create ARGB snapshots
        from_img = _render_widget_alpha(current_widget, w, h)
        to_img   = _render_widget_alpha(next_widget,   w, h)

        # Reverse direction for Slide-Down
        direction = -1 if to_index > from_index else 1  # Opposite to Slide-Up
        easing = QEasingCurve(QEasingCurve.OutCubic)
        overlay = _SlideUpOverlay(stack, from_img, to_img, direction, easing)

        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Linear)
        anim.valueChanged.connect(overlay.set_progress)

        grp = QParallelAnimationGroup(stack)
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

# Combined version with direction selection
class SlideVerticalTransition(TransitionStrategy):
    name = "slide_vertical"

    def __init__(self, direction="up"):
        super().__init__()
        self.direction = direction.lower()  # "up" or "down"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        from_index = stack.currentIndex()
        if to_index == from_index:
            return QParallelAnimationGroup(stack)

        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QParallelAnimationGroup(stack)

        current_widget: QWidget = stack.currentWidget()
        next_widget: QWidget = stack.widget(to_index)
        if current_widget is None or next_widget is None:
            grp = QParallelAnimationGroup(stack)
            grp.finished.connect(lambda: stack.setCurrentIndex(to_index))
            return grp

        # Hide pages during animation
        cur_was_visible = current_widget.isVisible()
        next_was_visible = next_widget.isVisible()
        current_widget.setVisible(False)
        next_widget.setVisible(False)

        # Create ARGB snapshots
        from_img = _render_widget_alpha(current_widget, w, h)
        to_img   = _render_widget_alpha(next_widget,   w, h)

        # Direction based on configuration
        if self.direction == "down":
            direction = -1 if to_index > from_index else 1
        else:  # default: up
            direction = 1 if to_index > from_index else -1

        easing = QEasingCurve(QEasingCurve.OutCubic)
        overlay = _SlideUpOverlay(stack, from_img, to_img, direction, easing)

        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Linear)
        anim.valueChanged.connect(overlay.set_progress)

        grp = QParallelAnimationGroup(stack)
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

