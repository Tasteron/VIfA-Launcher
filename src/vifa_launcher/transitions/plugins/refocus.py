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
# transitions/cinematic/refocus.py


import math

# ---- PyQt5/6 Shim ----------------------------------------------------
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = False

Qt   = QtCore.Qt
QE   = QtCore.QEasingCurve
QVA  = QtCore.QVariantAnimation
QSG  = QtCore.QSequentialAnimationGroup
QWidget        = QtWidgets.QWidget
QStackedWidget = QtWidgets.QStackedWidget
QPainter = QtGui.QPainter
QImage   = QtGui.QImage
QRect    = QtCore.QRect
QPoint   = QtCore.QPoint
QSize    = QtCore.QSize
QPointF  = QtCore.QPointF

if PYQT6:
    EASE        = getattr(QE.Type, "InOutQuad", QE.InOutQuad)
    RF_CHILDREN = QtWidgets.QWidget.RenderFlag.DrawChildren
    IgnoreAR    = Qt.AspectRatioMode.IgnoreAspectRatio
    SmoothTF    = Qt.TransformationMode.SmoothTransformation
    FormatARGB  = QImage.Format.Format_ARGB32_Premultiplied
else:
    EASE        = QE.InOutQuad
    RF_CHILDREN = QtWidgets.QWidget.DrawChildren
    IgnoreAR    = Qt.IgnoreAspectRatio
    SmoothTF    = Qt.SmoothTransformation
    FormatARGB  = QImage.Format_ARGB32_Premultiplied

# ---- Base -------------------------------------------------------------
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

# ---- Helpers ----------------------------------------------------------

def _render_widget_hidden(widget: QWidget, size: QSize) -> QImage:
    """
    Render a widget into an ARGB32 image WITHOUT making it visible.
    This is key to avoiding flickering!
    """
    w, h = max(1, size.width()), max(1, size.height())
    img = QImage(w, h, FormatARGB)
    img.fill(Qt.transparent)

    # Save widget state
    original_size = widget.size()
    original_visible = widget.isVisible()

    try:
        # Prepare widget for rendering (but DO NOT make it visible!)
        widget.resize(size)

        # Offscreen render without visibility
        p = QPainter(img)
        try:
            widget.render(p, QPoint(0, 0), QtGui.QRegion(), RF_CHILDREN)
        finally:
            p.end()

        # Restore original state
        widget.resize(original_size)
        widget.setVisible(original_visible)

    except Exception as e:
        print(f"Render error: {e}")
        # On error: return empty transparent image
        img.fill(Qt.transparent)

    return img

def _apply_warp_effect(image: QImage, progress: float) -> QImage:
    """
    Apply a simple warp effect to the image.
    progress: 0.0 (no effect) to 1.0 (maximum effect)
    """
    if image.isNull():
        return image

    width, height = image.width(), image.height()
    result = QImage(width, height, FormatARGB)
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # Simple wave effect for distortion
    wave_strength = min(width, height) * 0.02 * progress

    for y in range(0, height, 5):  # Step size for performance
        wave_offset = wave_strength * math.sin(y / 30.0)

        # Source
        src_rect = QRect(0, y, width, 5)

        # Destination with slight distortion
        dest_rect = QRect(int(wave_offset), y, width, 5)

        painter.drawImage(dest_rect, image, src_rect)

    painter.end()
    return result

def _apply_scale_effect(image: QImage, progress: float) -> QImage:
    """
    Apply a scaling effect to the image.
    """
    if image.isNull():
        return image

    width, height = image.width(), image.height()

    # Slight scaling change during transition
    scale = 1.0 - 0.1 * progress  # 1.0 → 0.9
    new_width = int(width * scale)
    new_height = int(height * scale)

    scaled = image.scaled(new_width, new_height, IgnoreAR, SmoothTF)

    result = QImage(width, height, FormatARGB)
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # Draw centered
    x_offset = (width - new_width) // 2
    y_offset = (height - new_height) // 2

    painter.drawImage(x_offset, y_offset, scaled)
    painter.end()

    return result

# ---- Overlay ----------------------------------------------------------

class _MorphOverlay(QWidget):
    """
    Overlay for the morph effect:
    - Shows an interpolated distortion between two pages
    """

    def __init__(self, parent_stack: QWidget, from_img: QImage, to_img: QImage):
        super().__init__(parent_stack)
        # Transparent overlay
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._from_img = from_img
        self._to_img = to_img
        self._t = 0.0  # 0..1
        # Do NOT show immediately - only after full setup!
        self.hide()

    def show_overlay(self):
        """Show the overlay only after full setup"""
        self.show()
        self.raise_()

    def set_images(self, from_img: QImage, to_img: QImage):
        """Set the images for the overlay"""
        self._from_img = from_img
        self._to_img = to_img
        self.update()

    def set_progress(self, t: float) -> None:
        self._t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
        self.update()

    def paintEvent(self, _: object) -> None:
        if self._from_img.isNull() or self._to_img.isNull():
            return
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)

            # Distortion strength based on progress
            # Maximum in the middle of the transition (t=0.5)
            warp_strength = 4.0 * self._t * (1.0 - self._t)  # Parabolic curve

            # Source effect (fading out)
            if self._t < 0.8:  # Only show up to 80%
                from_warped = _apply_warp_effect(self._from_img, warp_strength)
                from_scaled = _apply_scale_effect(from_warped, self._t)
                p.setOpacity(1.0 - self._t)
                p.drawImage(0, 0, from_scaled)

            # Target effect (fading in)
            if self._t > 0.2:  # Only show from 20%
                to_warped = _apply_warp_effect(self._to_img, warp_strength)
                to_scaled = _apply_scale_effect(to_warped, 1.0 - self._t)
                p.setOpacity(self._t)
                p.drawImage(0, 0, to_scaled)

            p.end()

        except Exception as e:
            print(f"Morph effect error: {e}")
            # Fallback: Simple crossfade
            p = QPainter(self)
            p.setOpacity(1.0 - self._t)
            p.drawImage(0, 0, self._from_img)
            p.setOpacity(self._t)
            p.drawImage(0, 0, self._to_img)
            p.end()

# ---- Strategy ---------------------------------------------------------

class DefocusRefocusTransition(TransitionStrategy):
    name = "refocus"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int) -> QSG:
        # Basic validation
        if to_index == stack.currentIndex():
            return QSG(stack)
        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSG(stack)
        size = QSize(w, h)
        from_idx = stack.currentIndex()
        from_widget = stack.widget(from_idx)
        to_widget = stack.widget(to_index)
        if not from_widget or not to_widget:
            return QSG(stack)

        # Create animation group
        animation_group = QSG(stack)

        # Create overlay (but do not show it yet!)
        overlay = _MorphOverlay(stack, QImage(), QImage())
        try:
            # 1. Hide ALL widgets immediately - PREVENTS FLICKERING!
            for i in range(stack.count()):
                widget = stack.widget(i)
                if widget:
                    widget.hide()

            # 2. Create screenshots WITHOUT visible widgets
            from_img = _render_widget_hidden(from_widget, size)
            to_img = _render_widget_hidden(to_widget, size)

            # 3. Fill overlay with images (still invisible)
            overlay.set_images(from_img, to_img)

            # 4. Show overlay NOW - NO FLICKERING!
            overlay.show_overlay()

            # 5. Animation 0..1
            anim = QVA(stack)
            anim.setDuration(max(1, int(duration_ms)))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(EASE)
            anim.valueChanged.connect(overlay.set_progress)
            animation_group.addAnimation(anim)

            def _finish():
                """Clean finish without timing issues"""
                try:
                    stack.setCurrentIndex(to_index)
                    # Only make target widget visible
                    for i in range(stack.count()):
                        widget = stack.widget(i)
                        if widget:
                            widget.setVisible(i == to_index)
                except Exception as e:
                    print(f"Finish error: {e}")
                finally:
                    # Delete overlay with delay (for smooth cleanup)
                    QtCore.QTimer.singleShot(100, overlay.deleteLater)

            animation_group.finished.connect(_finish)

        except Exception as e:
            print(f"Transition error: {e}")
            # Fallback: Direct switch
            self._fallback_switch(stack, to_index)
            overlay.deleteLater()
        return animation_group

    def _fallback_switch(self, stack: QStackedWidget, to_index: int):
        """Fallback for direct switch on errors"""
        try:
            stack.setCurrentIndex(to_index)
            for i in range(stack.count()):
                widget = stack.widget(i)
                if widget:
                    widget.setVisible(i == to_index)
        except Exception as e:
            print(f"Fallback error: {e}")

# Registration
def register_transition(registry):
    """Register the transition"""
    registry["defocus_refocus"] = DefocusRefocusTransition

