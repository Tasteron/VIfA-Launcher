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
# -*- coding: utf-8 -*-
# transitions/glitchy/fracture.py

import time
from typing import Optional, Dict

# ---- PyQt5/6 shim -----------------------------------------------------------------
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = False

# Aliases for better readability
Qt = QtCore.Qt
QE = QtCore.QEasingCurve
QVA = QtCore.QVariantAnimation
QSG = QtCore.QSequentialAnimationGroup
QWidget = QtWidgets.QWidget
QStackedWidget = QtWidgets.QStackedWidget
QPainter = QtGui.QPainter
QImage = QtGui.QImage
QRect = QtCore.QRect
QPoint = QtCore.QPoint
QSize = QtCore.QSize

if PYQT6:
    EASE = getattr(QE.Type, "Linear", QE.Linear)
    RF_CHILDREN = QtWidgets.QWidget.RenderFlag.DrawChildren
    IgnoreAR = Qt.AspectRatioMode.IgnoreAspectRatio
    SmoothTF = Qt.TransformationMode.SmoothTransformation
    FormatARGB = QImage.Format.Format_ARGB32_Premultiplied
else:
    EASE = QE.Linear
    RF_CHILDREN = QtWidgets.QWidget.DrawChildren
    IgnoreAR = Qt.IgnoreAspectRatio
    SmoothTF = Qt.SmoothTransformation
    FORMATARGB = QImage.Format_ARGB32_Premultiplied

try:
    from ..base import TransitionStrategy
except Exception:
    class TransitionStrategy:
        def start(self, stack, to_index, duration_ms):
            return QSG()

# -------- Helpers -----------------------------------------------------------------
def _render_widget_completely_hidden(widget: QWidget, size: QSize) -> QImage:
    """
    Renders widget completely offscreen WITHOUT any visibility changes.
    CRITICAL: No processEvents(), no move(), no setVisible() —
    this prevents flickering 100%!
    """
    w, h = max(1, size.width()), max(1, size.height())

    # ARGB format for transparency
    if PYQT6:
        img = QImage(w, h, FormatARGB)
    else:
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)

    # Fully save widget state
    original_size = widget.size()
    original_pos = widget.pos()
    original_visible = widget.isVisible()
    original_parent = widget.parent()

    try:
        # Only adjust size — no other changes!
        widget.resize(size)

        # NO processEvents() — this is the key!
        # NO move() — position doesn't matter for rendering
        # NO setVisible() — remains invisible

        # Direct offscreen rendering
        p = QPainter(img)
        try:
            widget.render(p, QPoint(0, 0), QtGui.QRegion(), RF_CHILDREN)
        finally:
            p.end()

        # Fully restore
        widget.resize(original_size)
        widget.move(original_pos)
        widget.setVisible(original_visible)

    except Exception as e:
        print(f"Hidden render error: {e}")
        # On error: transparent image
        img.fill(Qt.transparent)

        # Safety restore
        try:
            widget.resize(original_size)
            widget.move(original_pos)
            widget.setVisible(original_visible)
        except:
            pass

    return img

# -------- Overlay (Ultra-safe) ---------------------------------------------------------
class _Overlay(QWidget):
    def __init__(self, parent_stack: QWidget):
        super().__init__(parent_stack)
        # Maximum transparency attributes
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setStyleSheet("background: transparent; border: none;")
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._from = QImage()
        self._to = QImage()
        self._t = 0.0
        H = max(1, self.height())
        bands = max(10, H // 28)
        self._bands = bands
        self._band_h = max(1, H // bands)

        # Deterministic glitch offsets
        import random
        rng = random.Random(42)
        self._base = [rng.uniform(-1.0, 1.0) for _ in range(bands)]
        # CRITICAL: Do not show immediately!
        self.hide()

    def set_images(self, from_img: QImage, to_img: QImage):
        """Sets the source and target images"""
        self._from = from_img
        self._to = to_img
        self.update()

    def show_overlay(self):
        """Shows overlay only after complete setup"""
        self.show()
        self.raise_()
        # NO processEvents() here!

    def set_progress(self, t: float):
        self._t = max(0.0, min(1.0, float(t)))
        self.update()

    def paintEvent(self, _: object) -> None:
        W, H = self.width(), self.height()
        bands, band_h = self._bands, self._band_h
        t = self._t
        if W <= 0 or H <= 0:
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            # Glitch intensity: parabolic peak in the middle
            jt = 1.0 - abs(2.0 * t - 1.0)
            max_dx = int(24 * jt)
            # Phase 1: FROM image with glitch (fading out)
            if not self._from.isNull() and t < 1.0:
                p.setOpacity(1.0 - t)
                for bi in range(bands):
                    y = bi * band_h
                    bh = band_h if bi < bands - 1 else H - y
                    if bh <= 0:
                        continue

                    dx = int(self._base[bi] * max_dx) if max_dx > 0 else 0
                    src = QRect(0, y, W, bh)
                    dst = QRect(dx, y, W, bh)

                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.drawImage(dst, self._from, src)
            # Phase 2: TO image with glitch (fading in)
            if not self._to.isNull() and t > 0.0:
                p.setOpacity(t)
                for bi in range(bands):
                    y = bi * band_h
                    bh = band_h if bi < bands - 1 else H - y
                    if bh <= 0:
                        continue

                    dx = int(self._base[bi] * max_dx) if max_dx > 0 else 0
                    src = QRect(0, y, W, bh)
                    dst = QRect(dx, y, W, bh)

                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.drawImage(dst, self._to, src)
            p.setOpacity(1.0)
        except Exception as e:
            print(f"Paint error: {e}")
        finally:
            p.end()

# -------- Strategy (Flicker-free) -------------------------------------------------
class GlitchStripsTransition(TransitionStrategy):
    name = "fracture"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int) -> QSG:
        # Basic validation
        if to_index == stack.currentIndex():
            return QSG(stack)
        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSG(stack)
        size = QSize(w, h)
        from_widget = stack.widget(stack.currentIndex())
        target = stack.widget(to_index)
        if not from_widget or not target:
            return QSG(stack)

        # Animation group
        grp = QSG(stack)
        overlay = _Overlay(stack)
        try:
            # 1. IMMEDIATELY hide all widgets — PREVENTS FLICKERING!
            for i in range(stack.count()):
                widget = stack.widget(i)
                if widget:
                    widget.hide()

            # NO processEvents() here!
            # 2. Render BOTH sides completely hidden
            from_img = _render_widget_completely_hidden(from_widget, size)
            to_img = _render_widget_completely_hidden(target, size)

            # 3. Populate overlay with images (still hidden)
            overlay.set_images(from_img, to_img)

            # 4. Only now show overlay — GUARANTEED no flicker!
            overlay.show_overlay()
            # 5. Create animation
            anim = QVA(stack)
            anim.setDuration(max(1, int(duration_ms)))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(EASE)
            anim.valueChanged.connect(overlay.set_progress)
            grp.addAnimation(anim)

            def _finish():
                """Ultra-safe finish"""
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
                    # Overlay cleanup with delay
                    QtCore.QTimer.singleShot(100, overlay.deleteLater)

            grp.finished.connect(_finish)

        except Exception as e:
            print(f"Transition setup error: {e}")
            # Emergency fallback
            self._emergency_fallback(stack, to_index)
            try:
                overlay.deleteLater()
            except:
                pass
        return grp

    def _emergency_fallback(self, stack: QStackedWidget, to_index: int):
        """Emergency fallback without any animation"""
        try:
            stack.setCurrentIndex(to_index)
            for i in range(stack.count()):
                widget = stack.widget(i)
                if widget:
                    widget.setVisible(i == to_index)
        except Exception as e:
            print(f"Emergency fallback error: {e}")

# Registration
def register_transition(registry):
    """Registers the transition"""
    registry["glitch_strips"] = GlitchStripsTransition

