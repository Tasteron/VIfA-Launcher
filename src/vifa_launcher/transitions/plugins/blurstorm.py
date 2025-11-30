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
# transitions/classic/blurstorm.py
import time
from typing import Optional, Dict

# ---- PyQt5/6 shim ----------------------------------------------------
try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets
    PYQT6 = False

# Aliases for better readability
Qt = QtCore.Qt
QEasing = QtCore.QEasingCurve
QVAnim = QtCore.QVariantAnimation
QSeqGroup = QtCore.QSequentialAnimationGroup

if PYQT6:
    EASING_CURVE = getattr(QEasing.Type, "InOutCubic", QEasing.InOutCubic)
    DRAW_FLAGS = QtWidgets.QWidget.RenderFlag.DrawChildren
else:
    EASING_CURVE = QEasing.InOutCubic
    DRAW_FLAGS = QtWidgets.QWidget.DrawChildren

# ---- Base -------------------------------------------------------------
try:
    from ..base import TransitionStrategy
except ImportError:
    class TransitionStrategy:
        def start(self, stack, to_index, duration_ms):
            return QSeqGroup()

class DoubleBufferedOverlay(QtWidgets.QWidget):
    """Safe overlay with double buffering"""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)

        # Critical safety settings
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

        self.setGeometry(parent.rect())
        self._from_pixmap: Optional[QtGui.QPixmap] = None
        self._to_pixmap: Optional[QtGui.QPixmap] = None
        self._progress = 0.0

        # Style for absolute transparency
        self.setStyleSheet("background: transparent; border: none;")

        self.hide()

    def set_pixmaps(self, from_pix: Optional[QtGui.QPixmap],
                   to_pix: Optional[QtGui.QPixmap]) -> None:
        """Set pixmaps in a thread-safe manner"""
        self._from_pixmap = from_pix
        self._to_pixmap = to_pix
        self.update()

    def set_progress(self, progress: float) -> None:
        """Set progress with bounds checking"""
        self._progress = max(0.0, min(1.0, progress))
        self.update()

    def show_overlay(self) -> None:
        """Show the overlay only after full setup"""
        self.show()
        self.raise_()

    def paintEvent(self, event: Optional[QtGui.QPaintEvent] = None) -> None:
        """Ultra-safe paint event"""
        try:
            if not self.isVisible():
                return

            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

            try:
                self._draw_content(painter)
            finally:
                painter.end()
        except Exception as e:
            print(f"Overlay paint error: {e}")

    def _draw_content(self, painter: QtGui.QPainter) -> None:
        """Draw the overlay content"""
        width, height = self.width(), self.height()
        if width <= 10 or height <= 10:
            return

        # Fade out and zoom in old page
        if (self._from_pixmap and not self._from_pixmap.isNull()):
            zoom = 1.0 + (0.08 * self._progress)
            scaled_width = int(width * zoom)
            scaled_height = int(height * zoom)
            x = (width - scaled_width) // 2
            y = (height - scaled_height) // 2

            opacity = 1.0 - self._progress
            painter.setOpacity(opacity)
            painter.drawPixmap(
                QtCore.QRect(x, y, scaled_width, scaled_height),
                self._from_pixmap,
                self._from_pixmap.rect()
            )

        # Fade in and zoom out new page
        if (self._to_pixmap and not self._to_pixmap.isNull()):
            zoom = 1.08 - (0.08 * self._progress)
            scaled_width = int(width * zoom)
            scaled_height = int(height * zoom)
            x = (width - scaled_width) // 2
            y = (height - scaled_height) // 2

            opacity = self._progress
            painter.setOpacity(opacity)
            painter.drawPixmap(
                QtCore.QRect(x, y, scaled_width, scaled_height),
                self._to_pixmap,
                self._to_pixmap.rect()
            )
        painter.setOpacity(1.0)

class CrossfadeZoomTransition(TransitionStrategy):
    """Memory-safe crossfade transition without flickering"""

    name = "Blurstorm"

    def start(self, stack: QtWidgets.QStackedWidget,
             to_index: int, duration_ms: int) -> QSeqGroup:

        # Thorough validation
        if not stack or stack.count() == 0:
            return QSeqGroup(stack)

        if to_index < 0 or to_index >= stack.count():
            return QSeqGroup(stack)

        current_idx = stack.currentIndex()
        if current_idx == to_index:
            return QSeqGroup(stack)

        # Get widgets
        from_widget = stack.widget(current_idx)
        to_widget = stack.widget(to_index)

        if not from_widget or not to_widget:
            return QSeqGroup(stack)

        # Create animation group
        animation_group = QSeqGroup(stack)

        # Create overlay (but do not show yet!)
        overlay = DoubleBufferedOverlay(stack)

        try:
            # 1. FIRST save all current visibility states
            visibility_states = {}
            for i in range(stack.count()):
                widget = stack.widget(i)
                if widget:
                    visibility_states[i] = widget.isVisible()
                    widget.hide()  # Hide all

            # 2. Create screenshots in separate steps
            size = stack.size()

            # Screenshot of the old page
            from_pixmap = self._capture_widget_hidden(from_widget, size)

            # Screenshot of the new page
            to_pixmap = self._capture_widget_hidden(to_widget, size)

            # 3. Set pixmaps to overlay (still invisible!)
            overlay.set_pixmaps(from_pixmap, to_pixmap)

            # 4. NOW show the overlay - prevents flickering
            overlay.show_overlay()

            # 5. Create animation and add to group
            anim = QVAnim(stack)
            anim.setDuration(max(300, min(2000, duration_ms)))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(EASING_CURVE)
            anim.valueChanged.connect(overlay.set_progress)

            animation_group.addAnimation(anim)

            def finish():
                """Clean finish without timing issues"""
                try:
                    # Switch index
                    stack.setCurrentIndex(to_index)

                    # Only make target widget visible
                    for i in range(stack.count()):
                        widget = stack.widget(i)
                        if widget:
                            widget.setVisible(i == to_index)

                finally:
                    # Delete overlay with delay (for smooth cleanup)
                    QtCore.QTimer.singleShot(100, overlay.deleteLater)

            animation_group.finished.connect(finish)

        except Exception as e:
            print(f"Transition error: {e}")
            # Fallback: Direct switch without animation
            self._fallback_switch(stack, to_index)
            overlay.deleteLater()

        return animation_group

    def _capture_widget_hidden(self, widget: QtWidgets.QWidget,
                              target_size: QtCore.QSize) -> QtGui.QPixmap:
        """Take a screenshot of a widget without making it visible"""
        try:
            # Temporarily set up widget in correct size
            original_size = widget.size()
            original_visible = widget.isVisible()

            # Prepare widget (but do not make visible!)
            widget.resize(target_size)

            # Create pixmap
            pixmap = QtGui.QPixmap(target_size)
            pixmap.fill(Qt.transparent)

            # Screenshot without visible display
            painter = QtGui.QPainter(pixmap)
            try:
                widget.render(painter, QtCore.QPoint(0, 0),
                            QtGui.QRegion(), DRAW_FLAGS)
            finally:
                painter.end()

            # Restore original state
            widget.resize(original_size)
            widget.setVisible(original_visible)

            return pixmap

        except Exception as e:
            print(f"Screenshot error: {e}")
            # Fallback: Empty pixmap
            fallback = QtGui.QPixmap(target_size)
            fallback.fill(Qt.transparent)
            return fallback

    def _fallback_switch(self, stack: QtWidgets.QStackedWidget, to_index: int) -> None:
        """Fallback for direct switch on errors"""
        try:
            stack.setCurrentIndex(to_index)
            for i in range(stack.count()):
                widget = stack.widget(i)
                if widget:
                    widget.setVisible(i == to_index)
        except Exception:
            pass

# Registration
def register_transition(registry: Dict) -> None:
    """Register the transition"""
    registry["crossfade_zoom"] = CrossfadeZoomTransition

