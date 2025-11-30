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


# ----------------------------------------------------------------------
# Compatibility shim (PyQt5 ↔ PyQt6)
# ----------------------------------------------------------------------
try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = False

Qt = QtCore.Qt
QEasingCurve = QtCore.QEasingCurve
QVariantAnimation = QtCore.QVariantAnimation
QSequentialAnimationGroup = QtCore.QSequentialAnimationGroup
QRect = QtCore.QRect
QRegion = QtGui.QRegion
QPalette = QtGui.QPalette
QWidget = QtWidgets.QWidget
QStackedWidget = QtWidgets.QStackedWidget
QStackedLayout = QtWidgets.QStackedLayout

# Enums / aliases
if PYQT6:
    EASING_LINEAR = getattr(QEasingCurve.Type, "Linear", QEasingCurve.Linear)
    SL_StackAll = QStackedLayout.StackingMode.StackAll
    SL_StackOne = QStackedLayout.StackingMode.StackOne
else:
    EASING_LINEAR = QEasingCurve.Linear
    SL_StackAll = QStackedLayout.StackAll
    SL_StackOne = QStackedLayout.StackOne

# ----------------------------------------------------------------------
# Base class import (relative)
# ----------------------------------------------------------------------
try:
    from ..base import TransitionStrategy
except Exception:  # pragma: no cover
    from ..base import TransitionStrategy  # type: ignore

# ----------------------------------------------------------------------
# BarnDoorTransition – Live Widget Masking
# ----------------------------------------------------------------------
class BarnDoorTransition(TransitionStrategy):
    """Barn-door wipe using live widgets and QRegion mask (no grabs)."""
    name = "gate"

    def _apply_masks(self, from_w: QWidget, to_w: QWidget, t: float) -> None:
        """Set barn-door masks on both widgets for progress t ∈ [0,1]."""
        width = to_w.width()
        height = to_w.height()
        if width <= 0 or height <= 0:
            from_w.clearMask()
            to_w.clearMask()
            return
        cx = width // 2
        door = int(max(0.0, min(1.0, float(t))) * cx)
        if door <= 0:
            # New page remains invisible; only old page visible
            from_w.clearMask()
            return
        if door >= cx:
            # New page fully visible, old page fully hidden
            to_w.clearMask()
            from_w.setMask(QRegion())
            return
        # Visible area of the new page
        left_visible = QRect(cx - door, 0, door, height)
        right_visible = QRect(cx, 0, door, height)
        to_w.setMask(QRegion(left_visible) | QRegion(right_visible))
        # Inverse mask for old page
        left_hidden = QRect(0, 0, cx - door, height)
        right_hidden = QRect(cx + door, 0, width - (cx + door), height)
        from_w.setMask(QRegion(l eft_hidden) | QRegion(right_hidden))

    def start(
        self,
        stack: QStackedWidget,
        to_index: int,
        duration_ms: int,
    ) -> QSequentialAnimationGroup:
        # Trivial case handling
        if to_index == stack.currentIndex():
            return QSequentialAnimationGroup(stack)
        if stack.width() <= 0 or stack.height() <= 0:
            return QSequentialAnimationGroup(stack)
        from_idx = stack.currentIndex()
        from_w = stack.widget(from_idx)
        to_w = stack.widget(to_index)
        if to_w is None or from_w is None:
            return QSequentialAnimationGroup(stack)

        # StackingMode: both pages visible — but only these two!
        lay = stack.layout()
        if isinstance(lay, QStackedLayout):
            try:
                prev_mode = lay.stackingMode()
            except Exception:
                prev_mode = SL_StackOne
            lay.setStackingMode(SL_StackAll)
        else:
            prev_mode = None

        # Hide all other pages
        for i in range(stack.count()):
            if i not in (from_idx, to_index):
                w = stack.widget(i)
                if w:
                    w.setVisible(False)

        # Initially keep target page invisible
        to_w.setVisible(False)
        to_w.lower()  # ensure it's below for safety
        to_w.setGeometry(stack.rect())
        from_w.setGeometry(stack.rect())

        # Initial state: doors closed, only old page visible
        self._apply_masks(from_w, to_w, 0.0)
        from_w.setVisible(True)

        # Configure animation
        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(EASING_LINEAR)
        shown = {"to": False}

        def on_value_changed(v):
            t = float(v)
            if not shown["to"] and t > 0.0:
                # Only show now when mask > 0
                to_w.setVisible(True)
                to_w.raise_()
                shown["to"] = True
            self._apply_masks(from_w, to_w, t)

        anim.valueChanged.connect(on_value_changed)
        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            # Remove masks
            from_w.clearMask()
            to_w.clearMask()
            # Officially activate target page
            stack.setCurrentIndex(to_index)
            # Visibility: only show active page (classic behavior)
            for i in range(stack.count()):
                w = stack.widget(i)
                if w:
                    w.setVisible(i == to_index)
            # Restore StackingMode
            if isinstance(lay, QStackedLayout) and prev_mode is not None:
                lay.setStackingMode(prev_mode)

        grp.finished.connect(finish)
        return grp

